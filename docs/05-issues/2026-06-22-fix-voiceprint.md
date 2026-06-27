# 音色库页面布局修复指令 — MiMo Code

## 问题描述

音色库管理页面存在两个明显布局问题：

1. **左侧说话人列表项过于拥挤**：6 个条目紧贴在一起，几乎没有行间距
2. **右侧声纹样本垂直居中**：样本行在卡片中居中显示，应该紧贴卡片顶部

## 修复文件

`src/gui/voiceprint_page.py`

## 修复项（共 5 处）

### FIX-V1：说话人列表项固定高度 52px

**行号**：约第 565-566 行

```python
# 改前
list_item = QListWidgetItem()
list_item.setSizeHint(item_widget.sizeHint())

# 改后
list_item = QListWidgetItem()
list_item.setSizeHint(QSize(0, 52))  # 固定 52px 高度（32px 头像 + 20px padding）
```

### FIX-V2：添加 QSize 到 import

**行号**：约第 19 行

```python
# 改前
from PySide6.QtCore import Qt, Signal, QTimer, QThread

# 改后
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QSize
```

### FIX-V3：增加 item_widget 上下边距

**行号**：约第 538 行

```python
# 改前
item_layout.setContentsMargins(10, 8, 10, 8)

# 改后
item_layout.setContentsMargins(10, 10, 10, 10)
```

### FIX-V4：样本卡片去掉 stretch factor（最关键修复）

**行号**：约第 727 行

```python
# 改前
self._detail_layout.addWidget(samples_card, 1)

# 改后 — 去掉 stretch=1，让卡片保持自然高度
self._detail_layout.addWidget(samples_card)
```

### FIX-V5：添加 C_WARN 到 import

**行号**：约第 23 行

```python
# 改前
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR, C_TXT1, C_TXT2, C_TXT3, C_PURPLE,
    FONT_FAMILY, SPEAKER_COLORS, DEFAULT_SPK_QUALITY,
)

# 改后 — 添加 C_WARN
from gui.styles import (
    C_BG, C_CARD, C_BORDER, C_ACCENT, C_ACCENT_LT, C_BTN_HOVER,
    C_SUCCESS, C_ERROR, C_WARN, C_TXT1, C_TXT2, C_TXT3, C_PURPLE,
    FONT_FAMILY, SPEAKER_COLORS, DEFAULT_SPK_QUALITY,
)
```

> 注：C_WARN 在第 712 行使用但未导入，打开含低于 0.8 质量样本的说话人详情时会触发 NameError。

## 验证

修改后运行程序确认：
1. 左侧说话人列表每行有清晰间距，不拥挤
2. 右侧声纹样本卡片高度仅包裹内容，样本行紧贴卡片顶部
3. 打开不同说话人详情，卡片不出现大面积灰色空白
