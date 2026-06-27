# 模型下载改进方案

> 日期：2026-06-26
> 基于：深度代码排查 + SDK 分析
> 状态：待 Qoder 审核

---

## 一、问题根因分析

### 1.1 SDK 超时机制

ModelScope SDK（v1.37.1）内部超时配置：

| 配置 | 值 | 说明 |
|------|-----|------|
| `API_FILE_DOWNLOAD_TIMEOUT` | 60s | per-socket-read（每次 `recv()` 操作的超时） |
| `API_HTTP_CLIENT_TIMEOUT` | 60s | API 调用超时（连接 + 读取 HTTP 头） |
| 重试次数 | 5 次 | 指数退避: 0s, 1s, 2s, 4s, 8s |
| 分块阈值 | 500MB | 超过此大小分块并行下载 |
| 分块大小 | 160MB | 每个 chunk |
| 并行 workers | 1 | 默认单线程 |

**超时机制详解**：

SDK 的 60s 超时是 **per-socket-read**（`requests.get(timeout=60)`），含义是：
- 连接阶段：TCP 握手必须在 60s 内完成
- 读取阶段：**每次** `socket.recv()` 必须在 60s 内返回数据

对于大文件下载（流式传输）：
- 1GB 文件下载可能耗时 2.5 小时（100KB/s）
- 但只要网络持续传输数据，每次 `recv()` 都在 60s 内返回，就不会触发超时
- 只有当 socket **完全沉默** 超过 60s 才会超时（网络中断、服务器卡死）

**实际风险点**：
1. **连接超时**（60s）— 对慢速网络或服务器响应慢可能不够
2. **网络抖动** — 短暂中断后恢复，SDK 会重试（5 次 + 指数退避）
3. **重试耗尽** — 5 次重试后抛出 `FileDownloadError`，被项目代码捕获

### 1.2 下载速度预估

| 网络速度 | SenseVoiceSmall (900MB) | ct-punc (1GB) | cam++ (60MB) | fsmn-vad (2MB) |
|----------|------------------------|---------------|--------------|----------------|
| 50 KB/s | 5 小时 | 5.7 小时 | 20 分钟 | 40 秒 |
| 100 KB/s | 2.5 小时 | 2.8 小时 | 10 分钟 | 20 秒 |
| 500 KB/s | 30 分钟 | 34 分钟 | 2 分钟 | 4 秒 |
| 1 MB/s | 15 分钟 | 17 分钟 | 1 分钟 | 2 秒 |

### 1.3 当前代码问题

| 问题 | 影响 | 严重性 |
|------|------|--------|
| 首次启动弹窗阻塞用户操作 | 用户被迫等待 2.5h+ | **高** |
| 进度回调无实际进度 | 用户不知道还要等多久 | 中 |
| 无错误分类 | 用户只看到"下载失败" | 中 |
| 完整性校验仅检查文件大小 | 无法检测数据损坏 | 中 |
| 无下载/转写并发保护 | 边下载边转写可能冲突 | 低 |

---

## 二、改进方案

### 2.1 后台下载（核心改动）

**目标**：首次启动时不阻塞用户，模型在后台下载，用户可先操作和设置。

**当前流程**：
```
首次启动 → 弹窗 → 下载模型（阻塞 2.5h+）→ 完成后进入主界面
```

**改进流程**：
```
首次启动 → 显示"模型未就绪"提示 → 用户点击"后台下载" → 进入主界面
→ 状态栏显示下载进度 → 下载完成通知用户 → 转写功能可用
```

#### 2.1.1 首次启动界面改造

文件：`src/gui/first_launch.py`

**改动**：
1. 将"下载模型"步骤改为可选（不是必须等待完成）
2. 添加"后台下载，先去设置"按钮
3. 下载状态通过信号通知主界面

**新 UI 流程**：
```
Step 1: Beta 说明 + API Key 选择
Step 2: 模型下载（可选）
  ├── [立即下载] - 等待完成（适合快速网络）
  └── [后台下载] - 立即进入主界面，后台继续
```

#### 2.1.2 主界面状态栏

文件：`src/gui/app.py`

**改动**：
1. 添加状态栏下载进度显示
2. 下载完成时弹出通知
3. 转写按钮在模型未就绪时禁用（附提示文字）

#### 2.1.3 设置页下载改造

文件：`src/gui/settings_page.py`

