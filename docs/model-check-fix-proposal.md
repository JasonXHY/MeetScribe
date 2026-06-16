# 模型检查与下载功能缺陷修复方案

> 版本：v1.0 → v1.1（QoderWork 审查修订）
> 日期：2026-06-16
> 状态：已审查
> 审查人：QoderWork

---

## 一、缺陷清单

### 缺陷 1：检查只验证目录 + 主权重文件，不检查辅助文件（P0）

**位置**：`src/transcriber.py:125-178` `ModelManager.check_all_models()`

**现状**：
```
目录存在？ → configuration.json 存在？ → 主权重文件(model.pt)存在？ → cached=True
```

**问题**：SenseVoice 实际需要 3 类文件才能运行：
- `model.pt`（主权重，936MB）— 已检查
- `configuration.json`（模型配置）— 已检查
- `chn_jpn_yue_eng_ko_spectok.bpe.model`（tokenizer，377KB）— **未检查**

**后果**：目录存在 + `model.pt` 存在 = UI 显示"已缓存 ✅"，但转写时因缺少 tokenizer 崩溃：`Not found: chn_jpn_yue_eng_ko_spectok.bpe.model`

**复现**：从旧版复制 `models_cache` 时遗漏 tokenizer 文件，设置页检查显示正常，转写失败。

---

### 缺陷 2：两个 ModelManager 实现不一致（P1）

**位置**：
- `src/model_manager.py:13` — 简单版，仅检查目录存在
- `src/transcriber.py:117` — 完整版，检查目录 + configuration.json + 权重

**问题**：
- ~~`model_manager.py` 被 `app.py` 和其他模块引用~~，但 `settings_page.py` 使用 `transcriber.py` 的版本 <!-- [QW] 事实错误：经 grep 全项目确认，`from model_manager import` 和 `import model_manager` 均返回 0 条匹配。`app.py` 中无任何 ModelManager 或 model_manager 引用。实际只有 `transcriber.py:350` 和 `settings_page.py:59` 两处使用 `transcriber.ModelManager` -->
- 两套检查逻辑不一致，容易混淆
- `model_manager.py` 的 `check_models()` 只检查目录，完全不足以判断模型可用性

<!-- [QW] 补充：缺陷 2 的严重性被高估。既然没有任何代码引用 model_manager.py，它实际上是一个死代码文件，不存在"两套逻辑运行时不一致"的问题。正确的处理方式是直接删除该文件，而非保留 shim -->

---

### 缺陷 3：下载不验证完整性（P1）

**位置**：`src/transcriber.py:191-230` `ModelManager.download_model()`

**现状**：
```python
def download_model(self, model_id, progress_callback=None):
    # 实际代码（transcriber.py:207-209）：
    local_path = os.path.join(self.cache_dir, "models", "iic", model_name)
    if os.path.isdir(local_path):
        return True, f"模型 {model_id} 已在本地缓存"  # ← 空目录也返回 True！
    snapshot_download(model_name, cache_dir=self.cache_dir)
    self.check_all_models()  # 直接保存，不验证
    return True, f"模型 {model_id} 下载完成"
```
<!-- [QW] 原文档伪代码与实际代码有出入。实际代码在 line 208-209 先检查 `os.path.isdir(local_path)` 就返回"已缓存"，
这意味着：(1) 如果之前下载中断留下了空目录，再次调用会误报"已缓存"而跳过下载——这是第 6 个缺陷，见下方补充 -->

**问题**：网络中断、磁盘满、部分下载 → 文件不完整 → 通过检查 → 转写时崩溃

---

### 缺陷 6（QoderWork 补充）：download_model() 空目录假阳性（P1）

**位置**：`src/transcriber.py:207-209`

**现状**：
```python
local_path = os.path.join(self.cache_dir, "models", "iic", model_name)
if os.path.isdir(local_path):
    return True, f"模型 {model_id} 已在本地缓存"
```

**问题**：`os.path.isdir()` 只检查目录是否存在，不检查目录是否为空或内容完整。如果上次下载被中断（如用户强制关闭程序），`os.makedirs(local_dir, exist_ok=True)`（line 221）已经创建了目录，但文件未下载完成。再次调用时直接返回"已缓存"，跳过下载。

**后果**：用户看到"模型已就绪"，但实际缺少模型文件，转写时报错。

