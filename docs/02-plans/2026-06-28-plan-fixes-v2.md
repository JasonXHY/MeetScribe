# 安装后问题修复方案 v2

> 日期：2026-06-28
> 状态：待用户确认后执行
> 背景：第 3 次打包安装后发现多个问题

---

## 一、问题清单

| # | 问题 | 严重度 | 根因 |
|---|------|--------|------|
| 1 | VB-Cable 静默安装无效，弹窗+网页跳转 | 高 | VB-Cable 不是 Inno Setup 安装程序，`/VERYSILENT` 无效 |
| 2 | 转写失败（Permission denied） | 高 | 模型状态文件写入 Program Files 需管理员权限 |
| 3 | 转写失败（Missing funasr version.txt） | 高 | PyInstaller 漏打包 funasr 版本文件 |
| 4 | UI 按钮样式与源码不一致 | 中 | 待确认：可能是 PyInstaller 缓存旧 .pyc 文件 |
| 5 | 图标问题 | 已验证 | 测试快捷方式图标正确，已安装版本需重建快捷方式 |

---

## 二、逐个分析

### 问题 1：VB-Cable 静默安装

**事实**：
- VB-Cable 的 `VBCABLE_Setup_x64.exe` **不是 Inno Setup 安装程序**
- `/VERYSILENT` 是 Inno Setup 参数，对 VB-Cable 无效
- VB-Cable readme 写明："Run Setup Program in administrator mode"
- 安装完成后会自动打开捐赠页面（Donationware 行为）

**解决方案**：

方案 A：接受手动安装（推荐）
- 移除 installer.iss 中的 VB-Cable 自动安装
- 在首次启动对话框中添加提示："推荐安装 VB-Audio Cable 以获得更好的录音体验"
- 提供 VB-Cable 下载链接
- 用户手动下载安装（~1MB，30 秒）

方案 B：研究 VB-Cable 的静默安装方式
- 需要逆向分析 VB-Cable 安装程序
- 风险：可能没有静默安装方式

**建议**：选方案 A，简单可靠。

### 问题 2：Permission denied

**事实**（从日志）：
```
Permission denied: 'C:\Program Files\MeetScribe\models\model_status.json'
```

**根因**：Program Files 目录需要管理员权限写入。ModelManager 尝试写入 `model_status.json` 到模型目录。

**解决方案**：

方案 A（推荐）：将模型安装到 AppData 目录
- 模型复制到 `%LOCALAPPDATA%\MeetScribe\models\` 而非 `{app}\models\`
- 这是 Windows 应用的标准做法（Chrome、VS Code 等都用 AppData）
- 用户数据和应用分离，便于更新和卸载

方案 B：安装时设置目录权限
- Inno Setup 可以设置目录权限，但不推荐

### 问题 3：Missing funasr version.txt

**事实**（从日志）：
```
Failed to patch campplus utils: No such file or directory: 'C:\Program Files\MeetScribe\_internal\funasr\version.txt'
```

**根因**：PyInstaller 没有打包 `funasr/version.txt` 文件。

**解决方案**：
- 在 me.spec 的 datas 中添加 funasr 版本文件
- 或修改代码使其在文件不存在时不报错

### 问题 4：UI 样式差异

**事实**：
- 用户报告从源码运行和安装版本的 UI 有细微差异
- 特别是录音按钮那一行

**可能原因**：
1. PyInstaller 使用了缓存的旧 .pyc 文件
2. 字体渲染差异（安装环境 vs 开发环境）
3. Qt 样式表加载顺序不同

**验证方法**：
- 对比源码和 dist 中的 styles.py 内容（需要反编译 .pyc）
- 或直接在安装目录运行 Python 脚本验证

**解决方案**：
- 完全清理 build 目录后重新打包
- 确保 PyInstaller 不使用缓存

### 问题 5：图标

**已验证**：
- 源码 `assets/logo.ico` 与旧版一致（95871 字节）
- 创建的测试快捷方式图标正确
- 已安装版本的快捷方式可能缓存了旧图标

**解决方案**：
- 删除桌面旧快捷方式
- 重新安装后会创建新快捷方式
- 或手动重建快捷方式

---

## 三、执行计划

### 第一步：修复模型安装路径（关键）

将模型从 `{app}/models/` 改为 `%LOCALAPPDATA%/MeetScribe/models/`：

1. 修改 `installer.iss`：模型复制到 `{userappdata}\MeetScribe\models\`
2. 修改 `transcriber.py`：`_get_model_dir()` frozen 模式返回 `%LOCALAPPDATA%/MeetScribe/models`
3. 修改 `styles.py`：`MODEL_CACHE_DIR` frozen 模式返回 `%LOCALAPPDATA%/MeetScribe/models`
4. 修改 `first_launch.py`：`_check_models_packaged()` 检查 AppData 目录

### 第二步：移除 VB-Cable 自动安装

1. 修改 `installer.iss`：移除 VB-Cable 相关的 [Files] 和 [Run] 段
2. 修改 `first_launch.py`：添加 VB-Cable 安装提示页面
3. 修改 `config.py`：`use_vb_cable` 默认改为 `False`

### 第三步：修复 funasr version.txt

1. 检查 funasr 包中 version.txt 的位置
2. 在 me.spec 的 datas 中添加该文件
3. 或修改代码使其容错

### 第四步：清理并重新打包

1. 完全删除 build/ 和 dist/ 目录
2. 重新运行 PyInstaller
3. 重新运行 Inno Setup
4. 测试安装

---

## 四、待确认

1. **模型路径**：你希望模型安装到哪里？
   - A. `%LOCALAPPDATA%/MeetScribe/models/`（推荐，标准做法）
   - B. `{app}/models/`（当前方案，有权限问题）

2. **VB-Cable**：你希望怎么处理？
   - A. 移除自动安装，改为提示用户手动安装（推荐）
   - B. 继续尝试自动安装（需要逆向分析）

3. **UI 差异**：你能具体描述哪里不同吗？（按钮大小？颜色？文字？）