**改动**：
1. 进度回调改为实际进度（当前是 `lambda m: None`）
2. 显示每个模型的下载状态和速度

### 2.2 超时和重试改进

**目标**：增大 SDK 超时值，添加项目级重试。

#### 2.2.1 增大 SDK 超时

文件：`src/transcriber.py`

在 `_setup_modelscope_cache()` 中添加超时配置（monkey-patch SDK 常量）：

```python
def _setup_modelscope_cache(cache_dir):
    """设置 MODELSCOPE_CACHE 环境变量并调整 SDK 超时"""
    global _MODELSCOPE_CACHE_SET
    if _MODELSCOPE_CACHE_SET or not cache_dir:
        return
    os.environ["MODELSCOPE_CACHE"] = cache_dir
    os.environ.setdefault("MODELSCOPE_SCENARIO", "cli")
    
    # 增大 SDK 超时（默认 60s 对慢速网络不够）
    try:
        import modelscope.hub.constants as hc
        hc.API_FILE_DOWNLOAD_TIMEOUT = 120   # per-socket-read: 120s
        hc.API_HTTP_CLIENT_TIMEOUT = 120     # 连接+API调用: 120s
    except (ImportError, AttributeError):
        pass  # SDK 版本变化时静默跳过
    
    _MODELSCOPE_CACHE_SET = True
    logger.info(f"MODELSCOPE_CACHE set to: {cache_dir}")
```

**超时值说明**：
- **per-socket-read 120s**：不是下载总时间超时，而是每次 `recv()` 操作的超时
  - 数据持续流动时不会触发（100KB/s 下每次 recv 都在 120s 内返回）
  - 仅在网络完全沉默（中断/卡死）时才触发
  - 从 60s 提升到 120s，给网络抖动留足 buffer
- **连接超时 120s**：应对慢速网络的 TCP 握手和服务器响应
- SDK 内部已有 5 次重试 + 指数退避，连接超时后会自动重试

#### 2.2.2 项目级重试

文件：`src/transcriber.py`

在 `download_model()` 中添加重试逻辑：

```python
def download_model(self, model_id, progress_callback=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            # ... 现有下载逻辑
            return True, "下载完成"
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"下载失败，{wait}s 后重试: {e}")
                time.sleep(wait)
            else:
                return False, f"下载失败（已重试 {max_retries} 次）: {e}"
```

### 2.3 进度监控改进

**目标**：显示真实的下载进度和速度。

#### 2.3.1 进度回调增强

文件：`src/transcriber.py`

在 `download_model()` 中添加进度计算：

```python
def download_model(self, model_id, progress_callback=None):
    # 计算总体进度
    total_models = len(REQUIRED_MODELS)
    model_index = list(REQUIRED_MODELS.keys()).index(model_id)
    
    def _progress_handler(msg):
        base_percent = (model_index / total_models) * 100
        model_percent = 10  # 每个模型占 10% 进度
        if progress_callback:
            progress_callback(base_percent + model_percent, msg)
    
    # 传递给 snapshot_download 的 progress 钩子
```

#### 2.3.2 进度显示改造

文件：`src/gui/first_launch.py`, `src/gui/settings_page.py`

- `first_launch.py`：进度条改为确定模式（0-100%）
- `settings_page.py`：添加 `progress` 信号，显示速度和预计剩余时间

### 2.4 完整性校验改进

**目标**：增加 hash 校验，防止数据损坏。

文件：`src/transcriber.py`

在 `check_all_models()` 中添加可选的 hash 校验：

```python
# 从 configuration.json 获取文件的 expected hash
config = json.load(open(os.path.join(local_path, "configuration.json")))
expected_hash = config.get("file_path_metas", {}).get("init_param_hash")
if expected_hash:
    actual_hash = hashlib.md5(open(weight_path, "rb").read()).hexdigest()
    if actual_hash != expected_hash:
        size_ok = False  # 标记为不完整
```

**注意**：ModelScope 的 configuration.json 不一定包含 hash，需要验证。如果 SDK 不提供 hash，则保持现有大小校验。

### 2.5 错误分类和用户提示

**目标**：区分不同错误类型，给用户有用的提示。

文件：`src/transcriber.py`