**修复建议**：将 `os.path.isdir(local_path)` 改为调用 `check_all_models()` 中对单个模型的完整性检查，或至少检查目录非空：
```python
if os.path.isdir(local_path) and os.listdir(local_path):
    # 目录存在且非空，进一步检查文件完整性
    ...
```

---

### 缺陷 4：无文件大小校验（P2）

**位置**：`src/transcriber.py:125-178` `check_all_models()`

**问题**：不对比已下载文件与预期大小。0 字节的 `model.pt` 或截断的 tokenizer 文件无法被检测。

---

### 缺陷 5：fsmn-vad 未纳入旧版 ModelManager（P2）

**位置**：`src/model_manager.py:17-30`

**现状**：
```python
MODELS = {
    "sensevoice": {...},
    "cam++": {...},
    "ct-punc": {...},
    # fsmn-vad 缺失！
}
```

**问题**：旧版 ModelManager 缺少 fsmn-vad 模型定义，如果代码路径走到旧版检查，会遗漏 VAD 模型。

---

## 二、修复方案

### 修复 1：增强 check_all_models() 关键辅助文件检查

**文件**：`src/transcriber.py`

**改动**：在 `check_all_models()` 中，对 SenseVoice 模型增加 tokenizer 文件检查。

```python
# ── 新增：每个模型的必需辅助文件 ──
REQUIRED_AUX_FILES = {
    "SenseVoiceSmall": ["chn_jpn_yue_eng_ko_spectok.bpe.model"],
    "fsmn-vad": [],  # 无额外必需文件
    "ct-punc": [],   # 无额外必需文件
    "cam++": [],     # 无额外必需文件
}

class ModelManager:
    def check_all_models(self):
        results = {}
        for model_id, info in REQUIRED_MODELS.items():
            # ... 现有逻辑：检查目录 + configuration.json + 主权重 ...

            # ── 新增：检查必需辅助文件 ──
            aux_files = REQUIRED_AUX_FILES.get(model_id, [])
            aux_missing = []
            for aux_file in aux_files:
                if not os.path.isfile(os.path.join(local_path, aux_file)):
                    aux_missing.append(aux_file)

            cached = dir_exists and has_weights and not aux_missing

            results[model_id] = {
                "cached": cached,
                "path": local_path if cached else None,
                "info": info,
                "aux_missing": aux_missing,  # 新增字段
            }
        return results
```

**影响范围**：仅影响 `cached` 判断逻辑，不改变接口。

---

### 修复 2：统一 ModelManager，废弃 model_manager.py

**文件**：~~`src/model_manager.py`、`src/gui/app.py`~~ <!-- [QW] app.py 无任何 ModelManager 引用，不需要改动 -->

**方案**：
1. ~~`model_manager.py` 的 ModelManager 改为从 `transcriber.py` 导入，或直接删除~~
2. ~~`app.py` 中引用改为使用 `transcriber.ModelManager`~~
3. ~~保留 `model_manager.py` 作为兼容 shim（内部转发）~~

<!-- [QW] 方案需要重大修改，原因如下：

1. **shim 不必要**：全项目 grep 确认没有任何文件 `from model_manager import ModelManager`。唯一使用 ModelManager 的两个位置（settings_page.py:59 和 transcriber.py:350）都已经使用 `from transcriber import ModelManager`。因此不需要保留兼容层，直接删除 `model_manager.py` 即可。

2. **构造函数签名不匹配**：如果做 shim，旧版 `model_manager.py` 的构造函数是 `__init__(self, cache_dir=None)`（可选参数，有默认值 `_get_default_cache_dir()`），而 `transcriber.ModelManager` 的构造函数是 `__init__(self, cache_dir)`（必需参数）。如果有代码调用 `ModelManager()` 不传参数，shim 会抛 TypeError。虽然当前没有这样的调用，但 shim 作为"兼容层"应该处理这种差异。

3. **路径构造方式不同**：旧版用 `model_info["name"].replace("/", "--")` 构造路径（如 `models_cache/iic--SenseVoiceSmall`），新版用 `os.path.join(cache_dir, "models", "iic", model_name)`（如 `models_cache/models/iic/SenseVoiceSmall`）。这是完全不同的目录结构，shim 无法透明兼容。

**[QW] 修改建议**：直接删除 `src/model_manager.py`，不做 shim。理由：
- 无调用方引用该文件
- 路径结构不兼容，shim 无法透明转发
- 保留死代码只增加维护负担
- 缺陷 5（fsmn-vad 缺失）随之自动消除，因为不再有旧版检查路径
-->

