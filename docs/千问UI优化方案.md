# 侧耳倾听 UI 优化方案 — 字段级修复指南

> 日期：2026-06-12
> 对比基准：`C:\MeetScribe\src\gui\`（原版 customtkinter v3.3）
> 审查人：QoderWork
> 文档用途：逐字段指导 PySide6 新版的 UI 样式修正，使视觉效果达到或超过原版水平
> 协作分工：QoderWork 写方案 → MiMo/千问 Code 实施 → 用户测试验收

---

## 〇、问题总览与修复策略

### 根因分析

当前 UI "丑"的根因不是颜色不好看（两版色板完全一致），而是 **PySide6 迁移过程中的样式还原遗漏**。具体表现为：

1. **交互反馈缺失**：按钮 hover/pressed 效果在 customtkinter 中是内建的，迁移到 QPushButton 后需要手动写 QSS `:hover` / `:pressed` 伪状态，但大量按钮遗漏了
2. **下拉控件失去辨识度**：CTkOptionMenu 有蓝色下拉箭头按钮，QComboBox 的 `::drop-down` 被设为 `border: none` 后完全看不出是下拉框
3. **全局 QSS 副作用**：`QFrame { border: 1px solid; border-radius: 8px }` 这条全局规则导致所有嵌套 QFrame 都出现意外的双重边框
4. **布局参数硬编码**：styles.py 定义了完整的设计 token（`FONT_SIZE_*`, `SPACING_*`, `BTN_SIZE_*`），但实际代码中全部硬编码数值，未引用常量
5. **功能降级**：部分控件从丰富的 customtkinter 控件（CTkSwitch、CTkOptionMenu）降级为基础 Qt 控件（QCheckBox、QComboBox），交互体验下降

### 修复优先级

| 优先级 | 问题数 | 预估工时 | 说明 |
|--------|--------|----------|------|
| **P0 全局样式系统** | 5 项 | 1.5h | 修复影响所有页面的样式根因 |
| **P1 各页面布局还原** | 25 项 | 3-4h | 逐页面还原原版视觉效果 |
| **P2 功能补全** | 8 项 | 1-2天 | 补回缺失的控件和功能 |

---

## 一、P0：全局样式系统修复（`src/gui/styles.py`）

### FIX-01：修复全局 QFrame 边框副作用

**问题**：`MAIN_STYLESHEET` 第 139-142 行对 `QFrame` 设了默认 `border: 1px solid {C_BORDER}; border-radius: 8px`。这导致所有嵌套的 QFrame（包括分隔线、行容器、按钮容器）都出现意外的边框和圆角。

**修改位置**：`styles.py` 第 137-142 行

**原代码**：
```css
QFrame {
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}
```

**改为**：
```css
/* 只有顶层卡片容器才有边框，嵌套 QFrame 默认无框 */
QFrame.card {
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}
QFrame {
    background-color: transparent;
    border: none;
}
```

**配合修改**：所有创建卡片容器的代码中需要加 `card.setProperty("class", "card")`，或改用更精确的选择器。

**影响范围**：所有页面（主页、设置页、音色库页、所有对话框）

---

### FIX-02：补全按钮 hover + pressed 效果

**问题**：全局 QSS 的 `QPushButton:hover` 只设了 `background-color: {C_ACCENT_LT}`（浅蓝），但主色按钮（蓝色背景）悬停时应该变为更深的蓝色（`C_BTN_HOVER`），而非浅蓝。且所有按钮缺少 `:pressed` 效果。

**修改位置**：`styles.py` 全局 QSS QPushButton 段落

**原代码**（第 144-173 行）：
```css
QPushButton {
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
    color: {C_TXT1};
}
QPushButton:hover {
    background-color: {C_ACCENT_LT};
}
QPushButton:disabled {
    color: {C_TXT3};
    border-color: {C_TXT3};
}
QPushButton[cssClass="primary"] {
    background-color: {C_ERROR};
    color: white;
    border: none;
}
QPushButton[cssClass="primary"]:hover {
    background-color: #A52318;
}
```

**改为**：
```css
/* 普通按钮（透明边框风格） */
QPushButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: {BTN_RADIUS}px;
    padding: 6px 12px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_BODY}px;
    color: {C_TXT1};
}}
QPushButton:hover {{
    background-color: #F5F5F5;
    border-color: #D0D0D0;
}}
QPushButton:pressed {{
    background-color: #EBEBEB;
}}
QPushButton:disabled {{
    color: {C_TXT3};
    border-color: #D0D0D0;
    background-color: #F8F8F8;
}}

