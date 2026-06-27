# 测试方法论

> 创建日期：2026-06-26
> 目的：建立高效测试流程，减少手动测试负担

## 设计原则

1. **自动化优先**：能自动化的测试绝不手动
2. **分层测试**：单元测试 → 集成测试 → 端到端测试
3. **快速反馈**：开发模式下秒级反馈，打包前全面验证
4. **按需执行**：不同改动跑不同级别的测试

---

## 测试分层

### 第一层：单元测试（秒级）

**触发条件**：修改单个模块的内部逻辑
**运行命令**：
```bash
# 只跑相关模块的测试
pytest tests/test_<module>.py -v

# 例：修改 config.py 后
pytest tests/test_config.py -v
```

**覆盖范围**：
- 函数输入输出
- 边界条件
- 错误处理

### 第二层：集成测试（分钟级）

**触发条件**：修改模块间交互
**运行命令**：
```bash
# 跑相关模块组合的测试
pytest tests/test_config.py tests/test_file_manager.py -v
```

**覆盖范围**：
- 模块间数据传递
- 配置加载与保存
- 文件读写流程

### 第三层：全量测试（5-10分钟）

**触发条件**：
- 打包前
- 大规模重构后
- 修复多个模块后

**运行命令**：
```bash
pytest tests/ -v --timeout=60
```

### 第四层：打包验证（15-20分钟）

**触发条件**：准备发布安装包
**运行内容**：
1. PyInstaller 打包
2. ISCC 编译安装包
3. 安装到 Program Files 测试
4. 首次启动测试

---

## 测试文件命名规范

```
test_<module>_<scope>.py

scope 说明：
- 无后缀：基础功能测试
- _p0：P0 关键路径测试
- _e2e：端到端流程测试
- _gui：GUI 相关测试
```

**示例**：
- `test_config.py` - 配置模块基础测试
- `test_transcription_p0.py` - 转写关键路径测试
- `test_voiceprint_e2e.py` - 声纹端到端测试

---

## 测试检查清单

### 修改代码后
- [ ] 运行相关模块的单元测试
- [ ] 检查是否有 import 错误
- [ ] 验证 get_data_dir() 路径正确

### 打包前
- [ ] 运行全量测试
- [ ] 确认 me.spec 指向正确目录
- [ ] 确认所有 __file__ 路径已修复
- [ ] 确认图标已更新

### 安装测试
- [ ] 安装到 Program Files
- [ ] 首次启动不报错
- [ ] 日志写入正常
- [ ] 配置保存正常
- [ ] 录音功能正常
- [ ] 转写功能正常
- [ ] 音色库保存正常

---

## 快速诊断流程

### 问题：启动报 PermissionError
```bash
# 检查哪些文件还在用 __file__ 写入
grep -r "os.path.dirname.*__file__" src/ --include="*.py"
# 确认是否都已改用 get_data_dir()
grep -r "get_data_dir" src/ --include="*.py"
```

### 问题：配置文件找不到
```bash
# 检查 get_data_dir() 返回值
python -c "from utils import get_data_dir; print(get_data_dir())"
# 检查 config 目录是否存在
ls $(python -c "from utils import get_data_dir; print(get_data_dir())")/config/
```

### 问题：模型加载失败
```bash
# 检查 MODEL_CACHE_DIR
python -c "from gui.styles import MODEL_CACHE_DIR; print(MODEL_CACHE_DIR)"
# 检查模型目录
ls $(python -c "from gui.styles import MODEL_CACHE_DIR; print(MODEL_CACHE_DIR)")
```

---

## 测试覆盖率目标

| 模块 | 目标覆盖率 | 优先级 |
|------|-----------|--------|
| config.py | 90% | P0 |
| file_manager.py | 85% | P0 |
| voiceprint.py | 80% | P1 |
| gui/app.py | 70% | P1 |
| transcribe_worker.py | 75% | P1 |

---

## 与手动测试的分工

| 测试类型 | 自动化 | 手动 |
|----------|--------|------|
| 单元测试 | ✅ | ❌ |
| 集成测试 | ✅ | ❌ |
| GUI 布局 | ❌ | ✅ |
| 用户体验 | ❌ | ✅ |
| 安装流程 | ❌ | ✅ |
| 跨版本兼容 | 部分 | ✅ |

---

## 持续改进

1. **每次发现 bug**：补充对应的测试用例
2. **每次修复问题**：记录到测试用例库
3. **每月回顾**：清理过时测试，补充缺失覆盖