```python
except Exception as e:
    error_str = str(e).lower()
    if "timeout" in error_str or "timed out" in error_str:
        return False, "下载超时，请检查网络连接后重试"
    elif "connection" in error_str:
        return False, "无法连接到下载服务器，请检查网络"
    elif "disk" in error_str or "no space" in error_str:
        return False, "磁盘空间不足，请清理后重试"
    elif "permission" in error_str:
        return False, "没有写入权限，请以管理员身份运行"
    elif "FileDownloadError" in type(e).__name__:
        return False, f"文件下载失败: {e}"
    else:
        return False, f"下载失败: {e}"
```

---

## 三、文件修改清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/transcriber.py` | 修改 | 超时配置、项目级重试、进度回调、错误分类 |
| `src/gui/first_launch.py` | 修改 | 后台下载按钮、进度条改为确定模式 |
| `src/gui/settings_page.py` | 修改 | 进度回调增强、添加 progress 信号 |
| `src/gui/app.py` | 修改 | 状态栏下载进度、转写按钮禁用逻辑 |
| `scripts/diagnose_model_download.py` | 新增 | 诊断脚本（已完成） |

---

## 四、执行顺序

### Phase 1: 诊断验证（立即）
1. 运行 `python scripts/diagnose_model_download.py` 确认下载速度
2. 根据速度调整超时值

### Phase 2: 核心改进（1-2 天）
1. 修改 `transcriber.py`：超时配置 + 项目级重试 + 错误分类
2. 修改 `first_launch.py`：后台下载按钮
3. 修改 `app.py`：状态栏进度显示

### Phase 3: 完善（0.5 天）
1. 修改 `settings_page.py`：进度回调增强
2. 完整性校验改进（如果 SDK 提供 hash）
3. 测试验证

---

## 五、给 Qoder 的审查要点

1. **超时值**：300s per-socket-read 是否合理？是否需要更大？
2. **后台下载**：首次启动 UI 改造方案是否可行？
3. **项目级重试**：3 次重试 + 指数退避是否足够？
4. **错误分类**：是否遗漏了其他错误类型？
5. **完整性校验**：是否需要增加 hash 校验？SDK 的 configuration.json 是否包含 hash？
6. **并发保护**：是否需要添加下载/转写互斥锁？

---

## Qoder 审查结果

> 审查日期：2026-06-26
> 审查方法：逐行核实 transcriber.py、first_launch.py、settings_page.py 的实际代码

### 排查报告核实

排查报告中的所有关键结论均已验证，**全部准确**：

| 结论 | 验证结果 |
|------|---------|
| 4 个模型（SenseVoiceSmall 900MB、fsmn-vad 2MB、ct-punc 1GB、cam++ 60MB） | 正确，transcriber.py L44-77 |
| 无项目级超时 | 正确，snapshot_download 仅传 2 个参数 |
| 无项目级重试 | 正确，单次尝试，失败直接返回 |
| 完整性校验 = 目录存在 + 权重文件存在 + 最小文件大小 + 辅助文件 | 正确，无 hash 校验 |
| first_launch 进度始终为 0 | 正确，L42-43 硬编码 emit(0, msg) |
| settings_page 吞掉进度回调 | 正确，L36 使用 `lambda m: None` |
| CAM++ 加载增加了本地路径解析 | 正确，L1069-1073 |
| 新旧代码下载逻辑无差异 | 正确，新版未引入下载相关 bug |

### 对改进方案的意见

**2.1 后台下载 — 同意，这是最重要的改动**

方案可行且必要。当前首次启动阻塞用户 2.5h+ 是不可接受的。补充两个注意事项：

1. **部分下载恢复**：用户关闭程序时，ModelScope SDK 会留下不完整的文件。重新下载时 SDK 是否能断点续传？如果不能，需要在后台下载逻辑中清理残留文件后重新下载。建议检查 SDK 的 `snapshot_download` 对不完整缓存的行为。

2. **下载完成通知**：方案提到"下载完成时弹出通知"，但要注意不要在用户正在操作时弹模态对话框。建议用非侵入式通知（状态栏文字变化 + 转写按钮自动启用），不要用 QMessageBox。

**2.2 超时和重试 — 同意，有一个数值不一致需要注意**

方案代码示例中写的是 120s，但审查要点中问的是 300s。**建议用 180s**：
- 120s 对大多数网络抖动足够
- 300s 太长，如果服务器真的卡死，用户要等 5 分钟才发现超时
- 180s 是一个折中值，且 SDK 内部已有 5 次重试，项目级再重试 3 次 = 总共 15 次机会