/* 主操作按钮（蓝色实心） */
QPushButton.btn-primary {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton.btn-primary:hover {{
    background-color: {C_BTN_HOVER};
}}
QPushButton.btn-primary:pressed {{
    background-color: #004E8C;
}}
QPushButton.btn-primary:disabled {{
    background-color: {C_TXT3};
    color: #E0E0E0;
}}

/* 危险按钮（红色，用于录音/停止） */
QPushButton.btn-danger {{
    background-color: {C_ERROR};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton.btn-danger:hover {{
    background-color: #A52318;
}}
QPushButton.btn-danger:pressed {{
    background-color: #8C1B14;
}}

/* 成功按钮（绿色，用于开始转写） */
QPushButton.btn-success {{
    background-color: {C_SUCCESS};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton.btn-success:hover {{
    background-color: #0A5E0A;
}}
QPushButton.btn-success:pressed {{
    background-color: #084D08;
}}

/* 幽灵按钮（透明 + 边框，用于次要操作） */
QPushButton.btn-ghost {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    color: {C_TXT1};
}}
QPushButton.btn-ghost:hover {{
    background-color: #F5F5F5;
}}
QPushButton.btn-ghost:pressed {{
    background-color: #EBEBEB;
}}
```

**使用方式**：代码中用 `btn.setProperty("class", "btn-primary")` 代替内联 setStyleSheet。

---

### FIX-03：修复 QComboBox 下拉箭头缺失

**问题**：`::drop-down { border: none }` 把下拉箭头完全移除，用户看不出这是下拉控件。

**修改位置**：`styles.py` 全局 QSS QComboBox 段落（第 196-214 行）

**原代码**：
```css
QComboBox::drop-down {
    border: none;
}
```

**改为**：
```css
QComboBox {{
    border: 1px solid {C_BORDER};
    border-radius: {BTN_RADIUS}px;
    padding: 4px 28px 4px 8px;  /* 右侧留出箭头空间 */
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_BODY}px;
    background-color: {C_BG};
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: {C_ACCENT};
    background-color: #EDEDED;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {C_BORDER};
    border-top-right-radius: {BTN_RADIUS}px;
    border-bottom-right-radius: {BTN_RADIUS}px;
    background-color: #E8E8E8;
}}
QComboBox::drop-down:hover {{
    background-color: {C_ACCENT_LT};
}}
QComboBox::down-arrow {{
    image: none;  /* 不用图片，用 border 技巧画三角 */
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C_TXT2};
    width: 0;
    height: 0;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    border: 1px solid {C_BORDER};
    selection-background-color: {C_ACCENT_LT};
    selection-color: {C_TXT1};
    outline: none;
    padding: 2px;
}}
```

---

### FIX-04：统一 QCheckBox 为更美观的开关样式

**问题**：原版 customtkinter 的 CTkCheckBox 有圆角方框 + 勾选动画效果。新版 QCheckBox 的全局样式过于基础。

**修改位置**：`styles.py` 全局 QSS QCheckBox 段落（第 250-266 行）

**改为**：
```css
QCheckBox {{
    spacing: 8px;
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_BODY}px;
    color: {C_TXT1};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {C_BORDER};
    border-radius: 4px;
    background-color: white;
}}
QCheckBox::indicator:hover {{
    border-color: {C_ACCENT};
}}
QCheckBox::indicator:checked {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
    image: none;  /* 可后续添加勾选 SVG 图标 */
}}
QCheckBox::indicator:checked:hover {{
    background-color: {C_BTN_HOVER};
    border-color: {C_BTN_HOVER};
}}
```

---

### FIX-05：让 styles.py 的常量真正被代码引用

**问题**：`FONT_SIZE_PAGE_TITLE=22`、`SPACING_CARD_PADDING=14`、`BTN_SIZE_PRIMARY=(90,32)` 等常量定义了但代码中全部硬编码数值。

**方案**：本次不强制全部替换，但在修复上述问题时，新写的代码应引用常量。后续可以逐步替换硬编码。

---

## 二、P1：各页面布局还原

### 2.1 设置页（`settings_page.py`）

#### FIX-06：Section 标题位置 — 从卡片内移到卡片外

**问题**：原版 section 标题（"存储路径"、"转写引擎"等）在卡片**上方/外部**，新版标题在卡片**内部**（被卡片边框包裹）。

**修改位置**：`_create_group()` 方法

**当前代码结构**：
```python
def _create_group(self, parent, title):
    card = QFrame(parent)
    card.setStyleSheet(f"... border: 1px solid {C_BORDER}; border-radius: 8px; ...")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 12, 16, 12)
    # 标题在 card 内部
    title_lbl = QLabel(title)
    card_layout.addWidget(title_lbl)
    return card, card_layout