```python
# model_manager.py — 改为兼容 shim
from transcriber import ModelManager as _TranscriberModelManager

class ModelManager(_TranscriberModelManager):
    """兼容旧接口，实际使用 transcriber.ModelManager"""
    pass
```

**好处**：单一实现，维护一套检查逻辑。

---

### 修复 3：下载后增加完整性校验

**文件**：`src/transcriber.py`

**改动**：`download_model()` 下载完成后增加文件存在性和大小检查。

```python
def download_model(self, model_id, progress_callback=None):
    # ... 下载逻辑 ...

    # ── 新增：下载后校验 ──
    local_path = self._get_model_path(model_id)  # ← [QW] 此方法不存在！
    if not os.path.isdir(local_path):
        return False, f"下载失败：目录不存在 {local_path}"

    # 检查主权重文件
    config_file = os.path.join(local_path, "configuration.json")
    if os.path.isfile(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        weight_file = config.get("file_path_metas", {}).get("init_param", "model.pt")
        weight_path = os.path.join(local_path, weight_file)
        if not os.path.isfile(weight_path):
            return False, f"下载不完整：缺少权重文件 {weight_file}"
        if os.path.getsize(weight_path) < 1024:  # 小于 1KB 视为损坏
            return False, f"下载损坏：权重文件过小 ({os.path.getsize(weight_path)} bytes)"

    # 检查辅助文件
    aux_files = REQUIRED_AUX_FILES.get(model_id, [])
    for aux_file in aux_files:
        aux_path = os.path.join(local_path, aux_file)
        if not os.path.isfile(aux_path):
            return False, f"下载不完整：缺少辅助文件 {aux_file}"

    return True, f"{model_id} 下载完成且验证通过"
```

<!-- [QW] Fix 3 代码存在以下问题：

1. **`self._get_model_path(model_id)` 方法不存在**：`transcriber.ModelManager` 没有 `_get_model_path()` 方法。路径是在 `download_model()` 内部用 3 行代码计算的（line 205-207）：
   ```python
   parts = ms_id.split("/")
   model_name = parts[-1] if len(parts) >= 2 else ms_id
   local_path = os.path.join(self.cache_dir, "models", "iic", model_name)
   ```
   建议将路径计算提取为 `_get_model_path(model_id)` 辅助方法，或在 Fix 3 的校验代码中直接使用上面的内联计算。

2. **与缺陷 6 的关系**：Fix 3 的下载后校验逻辑本身是正确的，但需要同步修复缺陷 6（line 208 的空目录假阳性），否则校验代码永远不会被执行到。

3. **建议执行顺序**：先修复缺陷 6（去掉空目录短路返回），再添加 Fix 3 的下载后校验。
-->

---

### 修复 4：增加文件大小校验

**文件**：`src/transcriber.py`

**改动**：在 `REQUIRED_MODELS` 中增加每个模型的预期大小范围。

```python
REQUIRED_MODELS = {
    "SenseVoiceSmall": {
        ...
        "min_size_mb": 800,  # 主权重至少 800MB
    },
    "fsmn-vad": {
        ...
        "min_size_mb": 1,
    },
    "ct-punc": {
        ...
        "min_size_mb": 1000,
    },
    "cam++": {
        ...
        "min_size_mb": 20,
    },
}
```

在 `check_all_models()` 中：
```python
min_size = info.get("min_size_mb", 0) * 1024 * 1024
if has_weights and min_size > 0:
    actual_size = os.path.getsize(os.path.join(local_path, weight_file))
    if actual_size < min_size:
        cached = False  # 文件过小，视为不完整
```

---

### 修复 5：清理旧版 ModelManager

**文件**：`src/model_manager.py`

**方案**：~~将 `model_manager.py` 改为兼容 shim，内部使用 `transcriber.ModelManager`。~~

<!-- [QW] 与 Fix 2 重复，且方案应改为直接删除。理由同 Fix 2 审查意见：无调用方引用、路径结构不兼容、保留死代码无意义。

**[QW] 修改后的方案**：
```bash
# 直接删除文件
git rm src/model_manager.py
```
删除后：
- 缺陷 2（双实现不一致）自动消除
- 缺陷 5（fsmn-vad 缺失）自动消除
- 无需维护兼容层
-->

```python
"""
模型管理器（兼容层）
实际实现在 transcriber.py，此处仅保留旧接口兼容
"""
import logging
from transcriber import ModelManager

logger = logging.getLogger("MeetScribe")
logger.debug("model_manager.py: 使用 transcriber.ModelManager")
```