monkey-patch SDK 常量的方式有版本风险：modelscope 升级后可能改名或移除这些常量。建议在 try/except 中静默处理（方案已考虑到），并加一行注释标明依赖的 SDK 版本。

**2.3 进度监控 — 方向正确，实现细节需要调整**

方案中的进度计算有问题：

```python
base_percent = (model_index / total_models) * 100
model_percent = 10  # 每个模型占 10% 进度
```

这不对。4 个模型总大小约 2GB，但 fsmn-vad 只有 2MB，ct-punc 有 1GB。如果按模型数量均分进度，下载 2MB 的 fsmn-vad 和下载 1GB 的 ct-punc 显示的进度一样，用户体验会很奇怪（大文件卡在同一个百分比很久）。

**建议按模型大小加权分配进度**：

```python
model_sizes = {
    "SenseVoiceSmall": 900,
    "fsmn-vad": 2,
    "ct-punc": 1000,
    "cam++": 60,
}
total_size = sum(model_sizes.values())  # ~1962 MB

# 每个模型的进度权重
for model_id in REQUIRED_MODELS:
    weight = model_sizes[model_id] / total_size
    # SenseVoiceSmall: 46%, ct-punc: 51%, cam++: 3%, fsmn-vad: 0.1%
```

另外，ModelScope SDK 的 `snapshot_download` 不直接提供字节级进度回调。如果想显示真正的下载百分比，需要用 SDK 的 `DownloadDataset` 或手动 HTTP 请求。如果实现太复杂，先用"当前第 N/4 个模型 + 模型名称"的文本进度也可以接受。

**2.4 完整性校验 — hash 校验不可行，保持现状**

mimo 自己也在文档末尾标注了"configuration.json 不一定包含 hash"。我核实了本地缓存的 configuration.json，确认 **不包含文件 hash**。ModelScope SDK 下载完成后自身会做校验，如果文件损坏 SDK 会报错。所以现有的最小文件大小校验已经足够，不建议增加 hash 校验。

**2.5 错误分类 — 同意，补充两个错误类型**

方案的关键词匹配方式简单有效。补充：

1. `"ssl"` 或 `"certificate"` → "SSL 证书验证失败，可能是公司网络代理导致，请检查网络环境"
2. `"quota"` 或 `"rate limit"` → "下载频率超限，请稍后重试"

这两个在企业网络环境中比较常见。

**2.6 并发保护 — 建议添加简单互斥**

方案没有覆盖这点（审查要点中提了但改进方案没写）。建议在 `ModelManager` 中添加一个简单的下载锁：

```python
import threading

class ModelManager:
    _download_lock = threading.Lock()
    
    def download_model(self, model_id, ...):
        if not self._download_lock.acquire(blocking=False):
            return False, "已有下载任务正在进行"
        try:
            # ... 现有下载逻辑
        finally:
            self._download_lock.release()
```

这可以防止用户在设置页点下载的同时，首次引导也在后台下载。

### 审查要点回答

1. **超时值**：建议 180s（方案代码和审查要点中的 120s/300s 不一致）
2. **后台下载**：可行，注意不要用模态弹窗通知完成
3. **项目级重试**：3 次 + 指数退避足够（加上 SDK 内部 5 次 = 总共 15 次机会）
4. **错误分类**：补充 SSL 证书和配额限制两种类型
5. **完整性校验**：保持现状，SDK 已做内部校验，configuration.json 不含 hash
6. **并发保护**：建议添加 threading.Lock 互斥

### 执行优先级建议

| 优先级 | 改动 | 原因 |
|--------|------|------|
| P0 | 后台下载（2.1） | 解决用户被阻塞 2.5h 的核心痛点 |
| P0 | 超时增大（2.2） | 一行代码，立竿见影 |
| P1 | 错误分类（2.5） | 用户能看到有意义的错误提示 |
| P1 | 进度监控（2.3） | 用户知道还要等多久 |
| P2 | 项目级重试（2.2.2） | SDK 已有 5 次重试，优先级可以稍低 |
| P2 | 并发保护（2.6） | 低风险场景，但防御性编程值得做 |
| 跳过 | hash 校验（2.4） | SDK 已做，configuration.json 不含 hash |