```

**改为**：
```python
def _create_group(self, parent, title):
    # 容器 widget（无边框，只负责布局）
    container = QWidget(parent)
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(4)  # 标题与卡片间距 4px

    # 标题在卡片外部
    title_lbl = QLabel(f"  {title}")  # 前导空格模拟缩进
    title_lbl.setStyleSheet(f"""
        font-size: {FONT_SIZE_SECTION_TITLE}px;
        font-weight: bold;
        color: {C_TXT1};
        background: transparent;
        border: none;
    """)
    container_layout.addWidget(title_lbl)

    # 卡片在标题下方
    card = QFrame(container)
    card.setProperty("class", "card")
    card.setStyleSheet(f"""
        QFrame.card {{
            background-color: {C_CARD};
            border: 1px solid {C_BORDER};
            border-radius: {SPACING_CARD_RADIUS}px;
        }}
    """)
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(SPACING_CARD_PADDING, 12, SPACING_CARD_PADDING, 12)
    card_layout.setSpacing(8)
    container_layout.addWidget(card)

    return container, card_layout
```

---

#### FIX-07：输入框宽度 — 从固定 300px 改为自适应填充

**问题**：`_create_path_row` 中 QLineEdit 设了 `setFixedWidth(300)`，窗口拉宽时输入框不跟随。原版用 `pack(fill="x", expand=True)` 自适应。

**修改位置**：`_create_path_row()` 方法

**当前代码**：
```python
entry = QLineEdit(row)
entry.setFixedWidth(300)
```

**改为**：
```python
entry = QLineEdit(row)
# 不设 fixedWidth，让 QHBoxLayout 的 stretch 因子控制
```

同时修改 row 的 QHBoxLayout，给 entry 加 stretch：
```python
row.addWidget(label)
row.addWidget(entry, 1)  # stretch=1，填充剩余空间
row.addWidget(browse_btn)
```

**同步修改**：AI 服务区的 API Key 输入框也从 `setFixedWidth(300)` 改为 stretch 填充。

---

#### FIX-08：输入框背景色 — 从白色改为浅灰

**问题**：原版 CTkEntry 用 `fg_color=C_BG`（#F3F3F3 浅灰），新版 QLineEdit 全局 QSS 用白色背景。

**修改位置**：`styles.py` 全局 QSS QLineEdit 段落

**当前**：
```css
QLineEdit {
    background-color: white;
}
```

**改为**：
```css
QLineEdit {{
    background-color: {C_BG};
}}
```

---

#### FIX-09：保存按钮 — 左对齐 + primary 样式

**问题**：保存按钮在 QVBoxLayout 中默认居中，原版是 `pack(anchor="w")` 左对齐。

**修改位置**：`_build()` 方法中保存按钮的添加方式

**当前代码**：
```python
scroll_layout.addWidget(save_btn)
```

**改为**：
```python
# 用 QHBoxLayout 包裹，实现左对齐
btn_row = QHBoxLayout()
btn_row.setContentsMargins(0, 8, 0, 20)
btn_row.addWidget(save_btn)
btn_row.addStretch()
scroll_layout.addLayout(btn_row)
```

按钮样式改用 class 选择器：
```python
save_btn.setProperty("class", "btn-primary")
# 移除内联 setStyleSheet
```

---

#### FIX-10：检查模型按钮 — 恢复 primary（蓝色实心）样式

**问题**：原版"检查模型"按钮是蓝色实心主按钮（`fg_color=C_ACCENT`），新版变成了透明边框的 ghost 按钮。

**修改位置**：`_build_model_section()` 方法

**当前代码**：
```python
check_btn.setStyleSheet(f"""
    QPushButton {{
        background: transparent;
        color: {C_TXT2};
        border: 1px solid {C_BORDER};
        font-size: 11px;
        padding: 4px 8px;
        border-radius: 6px;
    }}
""")
```

**改为**：
```python
check_btn.setProperty("class", "btn-primary")
check_btn.setFixedSize(100, 32)
# 移除内联 setStyleSheet
```

---

#### FIX-11：补充所有控件的 hint 描述文本

**问题**：原版每个设置项下方都有灰色小字描述（如"Token Plan = 包月套餐，适合个人用户"），新版全部缺失。

**修复方式**：在每个控件行下方添加 hint QLabel：

```python
hint = QLabel("提示文字")
hint.setStyleSheet(f"""
    font-size: {FONT_SIZE_CAPTION}px;
    color: {C_TXT3};
    background: transparent;
    border: none;
""")
hint.setWordWrap(True)
# 用 indent spacer 对齐到控件左侧
hint_row = QHBoxLayout()
hint_row.addWidget(QLabel("  "))  # 缩进
hint_row.addWidget(hint)
card_layout.addLayout(hint_row)
```

需要补 hint 的控件：
- 录音目录："录音文件的默认保存位置"
- 转写目录："转写结果和 AI 摘要的输出位置"
- 转写模式："FunASR SenseVoice + CAM++ + ct-punc 本地推理"
- 启用 AI 摘要："转写完成后自动调用 MiMo 云端生成会议摘要"
- 启用 AI 纠错："转写完成后自动调用 LLM 修正识别错误"

---

#### FIX-12：关于区域 — 恢复结构化布局

**问题**：原版关于区域是 5 个独立 Label（标题加粗 + 4 行信息），新版是 1 个多行 QLabel（标题无加粗）。

**修改位置**：`_build_about_section()` 方法

改为与原版一致的结构：

```python
def _build_about_section(self, parent):
    container, card_layout = self._create_group(parent, "关于")
    about_f = QWidget()
    about_f.setStyleSheet("background: transparent; border: none;")
    about_layout = QVBoxLayout(about_f)
    about_layout.setContentsMargins(0, 0, 0, 0)
    about_layout.setSpacing(2)

    # 标题行（加粗）
    title = QLabel(f"{APP_NAME} v{APP_VERSION}  —  会议录音转写助手")
    title.setStyleSheet(f"""
        font-size: 13px; font-weight: bold;
        color: {C_TXT1}; background: transparent; border: none;
    """)
    about_layout.addWidget(title)

    # 制作者
    maker = QLabel("制作者：刘家诚")
    maker.setStyleSheet(f"font-size: 12px; color: {C_TXT2}; background: transparent; border: none;")
    about_layout.addWidget(maker)

    # 技术栈信息
    for line in [
        "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
        "AI: MiMo 云端 (摘要 / 纠错)",
        "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
    ]:
        lbl = QLabel(line)
        lbl.setStyleSheet(f"font-size: 12px; color: {C_TXT2}; background: transparent; border: none;")
        about_layout.addWidget(lbl)

    card_layout.addWidget(about_f)
    return container