同时确保 `REQUIRED_MODELS` 包含 fsmn-vad（已在 transcriber.py 中定义）。

---

## 三、改动汇总

| 编号 | 修复 | 文件 | 改动量 | 风险 |
|------|------|------|--------|------|
| F-1 | 辅助文件检查 | transcriber.py | ~20行 | 低：纯增量逻辑 |
| ~~F-2~~ | ~~统一 ModelManager（shim）~~ | ~~model_manager.py~~ | ~~~~ | ~~[QW] 改为直接删除文件~~ |
| F-3 | 下载完整性校验 | transcriber.py | ~30行 | 低：下载后校验（需修正 _get_model_path） |
| F-4 | 文件大小校验 | transcriber.py | ~15行 | 低：增量判断 |
| ~~F-5~~ | ~~清理旧版（shim）~~ | ~~model_manager.py~~ | ~~~~ | ~~[QW] 与 F-2 合并，直接删除~~ |
| **F-6** | **修复空目录假阳性** | **transcriber.py** | **~5行** | **[QW 新增] 低：去掉短路返回** |

---

## 四、验证方法

修复后运行以下验证：

```bash
# 1. 单元测试
pytest tests/test_tdd_flows.py -v -k "test_audio_files_valid"

# 2. 模型检查验证（应显示所有模型已缓存）
python -c "
from transcriber import ModelManager
from gui.styles import MODEL_CACHE_DIR
mm = ModelManager(MODEL_CACHE_DIR)
status = mm.check_all_models()
for k, v in status.items():
    print(f'{k}: cached={v[\"cached\"]}, aux_missing={v.get(\"aux_missing\", [])}')
"

# 3. 转写端到端验证
pytest tests/test_tdd_flows.py::TestTranscriptionWithRealAudio::test_transcription_16min -v --timeout=300 -s
```

---

## 五、注意事项

1. ~~**向后兼容**：`model_manager.py` 改为 shim 后，现有 `from model_manager import ModelManager` 的代码无需修改~~ <!-- [QW] 此条不成立。没有代码引用 model_manager.py，直接删除即可，无兼容性问题 -->
2. **测试覆盖**：需要补充模型检查的单元测试（mock 文件系统）
3. **下载重试**：F-3 的完整性校验失败后，应允许用户重新下载（当前已有此交互）
4. **fsmn-vad 已在 REQUIRED_MODELS 中**：transcriber.py:51-56 已定义，无需额外添加

---

## 六、QoderWork 审查汇总

> 审查日期：2026-06-16
> 审查方式：逐项对照源代码（transcriber.py、model_manager.py、settings_page.py、app.py）+ 全项目 grep 验证

### 审查发现

| 编号 | 类型 | 位置 | 发现 | 严重性 |
|------|------|------|------|--------|
| QW-1 | 事实错误 | 缺陷 2 描述 | `app.py` 引用 `model_manager.py` 不成立，grep 确认 0 条匹配 | 中：导致修复方案方向偏差 |
| QW-2 | 方案缺陷 | Fix 2 / Fix 5 | shim 不必要且不可行：无调用方、构造函数签名不同、路径结构不兼容 | 高：应改为直接删除 |
| QW-3 | 代码错误 | Fix 3 第 165 行 | `self._get_model_path(model_id)` 方法在 `transcriber.ModelManager` 中不存在 | 高：代码无法运行 |
| QW-4 | 遗漏缺陷 | download_model() | 缺陷 6：line 208-209 空目录短路返回，导致中断后无法重新下载 | 高：P1 级缺陷 |
| QW-5 | 冗余 | Fix 2 与 Fix 5 | 两个修复处理同一文件，方案重叠 | 低：合并即可 |

### 建议修改后的修复计划

| 优先级 | 修复 | 说明 |
|--------|------|------|
| 1 | **F-6（新增）** | 修复 `download_model()` 空目录假阳性，将 `os.path.isdir()` 短路返回改为完整性检查 |
| 2 | **F-1** | 增强 `check_all_models()` 辅助文件检查（原方案可用） |
| 3 | **F-3（修正）** | 下载后校验，需提取 `_get_model_path()` 辅助方法或使用内联路径计算 |
| 4 | **F-4** | `REQUIRED_MODELS` 增加 `min_size_mb`（原方案可用） |
| 5 | **F-2/F-5（合并）** | 直接删除 `src/model_manager.py`，不做 shim |
