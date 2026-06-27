# 临时文件清理方案

> 日期：2026-06-26
> 状态：待执行

---

## 当前磁盘占用

| 目录 | 文件数 | 大小 | .gitignore | 说明 |
|------|--------|------|------------|------|
| `recordings/` | 40 | ~2.7 GB | YES | 用户录音文件 |
| `models_cache/` | 58 | ~2.0 GB | YES | FunASR 模型缓存 |
| `__pycache__/` (3处) | 82 | ~1.8 MB | YES | Python 字节码 |
| `logs/` | 2 | ~9.6 MB | YES | 运行日志 |
| `.pytest_cache/` | - | ~54 KB | YES | pytest 缓存 |
| `transcripts/` | 73 | ~1.7 MB | YES | 转写结果 |
| `dist/` | 0 | - | NO | PyInstaller 输出（尚未生成） |
| `build/` | 0 | - | NO | PyInstaller 中间文件（尚未生成） |
| `installer_output/` | 0 | - | NO | Inno Setup 输出（尚未生成） |

## .gitignore 覆盖情况

已覆盖：`__pycache__/`、`*.py[cod]`、`.pytest_cache/`、`logs/`、`recordings/`、`transcripts/`、`models_cache/`、`data/`、`.env`、`.venv/`、`venv/`、`.mimocode/`、`config/settings.json`

**缺失**：`dist/`、`build/`、`installer_output/`

## 评估

1. **无构建产物需清理**：dist/、build/、installer_output/ 尚不存在，打包后才会生成
2. **__pycache__ 已 gitignore**：1.8MB 不影响版本控制，但可定期清理
3. **大目录均为运行时数据**：recordings (2.7GB) 和 models_cache (2.0GB) 是用户数据和模型，不应删除
4. **.gitignore 有缺口**：需要补充 dist/、build/、installer_output/ 规则

## 执行方案

### 第一步：补充 .gitignore（立即执行）

在 `.gitignore` 中添加：

```
dist/
build/
installer_output/
```

### 第二步：清理 __pycache__（可选）

```bash
# 删除所有 __pycache__ 目录
Get-ChildItem -Path "C:\侧耳倾听" -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
```

释放空间：~1.8 MB

### 第三步：清理 .pytest_cache（可选）

```bash
Remove-Item -Path "C:\侧耳倾听\.pytest_cache" -Recurse -Force
```

释放空间：~54 KB

## 注意事项

- `recordings/` 和 `models_cache/` 不要清理，是用户数据
- `logs/` 可以定期清理，但不是必须的
- 打包前不需要清理，PyInstaller 会自己管理 dist/ 和 build/

---

## Qoder 审查结果

> 审查日期：2026-06-26
> 审查方法：核实 .gitignore 内容、实际目录文件数和大小

### 数据核实

| 项目 | 方案数据 | 实际数据 | 结论 |
|------|---------|---------|------|
| recordings/ | 40 文件, ~2.7 GB | 40 文件, 2762.9 MB | 正确 |
| models_cache/ | 58 文件, ~2.0 GB | 58 文件, 2059.6 MB | 正确 |
| __pycache__/ | 82 文件, ~1.8 MB | 85 文件, 1822 KB | 基本正确 |
| logs/ | 2 文件, ~9.6 MB | 2 文件, 9.6 MB | 正确 |
| transcripts/ | 73 文件, ~1.7 MB | 73 文件, 1.6 MB | 正确 |
| dist/build/installer_output/ | 不存在 | 不存在 | 正确 |
| .gitignore 缺失 | dist/ build/ installer_output/ | 确认缺失 | 正确 |

### 对执行方案的意见

**第一步：补充 .gitignore — 同意，立即执行**

方案正确。建议在 `.gitignore` 末尾添加以下内容。同时建议补充两条常见构建产物规则：

```
# Build outputs
dist/
build/
build_spec/
installer_output/

# PyInstaller
*.manifest
*.spec.bak
```

注：`build_spec/` 是项目 README 中 PyInstaller 打包命令使用的 `--workpath` 目录，也应加入 gitignore。`*.manifest` 和 `*.spec.bak` 是 PyInstaller 可能生成的中间文件。

**第二步：清理 __pycache__ — 同意，可选**

方案正确。1.8 MB 不大，但清理掉也无妨。补充：可以在 `.gitignore` 已有的基础上不需要手动清理，git 不会跟踪这些文件。

**第三步：清理 .pytest_cache — 同意，可选**

方案正确。54 KB 可忽略。

### 补充建议

1. **`scripts/` 目录**：mimo 在测试质量 v3 方案中把 `test_voiceprint_threshold.py` 移到 `scripts/`，这个清理方案里没提到。建议在脚本完成后确认 `scripts/` 目录结构。

2. **`venv_build/` 目录**：README 打包命令中使用了 `venv_build` 虚拟环境，但 `.gitignore` 中只列了 `.venv/` 和 `venv/`，建议补充 `venv_build/`。

3. **打包后清理**：方案说"打包前不需要清理"是对的，但建议补充一条：打包完成后如果 `dist/` 和 `build/` 占用过大（通常 500MB-1GB），可以手动清理释放磁盘空间。

### 结论

方案判断准确，数据核实无误，执行步骤合理。可以直接执行第一步（补 .gitignore），其余可选。