```

---

### 2.2 主页（`home_page.py`）

#### FIX-13：录音栏双重边距修复

**问题**：RecordingBar 自身 `setContentsMargins(12, 8, 12, 8)` + 父容器 HomePage 的 `rec_layout.setContentsMargins(14, 8, 14, 8)` = 水平 26px 内边距。原版只有 14px。

**修改位置**：`recording_bar.py` 的 `_setup_ui()` 方法

**当前**：
```python
layout.setContentsMargins(12, 8, 12, 8)
```

**改为**：
```python
layout.setContentsMargins(0, 0, 0, 0)  # 让父容器统一控制边距
```

---

#### FIX-14：录音栏元素间距还原

**问题**：原版各元素间距不统一（通过不同 padx 精细控制：状态后 10px、模式后 10px、计时器后 12px、按钮后 6px），新版统一 spacing=8。

**修改位置**：`recording_bar.py` `_setup_ui()` 方法

**方案**：将 `setSpacing(8)` 改为 `setSpacing(0)`，在每个元素后手动 `addSpacing()`：

```python
layout.addWidget(status_dot)
layout.addSpacing(6)
layout.addWidget(status_label)
layout.addSpacing(10)
layout.addWidget(mode_combo)
layout.addSpacing(10)
layout.addWidget(mode_hint)
layout.addSpacing(12)  # 计时器前大间距
# ... 以此类推
```

---

#### FIX-15：文件卡片添加分隔线

**问题**：原版工具栏和文件列表之间有一条 1px 分隔线，新版缺失。

**修改位置**：`home_page.py` 的文件卡片构建方法

在工具栏和 FileListView 之间添加：
```python
separator = QFrame()
separator.setFixedHeight(1)
separator.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
file_layout.addWidget(separator)
```

---

#### FIX-16：日志区标题和清除按钮

**问题**：
- 标题从"运行日志"(12px bold) 变成了"日志"(11px bold)
- 缺少"清除"按钮

**修改位置**：`home_page.py` 日志区构建方法

**修改**：
```python
# 标题
log_title = QLabel("运行日志")
log_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {C_TXT1}; ...")

