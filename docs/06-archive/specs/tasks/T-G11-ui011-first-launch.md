# T-G11 — 首次启动引导真实化

- **Tier**: 2
- **关联需求**: UI-011（首次启动引导）
- **依赖**: 无
- **预估**: 1 天

## 背景
spec 要求首次启动"引导安装 VB-Audio Cable、配置 API Key"。
当前 `src/gui/first_launch.py:65-269 FirstLaunchDialog`：
- 只引导"模型下载"，且下载是 `time.sleep` **模拟**（`:52-57`），并非真实下载；
- **不引导 VB-Audio Cable 安装**，**不引导 API Key 配置**。
即当前是一个功能 stub。

## Scope
1. 首次启动引导改为多步向导，至少包含：
   - 模型检查/下载（接 `ModelManager.download_all_missing` 真实下载 + 进度回调，替换 `time.sleep` 模拟）。
   - VB-Audio Cable 检测与安装指引（检测是否已安装；未装则给出下载链接/说明）。
   - API Key 配置入口（可填入并保存，或跳过）。
2. 引导完成后正确置位 `first_launch=false`，下次不再弹出。
3. 每步可跳过；跳过不阻塞进入主界面。

## Out of Scope
- VB-Cable 的静默自动安装（仅需检测 + 指引，安装由用户完成）。
- 模型下载的断点续传（用 ModelManager 现有能力即可）。

## Success Criteria
- [ ] 首次启动向导包含"模型 / VB-Cable / API Key"三步（或合理合并），且模型下载调用**真实** `ModelManager`，不再有 `time.sleep` 模拟下载。
- [ ] VB-Cable 步骤能反映真实安装状态（已装/未装），未装时显示获取指引。
- [ ] API Key 步骤填写后写入 config，可被设置页读到。
- [ ] 完成或跳过后 `first_launch=false`，重启不再弹出。
- [ ] 集成测试 `tests/test_first_launch.py`（qtbot，mock ModelManager / VB 检测，不需真实下载）覆盖三步流程与跳过路径。

## Verification
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_first_launch.py -q
```