# 清除按钮
clear_btn = QPushButton("清除")
clear_btn.setFixedSize(50, 22)
clear_btn.setProperty("class", "btn-ghost")
clear_btn.setStyleSheet(f"""
    QPushButton {{
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        background: transparent;
        border: 1px solid {C_BORDER};
        color: {C_TXT2};
    }}
    QPushButton:hover {{ background: #F5F5F5; }}
""")
clear_btn.setCursor(Qt.PointingHandCursor)
clear_btn.clicked.connect(self._clear_log)
```

---

#### FIX-17：格式选择标签文字还原

**问题**：原版 `"输出格式"` + `C_TXT3`（灰色），新版 `"导出格式:"` + `C_TXT2`（深灰）。

**修改**：改回 `"输出格式"` 并使用 `C_TXT3` 颜色。

---

### 2.3 文件列表（`file_list_view.py`）

#### FIX-18：表头与数据行列对齐修复

**问题**：表头和数据行分别在不同的 QHBoxLayout 中，列宽可能偏差。原版用 grid 7 列严格对齐。

**方案**：使用 QGridLayout 替代 QHBoxLayout，表头和数据行共享同一套列宽配置。

**修改要点**：
1. 将 `_build_header()` 中的 `QHBoxLayout` 改为 `QGridLayout`
2. 设置列 stretch 因子：`(0, 1, 3, 1, 1, 1, 2)`（与原版 col_weights 一致）
3. 数据行也使用相同的 `QGridLayout` 和相同的列 stretch
4. 表头各列的对齐方式还原：队列/时长/大小/状态 → `Qt.AlignCenter`，文件名/主题 → `Qt.AlignLeft | Qt.AlignVCenter`

**关键代码**：
```python
# 表头 grid
header_grid = QGridLayout()
header_grid.setContentsMargins(8, 4, 8, 4)
header_grid.setHorizontalSpacing(0)
header_grid.setColumnStretch(0, 0)   # 队列
header_grid.setColumnStretch(1, 1)   # 文件名
header_grid.setColumnStretch(2, 3)   # 主题
header_grid.setColumnStretch(3, 1)   # 时长
header_grid.setColumnStretch(4, 1)   # 大小
header_grid.setColumnStretch(5, 1)   # 状态
header_grid.setColumnStretch(6, 2)   # 操作

# 每列表头 label 的对齐
headers = [
    ("", Qt.AlignCenter),         # 队列
    ("文件名", Qt.AlignLeft),
    ("主题", Qt.AlignLeft),
    ("时长", Qt.AlignCenter),
    ("大小", Qt.AlignCenter),
    ("状态", Qt.AlignCenter),
    ("操作", Qt.AlignCenter),
]
for col, (text, align) in enumerate(headers):
    lbl = QLabel(text)
    lbl.setAlignment(align)
    header_grid.addWidget(lbl, 0, col)
```

---

#### FIX-19：数据行间距 — 从 0 改为 1px

**问题**：原版每行有 `pady=1` 的间距，新版 `setSpacing(0)` 导致行间无分隔。

**修改**：
```python
self._data_layout.setSpacing(1)  # 改为 1px
```

---

### 2.4 音色库页（`voiceprint_page.py`）

#### FIX-20：详情面板标题字号还原

**问题**：原版 `font_size=18, weight="bold"`，新版 `font-size: 14px` 无 bold。

**修改**：
```python
self._detail_title.setStyleSheet(f"""
    font-size: 18px;
    font-weight: bold;
    color: {C_TXT1};
    background: transparent;
    border: none;
""")
```

---

#### FIX-21：详情面板卡片风格 — 从 QGroupBox 改为扁平 QFrame

**问题**：原版用 `CTkFrame(fg_color=C_BG, corner_radius=6)` 做扁平卡片，新版用 `QGroupBox("基本信息")` 有凸起的标题区。

**修改**：将 QGroupBox 替换为 QFrame + QLabel 标题：

```python
def _create_detail_card(self, parent, title):
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {C_TXT1}; background: transparent; border: none;")
    layout.addWidget(title_lbl)

    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {C_BG};
            border-radius: 6px;
            border: none;
        }}
    """)
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 8, 12, 8)
    card_layout.setSpacing(4)
    layout.addWidget(card)

    return container, card_layout
```

---

#### FIX-22：列表选中色 — 从深蓝白字改为浅蓝

**问题**：原版选中色 `#E8F0FE`（浅蓝背景 + 深色文字），新版 `QListWidget::item:selected` 用 `C_ACCENT`（深蓝背景 + 白色文字）。

**修改位置**：`voiceprint_page.py` 中 QListWidget 的 QSS

**改为**：
```css
QListWidget::item:selected {
    background-color: #E8F0FE;
    color: #1A1A1A;
}
```

---

#### FIX-23：编辑/删除按钮添加 hover 效果和手型光标

**修改**：
```python
edit_btn.setCursor(Qt.PointingHandCursor)
delete_btn.setCursor(Qt.PointingHandCursor)
# 使用 btn-primary / btn-danger class
edit_btn.setProperty("class", "btn-primary")
delete_btn.setProperty("class", "btn-danger")
```

---

### 2.5 对话框（`dialogs.py`）

#### FIX-24：ExportDialog — 从 ComboBox 改回 RadioButton 组

**问题**：原版用 4 个 RadioButton 直观展示所有导出格式，新版改为 1 个 ComboBox 下拉框，用户需要额外点击才能看到选项。

**修改位置**：`ExportDialog._build()` 方法

改为：
```python
# 格式选择（RadioButton 组）
fmt_group = QButtonGroup(self)
for label, fmt_key in OUTPUT_FORMATS.items():
    rb = QRadioButton(label)
    rb.setStyleSheet(f"font-size: 12px; spacing: 8px;")
    fmt_group.addButton(rb)
    fmt_layout.addWidget(rb)
```

---

#### FIX-25：MergeOrderDialog 确认按钮颜色还原

**问题**：原版确认按钮 `fg_color=C_SUCCESS`（绿色），新版用 `C_ACCENT`（蓝色）。绿色表示"开始执行"的语义。

**修改**：
```python
confirm_btn.setProperty("class", "btn-success")
confirm_btn.setText("开始合并转写")
confirm_btn.setFixedSize(120, 32)
```

---

### 2.6 主窗口（`app.py`）

#### FIX-26：添加窗口初始尺寸

**问题**：新版缺少 `geometry` 设置，启动时窗口大小不可控。

**修改位置**：`app.py` `__init__` 方法

**添加**：
```python
self.resize(1060, 720)
self.setMinimumSize(880, 600)
```

---

#### FIX-27：状态栏样式还原

**问题**：原版状态栏是自定义 CTkFrame（height=28, bg=#FAFAFA, border_top=#E5E5E5），右侧显示引擎名。新版用 QStatusBar 原生样式。

**修改**：
```python
self._status_bar.setFixedHeight(28)
self._status_bar.setStyleSheet(f"""
    QStatusBar {{
        background-color: {C_SIDEBAR};
        border-top: 1px solid {C_BORDER};
        font-size: 11px;
        color: {C_TXT3};
    }}
    QStatusBar::item {{ border: none; }}
""")
self._status_bar.showMessage("就绪")
# 右侧永久标签
engine_label = QLabel("SenseVoice + CAM++ + ct-punc")
engine_label.setStyleSheet(f"font-size: 11px; color: {C_TXT3}; padding-right: 8px;")
self._status_bar.addPermanentWidget(engine_label)
```

---

#### FIX-28：TopBar 底部分隔线调整

**问题**：新版 TopBar 有 `border-bottom: 1px solid`，但原版没有。如果下方卡片也有上边框，会产生双线效果。

**修改**：保留 border-bottom（作为 TopBar 与内容的分隔），但确保下方内容区域无上边距/上边框。

---

## 三、P2：功能补全（后续实施）

以下项目在审查报告中已详细记录，此处简要列出：

| 序号 | 项目 | 文件 | 说明 |
|------|------|------|------|
| FIX-29 | 设置页缺少音频设备 section | settings_page.py | 添加 VB-Audio Cable 开关 + hint |
| FIX-30 | 设置页缺少通知 section | settings_page.py | 添加系统通知开关 + hint |
| FIX-31 | AI section 缺少 6 个下拉控件 | settings_page.py | 模型厂商/摘要模型/接入模式/本地LLM/自动摘要模式/纠错模式 |
| FIX-32 | API Key 明文/密文切换按钮 | settings_page.py | 添加 👁/🔒 切换按钮 |
| FIX-33 | AddVoiceDialog 录音弹窗 | voiceprint_page.py | 完整的录音添加音色功能 |
| FIX-34 | TranscriptionCompleteDialog | dialogs.py | 转写完成弹窗 |
| FIX-35 | 音色库匹配建议 | dialogs.py | SpeakerDialog 中的声纹自动匹配 |
| FIX-36 | Win11 窗口圆角 | app.py | DwmSetWindowAttribute 圆角 |

---

## 四、实施注意事项

### 4.1 修改顺序

**强烈建议按以下顺序实施**：

1. **先改 `styles.py` 全局 QSS**（FIX-01 ~ FIX-05）— 这是地基，改完后所有页面会同时改善
2. **再改 `settings_page.py`**（FIX-06 ~ FIX-12）— 用户反馈最强烈的页面
3. **再改 `home_page.py` + `recording_bar.py`**（FIX-13 ~ FIX-17）— 主页布局
4. **再改 `file_list_view.py`**（FIX-18 ~ FIX-19）— 列表对齐
5. **再改 `voiceprint_page.py`**（FIX-20 ~ FIX-23）— 音色库
6. **再改 `dialogs.py`**（FIX-24 ~ FIX-25）— 对话框
7. **最后改 `app.py`**（FIX-26 ~ FIX-28）— 主窗口

### 4.2 验证清单

每修改一个文件后，需要验证：

1. 启动应用无报错
2. 三个页面（主页/音色库/设置）均可正常切换
3. 各按钮 hover 时鼠标变色
4. 下拉框能看出是下拉框（有箭头指示器）
5. 设置页标题在卡片上方，卡片内无标题
6. 输入框随窗口拉宽而变宽
7. 文件列表表头与数据行各列严格对齐
8. 录音栏内容不出现双重内边距

### 4.3 QSS class 选择器使用说明

PySide6 的 QSS 支持 `QWidget[class="xxx"]` 属性选择器，但需要先设置属性：

```python
# 设置属性
btn.setProperty("class", "btn-primary")

# QSS 中使用
QPushButton[class="btn-primary"] {
    background-color: #0067C0;
    color: white;
}
```

注意：PySide6 不支持 `[cssClass="xxx"]`（这是 CSS 的 class 语法），必须用 `setProperty` + 属性选择器的方式。

---

## 五、分工建议

| 角色 | 负责内容 |
|------|----------|
| **QoderWork** | 本方案撰写 + 后续审阅 + 截图对比验证 |
| **MiMo/千问 Code** | P0 全局样式修复 + P1 各页面布局还原（FIX-01 ~ FIX-28） |
| **MiMo/千问 Code** | P2 功能补全（FIX-29 ~ FIX-36），按优先级排期 |
| **用户** | 每轮修复后测试验收，反馈视觉效果 |

---

> 本方案基于对原版 6700 行代码和新版 5300 行代码的逐字段对比分析。所有修改参数均经过交叉验证（grep 确认代码行号 + 对比原版实现）。
