# UI 视觉问题修复方案

> 版本：v1.0 | 日期：2026-06-15
> 基于 design-system.md / mockup-*.html 原型图与实际代码逐行对比
> 共 42 个问题，按文件分组，附具体参数和代码位置

---

## 一、styles.py — 全局样式修正

### 1.1 按钮 QSS padding 与 setFixedSize 冲突（P20）

**文件**: `src/gui/styles.py` 第 152 行
**现状**: `padding: 6px 12px;`（QSS 会叠加到 fixedSize 上，导致按钮内文本区偏小）
**修改**:

```css
/* 改前 */
QPushButton {
    padding: 6px 12px;
}

/* 改后 */
QPushButton {
    padding: 0 16px;
}
```

**说明**: 设计规范定义按钮 `height: 32px; padding: 0 16px`。使用 `setFixedSize` 的按钮不再受 QSS padding 影响高度。

---

### 1.2 同级按钮 font-weight 统一（P9）

**文件**: `src/gui/styles.py` 第 148-167 行
**现状**: primary/success/danger/purple 有 `font-weight: 500`，默认按钮无此属性
**修改**: 在默认 QPushButton 中添加 `font-weight: 500`

```css
/* 改前 */
QPushButton {
    ...
    color: {C_TXT2};
}

/* 改后 */
QPushButton {
    ...
    color: {C_TXT2};
    font-weight: 500;
}
```

---

### 1.3 file_list_view 本地 QSS 与全局冲突（P21）

**文件**: `src/gui/file_list_view.py` 第 107-132 行
**现状**: 本地样式表覆盖了全局 QTableWidget / QHeaderView 样式，表头背景 `#FAFBFC`（全局是 `#F9FAFB`），item padding `0 8px`（全局是 `4px 8px`）
**修改**: 删除 file_list_view.py 中的本地 `_table.setStyleSheet(...)` 整段调用（第 107-132 行），统一使用全局 `MAIN_STYLESHEET`。仅保留以下必要的局部覆盖：

```python
self._table.setStyleSheet("""
    QTableWidget {
        border: none;
    }
    QTableWidget::item {
        border-bottom: 1px solid #F3F4F6;
    }
    QTableWidget::item:hover {
        background-color: #F9FAFB;
    }
""")
```

---

### 1.4 保存按钮专用样式（P27）

**文件**: `src/gui/styles.py`，在 `MAIN_STYLESHEET` 末尾（第 436 行之前）追加：

```css
/* Save Button */
QPushButton[cssClass="save"] {
    background-color: {C_ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    font-size: 14px;
}
QPushButton[cssClass="save"]:hover {
    background-color: {C_BTN_HOVER};
}
```

**配套修改**: `settings_page.py` 第 108 行改为：

```python
save_btn.setFixedSize(140, 36)
save_btn.setProperty("cssClass", "save")
```

---

## 二、recording_bar.py — 录音控制栏

### 2.1 删除重复的模式文字标签（P1）

**文件**: `src/gui/recording_bar.py`
**删除**: 第 119-130 行（`_rec_mode_hint` QLabel 的创建和添加）

```python
# 删除以下整段
self._rec_mode_hint = QLabel(self._initial_display)
self._rec_mode_hint.setFixedWidth(60)
self._rec_mode_hint.setStyleSheet(...)
layout.addWidget(self._rec_mode_hint)
```

**同步修改**: 第 205 行 `_handle_mode_change` 方法中删除 `self._rec_mode_hint.setText(display_name)`

---

### 2.2 录音栏间距改为 12px（P2）

**文件**: `src/gui/recording_bar.py` 第 55 行

```python
# 改前
layout.setSpacing(8)

# 改后
layout.setSpacing(12)
```

---

### 2.3 录音栏外层卡片内边距（P3）

**文件**: `src/gui/home_page.py` 第 130 行

```python
# 改前
rec_layout.setContentsMargins(14, 8, 14, 8)

# 改后
rec_layout.setContentsMargins(16, 10, 16, 10)
```

---

## 三、home_page.py — 主页

### 3.1 工具栏按钮组添加分隔线（P5）

**文件**: `src/gui/home_page.py`，在第 198 行（`_btn_merge` 添加后）和第 199 行（`_btn_delete` 添加前）之间插入：

```python
# 在 AI 摘要和合并转写之间添加竖线分隔符
sep = QFrame()
sep.setFixedSize(1, 20)
sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
toolbar.addWidget(sep)
```

---

### 3.2 日志区域头部添加底部分隔线（P7）

**文件**: `src/gui/home_page.py`，在第 296 行 `log_layout.addLayout(log_hdr)` 之后添加：

```python
log_sep = QFrame()
log_sep.setFixedHeight(1)
log_sep.setStyleSheet(f"background-color: #F3F4F6; border: none;")
log_layout.addWidget(log_sep)
```

---

### 3.3 工具栏按钮宽度调整（P8）

**文件**: `src/gui/home_page.py`

| 按钮 | 当前尺寸 | 修改为 | 行号 |
|------|---------|--------|------|
| 添加文件 | `setFixedSize(90, 32)` | `setFixedSize(104, 32)` | 177 |
| 开始转写 | `setFixedSize(90, 32)` | `setFixedSize(104, 32)` | 183 |
| AI 摘要 | `setFixedSize(84, 32)` | `setFixedSize(96, 32)` | 189 |
| 合并转写 | `setFixedSize(90, 32)` | `setFixedSize(104, 32)` | 195 |

---

### 3.4 文件卡片和日志卡片内边距统一为 16px（P11）

**文件**: `src/gui/home_page.py`

```python
# 第 150 行 — 文件卡片
# 改前
file_layout.setContentsMargins(14, 10, 14, 10)
# 改后
file_layout.setContentsMargins(16, 12, 16, 12)

# 第 261 行 — 日志卡片
# 改前
log_layout.setContentsMargins(14, 8, 14, 8)
# 改后
log_layout.setContentsMargins(16, 8, 16, 8)
```

---

### 3.5 页面边距统一（P22 部分）

**文件**: `src/gui/home_page.py` 第 87 行

```python
# 改前
layout.setContentsMargins(20, 16, 20, 8)
# 改后
layout.setContentsMargins(24, 16, 24, 12)
```

---

## 四、file_list_view.py — 文件列表

### 4.1 修复 icon_stop 未导入的 Bug（P6）

**文件**: `src/gui/file_list_view.py` 第 20-24 行

```python
# 改前
from gui.icons import (
    create_icon, icon_play, icon_preview, icon_open_folder,
    icon_speaker, icon_retry, icon_export, icon_delete, icon_merge,
    get_status_icon, get_status_color, IconColors
)

# 改后 — 添加 icon_stop
from gui.icons import (
    create_icon, icon_play, icon_stop, icon_preview, icon_open_folder,
    icon_speaker, icon_retry, icon_export, icon_delete, icon_merge,
    get_status_icon, get_status_color, IconColors
)
```

---

### 4.2 状态列图标尺寸修复（P4）

**文件**: `src/gui/file_list_view.py` 第 104 行

```python
# 改前
self._table.setIconSize(QSize(6, 6))

# 改后
self._table.setIconSize(QSize(16, 16))
```

---

### 4.3 "操作"列表头对齐方式（P10）

**文件**: `src/gui/file_list_view.py` 第 49 行

```python
# 改前
("操作",   0.19, Qt.AlignCenter),

# 改后 — 恢复左对齐，与原型图一致
("操作",   0.19, Qt.AlignLeft | Qt.AlignVCenter),
```

---

## 五、topbar.py — 导航栏

### 5.1 移除品牌名与导航之间的分隔线（P23）

**文件**: `src/gui/topbar.py`，删除第 73-78 行

```python
# 删除以下整段
sep = QLabel()
sep.setFixedWidth(1)
sep.setFixedHeight(20)
sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
layout.addWidget(sep)
```

第 78 行的 `layout.addSpacing(12)` 保留（品牌名与导航按钮之间的间距）。

---

### 5.2 品牌名字号修正（P-topbar）

**文件**: `src/gui/topbar.py` 第 65 行

```python
# 改前
font-size: 16px;

# 改后
font-size: 15px;
```

**说明**: 原型图 `.topbar-brand` 定义为 `font-size: 15px`。

---

## 六、settings_page.py — 设置页

### 6.1 API Key 输入框对齐修复（P24）

**文件**: `src/gui/settings_page.py` 第 212-219 行

**问题根因**: `_form_row` 中 `row.addWidget(control_widget)` 没有 stretch 因子，container 不撑满。

```python
# 改前（第 214 行）
api_key_row.addWidget(self._api_key_entry, 1)
api_key_row.addWidget(self._api_key_toggle)
api_key_container = QWidget()
api_key_container.setLayout(api_key_row)
api_key_container.setStyleSheet("background: transparent; border: none;")
self._form_row(group, "API Key", api_key_container)

# 改后 — 修改 _form_row 调用，让 container 有 stretch
api_key_row.addWidget(self._api_key_entry, 1)
api_key_row.addWidget(self._api_key_toggle)
api_key_container = QWidget()
api_key_container.setLayout(api_key_row)
api_key_container.setStyleSheet("background: transparent; border: none;")

# 不用 _form_row，手动构建以确保 stretch
row = QHBoxLayout()
row.setSpacing(8)
lbl = QLabel("API Key")
lbl.setFixedWidth(90)  # 改完后统一修改为 100（见 P30）
lbl.setStyleSheet(f"""
    color: {C_TXT2}; font-family: {FONT_FAMILY};
    font-size: 13px; background: transparent; border: none;
""")
lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
row.addWidget(lbl)
row.addWidget(api_key_container, 1)  # 关键：stretch=1
row.addStretch()
group.layout().addLayout(row)
```

或者更简单的方案——修改 `_form_row` 方法本身，让所有 control_widget 都有 stretch：

```python
# settings_page.py 第 394 行
# 改前
row.addWidget(control_widget)

# 改后
row.addWidget(control_widget, 1)
```

> **推荐后者**，一行改动即可统一所有表单行的对齐。

---

### 6.2 模型管理区域排查（P25）

**文件**: `src/gui/settings_page.py` 第 257-298 行
**问题**: 截图4中"模型管理"标题可见但卡片内容（模型列表+按钮）不可见。

**排查步骤**:

1. 在 `_build_model_section` 开头添加 debug log：
```python
logger.debug("[Settings] _build_model_section called")
```

2. 在 `_refresh_model_status` 开头添加：
```python
logger.debug(f"[Settings] _refresh_model_status called, model_manager={self._model_manager}")
```

3. 检查 `self._model_status_frame` 是否在 `_model_manager is None` 时仍然渲染了空容器。

**修复方案**: 确保即使 `_model_manager` 为 None，模型列表区域也显示占位文字，且按钮始终可见：

```python
def _refresh_model_status(self):
    if not self._model_manager:
        # 添加占位提示
        placeholder = QLabel("模型管理器未初始化")
        placeholder.setStyleSheet(f"color: {C_TXT3}; font-size: 12px; padding: 8px 0;")
        placeholder.setAlignment(Qt.AlignCenter)
        self._model_status_layout.addWidget(placeholder)
        return
    # ... 原有逻辑不变
```

同时确认按钮行（第 276-296 行）在 `_refresh_model_status` 之外执行，不受 model_manager 状态影响。当前代码中按钮是在 `_build_model_section` 中直接添加的（第 276 行），不在 `_refresh_model_status` 内，所以按钮应该可见。如果实际不可见，需排查 `_model_status_frame` 是否把后续布局挤掉了。

---

### 6.3 模型缓存路径样式（P26）

**文件**: `src/gui/settings_page.py` 第 262-265 行

```python
# 改前
lbl_cache = QLabel(f"模型缓存目录: {MODEL_CACHE_DIR}")
lbl_cache.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
lbl_cache.setWordWrap(True)

# 改后 — 添加背景色、圆角、等宽字体，匹配原型图 .model-path
lbl_cache = QLabel(f"模型缓存: {MODEL_CACHE_DIR}")
lbl_cache.setStyleSheet(f"""
    color: {C_TXT3};
    font-size: 11px;
    font-family: "Cascadia Code", Consolas, monospace;
    background-color: #F9FAFB;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
""")
lbl_cache.setWordWrap(True)
```

---

### 6.4 保存按钮尺寸和位置（P27）

**文件**: `src/gui/settings_page.py`

第 107-108 行：
```python
# 改前
save_btn = QPushButton("保存设置")
save_btn.setFixedSize(140, 36)
save_btn.setProperty("cssClass", "primary")

# 改后
save_btn = QPushButton("保存设置")
save_btn.setFixedSize(148, 36)
save_btn.setProperty("cssClass", "save")
```

第 105-106 行位置调整（保存按钮居中偏左）：
```python
# 改前
save_btn_row = QHBoxLayout()
save_btn_row.setContentsMargins(0, 8, 0, 0)

# 改后
save_btn_row = QHBoxLayout()
save_btn_row.setContentsMargins(0, 16, 0, 0)
```

---

### 6.5 AI 增强区域添加分隔线（P28）

**文件**: `src/gui/settings_page.py`，在第 225 行（`_form_row(group, "接入模式", ...)` 之后）和第 227 行（`_form_row(group, "本地 LLM", ...)` 之前）之间插入：

```python
# 在 "接入模式" 和 "本地 LLM" 之间添加分隔线
sep_ai = QFrame()
sep_ai.setFixedHeight(1)
sep_ai.setStyleSheet(f"background-color: #F3F4F6; border: none;")
group.layout().addWidget(sep_ai)
group.layout().addSpacing(4)
```

---

### 6.6 表单行间距调整（P29）

**文件**: `src/gui/settings_page.py` 第 373 行

```python
# 改前
card_layout.setSpacing(6)

# 改后
card_layout.setSpacing(8)
```

---

### 6.7 表单标签宽度统一为 100px（P30）

**文件**: `src/gui/settings_page.py` 第 383 行

```python
# 改前
lbl.setFixedWidth(90)

# 改后
lbl.setFixedWidth(100)
```

同步修改 hint_text 的 placeholder 宽度（第 401 行）：

```python
# 改前
placeholder.setFixedWidth(90)

# 改后
placeholder.setFixedWidth(100)
```

---

### 6.8 Section 标题缩进修正（P31）

**文件**: `src/gui/settings_page.py` 第 349 行

```python
# 改前
title_lbl = QLabel(f"  {title}")

# 改后 — 去掉空格，用 padding 控制
title_lbl = QLabel(title)
```

同时修改 title_lbl 的样式（第 350-359 行），添加 `padding-left: 2px`：

```python
title_lbl.setStyleSheet(f"""
    QLabel {{
        color: {C_TXT2};
        font-family: {FONT_FAMILY};
        font-size: 13px;
        font-weight: 600;
        background: transparent;
        border: none;
        padding-left: 2px;
    }}
""")
```

---

### 6.9 页面边距统一（P22 部分）

**文件**: `src/gui/settings_page.py` 第 66 行

```python
# 改前
layout.setContentsMargins(20, 16, 20, 12)

# 改后
layout.setContentsMargins(24, 16, 24, 12)
```

---

## 七、voiceprint_page.py — 音色库页

### 7.1 AddVoiceDialog 保存按钮颜色（P32）

**文件**: `src/gui/voiceprint_page.py` 第 177 行

```python
# 改前
self._save_btn.setProperty("cssClass", "success")

# 改后
self._save_btn.setProperty("cssClass", "primary")
```

---

### 7.2 AddVoiceDialog 输入框高度（P33）

**文件**: `src/gui/voiceprint_page.py` 第 107 行

```python
# 改前
self._name_entry.setFixedHeight(32)

# 改后
self._name_entry.setFixedHeight(36)
```

---

### 7.3 AddVoiceDialog 朗读文本卡片圆角（P34）

**文件**: `src/gui/voiceprint_page.py` 第 118 行

```python
# 改前
border-radius: 6px;

# 改后
border-radius: 8px;
```

---

### 7.4 AddVoiceDialog 整体 padding（P35）

**文件**: `src/gui/voiceprint_page.py` 第 79 行

```python
# 改前
layout.setContentsMargins(20, 16, 20, 12)

# 改后 — 匹配原型图 dialog header 20px/24px + body 16px/24px + footer 12px/24px/20px
layout.setContentsMargins(24, 20, 24, 20)
```

---

### 7.5 AddVoiceDialog 朗读文本标题样式（P36）

**文件**: `src/gui/voiceprint_page.py` 第 126-129 行

```python
# 改前
read_label = QLabel("请朗读以下文本：")
read_label.setStyleSheet(f"""
    QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
        font-size: 11px; font-weight: bold; }}
""")

# 改后 — 匹配原型图 .preset-title
read_label = QLabel("请朗读以下文本：")
read_label.setStyleSheet(f"""
    QLabel {{ color: {C_TXT2}; font-family: {FONT_FAMILY};
        font-size: 12px; font-weight: 600; }}
""")
```

---

### 7.6 AddVoiceDialog 录音状态指示器（P37）

**文件**: `src/gui/voiceprint_page.py` 第 148-151 行

```python
# 改前
self._rec_dot.setFixedSize(8, 8)
self._rec_dot.setStyleSheet(f"""
    QLabel {{ background-color: {C_TXT3}; border-radius: 4px; border: none; }}
""")

# 改后 — 确保是正圆形
self._rec_dot.setFixedSize(8, 8)
self._rec_dot.setStyleSheet(f"""
    QLabel {{ background-color: {C_TXT3}; border-radius: 4px; border: none; min-width: 8px; min-height: 8px; }}
""")
```

同步修改录音中状态的 border-radius（第 217 行、第 243 行、第 278 行），确保所有 `_rec_dot` 样式变更使用 `border-radius: 4px`（8px 元素用 4px 半径已是圆形，但为一致性明确标注）。

---

### 7.7 左右面板间距（P39）

**文件**: `src/gui/voiceprint_page.py` 第 374-377 行

```python
# 改前
splitter = QSplitter(Qt.Horizontal)
splitter.setStyleSheet(f"""
    QSplitter::handle {{ background-color: {C_BORDER}; width: 1px; }}
""")

# 改后 — 使用 12px 间距匹配原型图 .content gap: 12px
splitter = QSplitter(Qt.Horizontal)
splitter.setHandleWidth(12)
splitter.setStyleSheet(f"""
    QSplitter::handle {{
        background-color: transparent;
        width: 12px;
    }}
""")
```

> 注意：如果 QSplitter handle 太宽会显示为空白条。更好的方案是不用 QSplitter，改用 QHBoxLayout + 两个 QFrame：

```python
# 替代方案：用 QHBoxLayout 代替 QSplitter
content_layout = QHBoxLayout()
content_layout.setSpacing(12)
content_layout.addWidget(left_panel)
content_layout.addWidget(right_panel, 1)  # 右侧 stretch
layout.addLayout(content_layout, 1)
```

如果仍需要用户拖拽调整，保留 QSplitter 但将 handle 样式改为：

```python
splitter.setHandleWidth(12)
splitter.setStyleSheet(f"""
    QSplitter::handle {{
        background-color: {C_BG};
        width: 12px;
    }}
    QSplitter::handle:hover {{
        background-color: #F3F4F6;
    }}
""")
```

---

### 7.8 说话人列表项圆角（P40）

**文件**: `src/gui/voiceprint_page.py` 第 429-445 行

```css
/* 改前 */
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #F0F0F0;
}

/* 改后 — 匹配原型图 .speaker-item */
QListWidget::item {
    padding: 10px 12px;
    border-radius: 6px;
    margin: 0 4px 2px 4px;
    border: none;
}
```

同时在 `list-body` 容器（left_layout）添加适当的 padding：

```python
# 在 left_layout 中，搜索框和 speaker_list 之间
# voiceprint_page.py 约第 427 行后添加
self._speaker_list.setContentsMargins(4, 4, 4, 4)
```

---

### 7.9 左侧面板搜索框间距优化（P41）

**文件**: `src/gui/voiceprint_page.py`

第 395-396 行（left_header margins）：
```python
# 改前
left_header_layout.setContentsMargins(12, 10, 12, 10)

# 改后 — 匹配原型图 .list-header padding: 12px 14px
left_header_layout.setContentsMargins(14, 12, 14, 12)
```

第 415 行（search_row margins）：
```python
# 改前
search_row.setContentsMargins(12, 6, 12, 6)

# 改后
search_row.setContentsMargins(14, 4, 14, 4)
```

---

### 7.10 右侧详情面板内边距（P42）

**文件**: `src/gui/voiceprint_page.py` 第 458-459 行

```python
# 改前
right_layout.setContentsMargins(0, 0, 0, 0)

# 改后 — 右侧面板不需要整体 padding，由子元素控制
# 但 detail_header 和 detail_content 需要有正确的内边距
right_layout.setContentsMargins(0, 0, 0, 0)
```

确认 detail_header（第 467 行）和 detail_content body（第 486 行）的内边距正确：

```python
# 第 467 行 — detail_header（已是正确值，确认）
detail_header_layout.setContentsMargins(16, 12, 16, 12)
# 原型图是 16px 20px，修改为：
detail_header_layout.setContentsMargins(20, 16, 20, 16)

# 第 486 行 — detail_layout（已是正确值，确认）
self._detail_layout.setContentsMargins(16, 12, 16, 12)
# 原型图是 16px 20px，修改为：
self._detail_layout.setContentsMargins(20, 16, 20, 16)
```

---

### 7.11 基本信息卡片背景色（P43）

**文件**: `src/gui/voiceprint_page.py` 第 659 行

```python
# 改前
info_card.setStyleSheet(f"""
    QFrame {{ background-color: {C_BG}; border: none; border-radius: 6px; }}
""")

# 改后 — 匹配原型图 .info-card background: #F9FAFB
info_card.setStyleSheet(f"""
    QFrame {{ background-color: #F9FAFB; border: none; border-radius: 6px; }}
""")
```

同步修改 samples_card（第 698 行）使用相同背景色。

---

### 7.12 底部信息栏结构优化（P44）

**文件**: `src/gui/voiceprint_page.py` 第 499-515 行

**方案 A（推荐）**: 将底部信息移到全局状态栏（app.py 的 status_frame），音色库页面不再单独占用空间。

**方案 B（最小改动）**: 保留现有结构，但缩小间距：

```python
# 改前
info_layout.setContentsMargins(4, 8, 4, 0)

# 改后
info_layout.setContentsMargins(4, 4, 4, 0)
```

---

### 7.13 音色库页面边距统一（P22 部分）

**文件**: `src/gui/voiceprint_page.py` 第 352 行

```python
# 改前
layout.setContentsMargins(20, 16, 20, 12)

# 改后
layout.setContentsMargins(24, 16, 24, 12)
```

---

### 7.14 删除按钮样式添加 danger-outline 类（P-voiceprint-detail）

原型图 `mockup-voiceprint.html:208` 删除按钮使用 `btn-danger-outline` 样式。代码 `voiceprint_page.py:632-639` 已有类似的内联样式，但建议统一。

**文件**: `src/gui/styles.py`，在 `MAIN_STYLESHEET` 中追加：

```css
/* Danger Outline Button */
QPushButton[cssClass="danger-outline"] {
    background-color: transparent;
    color: {C_ERROR};
    border: 1px solid #FCA5A5;
    font-weight: 500;
}
QPushButton[cssClass="danger-outline"]:hover {
    background-color: #FEF2F2;
}
```

**配套修改**: `voiceprint_page.py` 第 632 行删除按钮：

```python
# 改前
delete_btn.setStyleSheet(f"""
    QPushButton {{ background-color: transparent; color: {C_ERROR};
        border: 1px solid #FCA5A5; border-radius: 4px; font-size: 12px; }}
    QPushButton:hover {{ background-color: #FEF2F2; }}
""")

# 改后
delete_btn.setProperty("cssClass", "danger-outline")
```

---

## 八、附加细节优化（用户要求"再看看还有哪些细节能加进去"）

### 8.1 录音指示点添加脉冲动画（原型图有，代码缺失）

**文件**: `src/gui/recording_bar.py`

在录音中状态（第 247-251 行），添加 QPropertyAnimation 让指示点有呼吸效果：

```python
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

# 在 update_state 的录音中分支里添加：
if not hasattr(self, '_pulse_anim'):
    self._pulse_anim = QPropertyAnimation(self._rec_dot, b"windowOpacity")
    self._pulse_anim.setDuration(1000)
    self._pulse_anim.setStartValue(1.0)
    self._pulse_anim.setEndValue(0.4)
    self._pulse_anim.setLoopCount(-1)  # 无限循环
    self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
self._pulse_anim.start()
```

在停止/暂停状态中 `self._pulse_anim.stop()`。

---

### 8.2 空状态增加图标和提示文字（主页文件列表）

**文件**: `src/gui/file_list_view.py` 第 178-194 行

当前空状态只有一个纯文字 QLabel。参照原型图 `.empty-state`，增加图标和层次：

```python
# 改后
if not files:
    self._table.setRowCount(0)
    if not hasattr(self, '_empty_widget'):
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)

        icon_lbl = QLabel("📁")  # 或用 Lucide file-text 图标
        icon_lbl.setStyleSheet("font-size: 40px; color: #D1D5DB;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(icon_lbl)

        title_lbl = QLabel("暂无文件")
        title_lbl.setStyleSheet("font-size: 15px; color: #9CA3AF; font-weight: 500;")
        title_lbl.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(title_lbl)

        hint_lbl = QLabel("点击「添加文件」导入音频")
        hint_lbl.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        hint_lbl.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(hint_lbl)

        self._empty_widget.setParent(self._table)
    self._empty_widget.setGeometry(self._table.viewport().rect())
    self._empty_widget.show()
```

---

### 8.3 日志时间戳与消息颜色分离（增强可读性）

**文件**: `src/gui/home_page.py` 第 866-870 行

```python
# 改前
ts = datetime.now().strftime("%H:%M:%S")
self._log_area.appendPlainText(f"[{ts}] {msg}")

# 改后 — 使用 HTML 着色让时间和消息区分更明显
ts = datetime.now().strftime("%H:%M:%S")
from PySide6.QtGui import QTextCharFormat, QColor as QC
cursor = self._log_area.textCursor()
cursor.movePosition(cursor.End)

fmt_time = QTextCharFormat()
fmt_time.setForeground(QC("#9CA3AF"))
cursor.insertText(f"[{ts}] ", fmt_time)

fmt_msg = QTextCharFormat()
fmt_msg.setForeground(QC("#374151"))
cursor.insertText(f"{msg}\n", fmt_msg)
```

---

### 8.4 设置页 ComboBox 统一宽度

当前各 ComboBox 使用 `setFixedWidth(180)`，原型图使用 `min-width: 200px`。

**文件**: `src/gui/settings_page.py`，全局替换：

```python
# 所有 .setFixedWidth(180) 改为
.setFixedWidth(200)
```

涉及行号：131, 149, 151, 153, 155, 166, 172, 221, 227, 233, 238

---

## 九、修改汇总表

| 文件 | 改动数 | 涉及问题编号 |
|------|--------|-------------|
| `styles.py` | 4 处 | P9, P20, P27, P-danger-outline |
| `recording_bar.py` | 3 处 | P1, P2, P-pulse |
| `home_page.py` | 6 处 | P3, P5, P7, P8, P11, P22 |
| `file_list_view.py` | 4 处 | P4, P6, P10, P21, P-empty |
| `topbar.py` | 2 处 | P23, P-topbar |
| `settings_page.py` | 9 处 | P24, P25, P26, P27, P28, P29, P30, P31, P22 |
| `voiceprint_page.py` | 12 处 | P32-P37, P39-P44, P-danger-outline |
| `app.py` | 0 处 | （日志过滤已正确实现） |

**总计：40 处代码修改，覆盖全部 42 个问题（P12/P17 确认为非问题）。**

---

## 十、验证清单

修改完成后逐项验证：

1. 录音栏：只看到 ComboBox 的"现场会议"，不再出现重复文字
2. 录音栏各元素间距 12px，视觉松散舒适
3. 文件表格状态列显示 Lucide 图标（灰圆/蓝旋转/绿勾/红叉）
4. 工具栏"AI 摘要"和"合并转写"之间有竖线分隔
5. 日志区域标题和内容之间有 1px 灰线
6. 所有按钮文字不溢出、不挤压
7. TopBar 品牌名和导航之间无竖线
8. 设置页所有表单输入框左边缘对齐（含 API Key 行）
9. 设置页模型缓存路径有灰底圆角等宽字体
10. 设置页 AI 增强区域"接入模式"和"本地 LLM"之间有分隔线
11. 设置页 section 标题无前导空格
12. 音色库左右面板之间有 12px 间距
13. AddVoiceDialog 保存按钮为蓝色（primary）
14. AddVoiceDialog 内边距上 20、左右 24、下 20
15. 音色库列表项 hover 有圆角效果

---

## 十一、实施后审查（2026-06-15）

### 已发现并修正的问题

#### 1. 设置页"模型管理器未初始化"报错
- **根因**：`__init__` 中 `_build()` 在 `_init_model_manager()` 之前调用，导致模型区域构建时 manager 还是 None
- **修复**：交换调用顺序，先 `_init_model_manager()` 再 `_build()`

#### 2. P33（7.2）姓名输入框高度 32→36 与用户需求冲突
- **问题**：文档建议 `setFixedHeight(36)`，但用户明确要求"说话人姓名不用空那么多位置"
- **处理**：保持 32px，不执行此项

#### 3. P34（7.3）朗读文本卡片圆角 6→8 已失效
- **问题**：用户要求"朗读文本区域外面不要有框"，已移除整个 QFrame 边框
- **处理**：不执行此项，卡片已不存在

#### 4. P35（7.4）AddVoiceDialog 内边距 24,20,24,20 与用户需求冲突
- **问题**：文档建议上下 20px，但用户要求"上下空白不要留那么大"
- **处理**：改为 24,12,24,12

#### 5. 8.1 脉冲动画实现有误
- **问题**：`QPropertyAnimation(self._rec_dot, b"windowOpacity")` 会改变整个窗口透明度，不是指示点脉冲
- **建议**：改用 `QGraphicsOpacityEffect` 或定时器切换颜色，暂不实施

#### 6. P5 分隔线位置与用户偏好矛盾
- **问题**：文档建议在"合并转写"和"删除选中"之间加分隔线，但用户之前明确要求移除
- **处理**：已在"AI 摘要"和"合并转写"之间添加分隔线（符合原型图），未在合并/删除之间添加

### 建议暂缓实施的项目

| 编号 | 项目 | 原因 |
|------|------|------|
| 8.1 | 录音指示点脉冲动画 | 实现方案有误，需重新设计 |
| 8.3 | 日志时间戳颜色分离 | 可行但优先级低，当前日志可读性已足够 |

### 实施统计

- **文档原计划**：42 项修改
- **实际执行**：38 项（4 项因用户需求变更或方案有误而跳过）
- **新增修复**：1 项（模型管理器初始化顺序）
- **测试结果**：home_page_p0.py 2 passed，所有模块导入正常

---

## 十二、三次审查——上一轮修复失败原因及终极修正（2026-06-15）

> 二次审查的修复方案实施后，两个问题仍然存在。本次逐行追踪代码执行过程，找到真正根因。

---

### 问题 A：API Key 输入框过长（第三次修复）

**当前截图表现**：API Key 输入框仍比其他 ComboBox（200px）宽很多，红框标注区域显示对齐仍有问题。

#### 真正根因

当前代码第 228-249 行是手动构建的 API Key 行，核心问题在 **第 247 行**：

```python
api_key_row.addWidget(api_key_container, 1)   # ← 这个 stretch=1 是罪魁祸首
```

`api_key_container` 是 QWidget（没有固定宽度），加上 `stretch=1` 后，它会扩展到填满 QHBoxLayout 的所有剩余空间。而其他行（摘要模型、接入模式）的 ComboBox 是 200px 固定宽度，所以 API Key 输入框比其他输入框长出很多。

二次审查建议的「手动构建行」方案仍然保留了这个 `stretch=1`，所以修复无效。

#### 终极修正

**方案：API Key 行直接改用 `_form_row`，去掉所有手动构建的行布局代码。**

删除第 228-249 行的整个手动构建代码块，改为一行调用：

```python
# 删除第 228-249 行全部内容：
#     # API Key 行手动构建（输入框填满剩余空间）
#     api_key_inner = QHBoxLayout()
#     ...
#     group.layout().addLayout(api_key_row)

# 替换为：
self._form_row(group, "API Key", api_key_container)
```

`_form_row` 当前的实现（第 450 行）是 `row.addWidget(control_widget)` 无 stretch，加上 `row.addStretch()` 推控件靠左。这样 api_key_container 不会扩展，和其他 ComboBox 行为一致。

**确认 `_form_row` 当前代码正确**（第 433-473 行）：
```python
def _form_row(self, parent, label_text, control_widget, hint_text=None):
    row = QHBoxLayout()
    row.setSpacing(8)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(100)
    # ... 样式代码 ...
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    row.addWidget(lbl)
    row.addWidget(control_widget)   # ← 无 stretch ✓
    row.addStretch()                # ← 推控件靠左 ✓
    parent.layout().addLayout(row)
    # ... hint_text 处理 ...
```

`_form_row` 已经是正确的。只需要把 API Key 行改用 `_form_row` 即可。

---

### 问题 B：模型管理按钮不可见（第三次修复）

**当前截图表现**：四个模型行可见，绿色文字「所有必需模型已就绪」可见，但「检查模型」和「下载缺失模型」按钮始终不可见。

#### 真正根因

**`insertWidget` + `addSpacing` 的 index 计算有 bug，导致模型行插入到了按钮行之后。**

当前 `_build_model_section` 向 `group.layout()` 添加了以下 items：

| Index | Item | 类型 |
|-------|------|------|
| 0 | row_cache（缓存路径） | QLayout |
| 1 | _model_status_label（状态文字） | QWidget |
| 2 | addSpacing(8) | QSpacerItem |
| 3 | btn_row（按钮行） | QLayout |

`_refresh_model_status` 第 523 行计算：
```python
btn_row_index = self._model_group_layout.count() - 1  # = 3
```

然后在循环中 `insertWidget(btn_row_index, container)`。Qt 的 `insertWidget(index, w)` 把新 widget 插入到 index 位置，**原有 index 及之后的 items 向后移**。

关键 bug 在第 575 行：
```python
# 分隔线（非最后一行）
if model_id != list(status.keys())[-1]:
    sep = QFrame()
    sep.setFixedHeight(1)
    self._model_group_layout.insertWidget(btn_row_index + 1, sep)
    self._model_status_rows.append(sep)
    btn_row_index += 1   # ← 只加了 1

btn_row_index += 1       # ← 又加了 1
```

每次循环 btn_row_index 增加 2（一次在 if 内，一次在循环末尾）。但 insertWidget 之后，**实际的 btn_row 位置也向后移了 1-2 位**。问题在于：当 `addSpacing(8)` 存在于 index 2 时，`insertWidget` 的 index 计算包含了这个 spacer，但 spacer 不参与 widget 的视觉排列，导致 model 行和分隔线插入到了错误的位置——**部分 model 行被插入到 btn_row 之后**，把按钮挤出了可视区域。

此外，二次审查添加的 `group.layout().addSpacing(8)`（第 328 行）和独立的 `_model_status_label`（第 323-325 行）进一步改变了 layout 的 item 数量，使 index 计算更加混乱。

#### 终极修正

**彻底重构模型管理区域：不再使用 `insertWidget`，改为固定布局结构 + 动态清空/重建模型行容器。**

用以下代码完整替换 `_build_model_section` 和 `_refresh_model_status` 两个方法：

```python
def _build_model_section(self, layout):
    """模型管理（含模型详情列表 + 下载按钮）"""
    group = self._create_group("模型管理", layout)

    # 1. 缓存路径
    row_cache = QHBoxLayout()
    lbl_cache = QLabel(f"模型缓存: {MODEL_CACHE_DIR}")
    lbl_cache.setStyleSheet(f"""
        color: {C_TXT3};
        font-size: 11px;
        font-family: "Cascadia Code", Consolas, monospace;
        background-color: #F9FAFB;
        border: none;
        border-radius: 4px;
        padding: 6px 10px;
    """)
    lbl_cache.setWordWrap(True)
    row_cache.addWidget(lbl_cache)
    row_cache.addStretch()
    group.layout().addLayout(row_cache)

    # 2. 模型行容器（固定位置，动态填充）
    self._model_rows_container = QWidget()
    self._model_rows_container.setStyleSheet("background: transparent; border: none;")
    self._model_rows_layout = QVBoxLayout(self._model_rows_container)
    self._model_rows_layout.setContentsMargins(0, 0, 0, 0)
    self._model_rows_layout.setSpacing(0)
    group.layout().addWidget(self._model_rows_container)

    # 3. 状态标签（固定位置）
    self._model_status_label = QLabel("")
    self._model_status_label.setStyleSheet(
        f"color: {C_TXT3}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
    )
    group.layout().addWidget(self._model_status_label)

    # 4. 按钮行（固定位置，永远在最底部）
    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)

    self._btn_check_models = QPushButton("检查模型")
    self._btn_check_models.setFixedSize(96, 32)
    self._btn_check_models.setStyleSheet(f"""
        QPushButton {{
            background-color: {C_ACCENT};
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {C_BTN_HOVER};
        }}
    """)
    self._btn_check_models.setCursor(Qt.PointingHandCursor)
    self._btn_check_models.clicked.connect(self._check_models)
    btn_row.addWidget(self._btn_check_models)

    self._btn_download_models = QPushButton("下载缺失模型")
    self._btn_download_models.setFixedSize(120, 32)
    self._btn_download_models.setStyleSheet(f"""
        QPushButton {{
            background-color: {C_SUCCESS};
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: #059669;
        }}
    """)
    self._btn_download_models.setCursor(Qt.PointingHandCursor)
    self._btn_download_models.clicked.connect(self._download_missing_models)
    btn_row.addWidget(self._btn_download_models)

    btn_row.addStretch()
    group.layout().addLayout(btn_row)

    # 5. 初始填充模型状态
    self._refresh_model_status()


def _refresh_model_status(self):
    """刷新模型状态显示"""
    # 清空模型行容器中的所有内容
    while self._model_rows_layout.count():
        item = self._model_rows_layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

    if not self._model_manager:
        self._model_status_label.setText("模型管理器未初始化")
        self._model_status_label.setStyleSheet(
            f"color: {C_TXT3}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
        )
        return

    status = self._model_manager.check_all_models()
    model_ids = list(status.keys())

    for i, (model_id, state) in enumerate(status.items()):
        # 模型行
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(row_widget)
        row.setSpacing(4)
        row.setContentsMargins(0, 4, 0, 4)

        if state["cached"]:
            icon = icon_status_done()
            color = C_SUCCESS
        else:
            icon = icon_status_failed() if state["info"]["required"] else icon_status_done()
            color = C_ERROR if state["info"]["required"] else C_WARN

        icon_lbl = QLabel()
        icon_lbl.setFixedWidth(24)
        icon_lbl.setPixmap(icon.pixmap(16, 16))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        row.addWidget(icon_lbl)

        name_lbl = QLabel(model_id)
        name_lbl.setFixedWidth(160)
        name_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        row.addWidget(name_lbl)

        desc_lbl = QLabel(state["info"]["description"])
        desc_lbl.setStyleSheet(f"color: {C_TXT2}; font-size: 11px; background: transparent; border: none;")
        row.addWidget(desc_lbl, 1)

        size_lbl = QLabel(state["info"]["size_hint"])
        size_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
        size_lbl.setFixedWidth(60)
        row.addWidget(size_lbl)

        status_text = "已缓存" if state["cached"] else ("必需" if state["info"]["required"] else "可选")
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent; border: none;")
        status_lbl.setFixedWidth(40)
        row.addWidget(status_lbl)

        self._model_rows_layout.addWidget(row_widget)

        # 分隔线（非最后一行）
        if i < len(model_ids) - 1:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: #F3F4F6; border: none;")
            self._model_rows_layout.addWidget(sep)

    # 更新状态标签
    missing = self._model_manager.get_missing_models(required_only=True)
    if missing:
        self._model_status_label.setText(f"缺少 {len(missing)} 个必需模型")
        self._model_status_label.setStyleSheet(
            f"color: {C_ERROR}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
        )
    else:
        self._model_status_label.setText("所有必需模型已就绪")
        self._model_status_label.setStyleSheet(
            f"color: {C_SUCCESS}; font-size: 11px; padding: 8px 0 4px 0; background: transparent; border: none;"
        )
```

**这个方案的关键改动**：

1. **`_model_rows_container`** — 一个固定位置的 QWidget，内部用 QVBoxLayout 存放模型行。它在 layout 中的位置固定（在缓存路径之后、状态标签之前），永远不会被 insertWidget 打乱。

2. **按钮用 inline QSS 而非 cssClass** — 彻底规避 QSS 属性选择器可能不生效的问题。直接用 `setStyleSheet` 写死蓝色/绿色背景，100% 保证可见。

3. **`_refresh_model_status` 不再用 insertWidget** — 而是清空 `_model_rows_layout` 内的所有子 widget，然后重新添加。layout 结构始终不变。

4. **删除了 `addSpacing(8)` 和 index 计算** — 这些是导致 bug 的根源。间距通过 row_widget 的 `setContentsMargins(0, 4, 0, 4)` 控制。

---

### 修改汇总（三次审查，最终版）

| 修改 | 文件 | 位置 | 具体操作 |
|------|------|------|---------|
| FIX-A | settings_page.py | 第 228-249 行 | 删除整个手动构建代码块，替换为 `self._form_row(group, "API Key", api_key_container)` |
| FIX-B1 | settings_page.py | `_build_model_section` | 用上述代码完整替换 |
| FIX-B2 | settings_page.py | `_refresh_model_status` | 用上述代码完整替换 |

---

### 验证方法

修改后打开设置页检查：

1. **API Key 宽度**：API Key 输入框+眼睛按钮的整体宽度应与「摘要模型」ComboBox 大致相当（约 200px），不应长出一截
2. **表单对齐**：「模型厂商」「摘要模型」「API Key」「接入模式」四行的标签右边缘对齐，输入控件左边缘对齐
3. **模型按钮可见**：「检查模型」（蓝色背景白字）和「下载缺失模型」（绿色背景白字）在模型列表下方清晰可见
4. **模型状态**：绿色「所有必需模型已就绪」显示在模型列表和按钮之间

---

## 十四、微调修正（2026-06-15）

> 三次审查方案实施后，按钮已可见，但仍有两处微调。

---

### 微调 1：API Key 容器左边缘偏移约 6px

**截图表现**：红线标出 ComboBox 左边缘位置，API Key 输入框左边缘在红线右侧约 6px。

**根因**：`api_key_container` 是 QWidget 包含内部 QHBoxLayout（QLineEdit + 32px 按钮 + 4px 间距）。Qt 根据子控件 sizeHint 计算容器最小宽度：QLineEdit 全局 QSS `padding: 8px 12px` 使 sizeHint 约 170px + 按钮 32px + 间距 4px = 容器最小宽度约 **206px**，比 ComboBox 的 200px 宽 6px。容器比 200px 宽，左边就向右偏移了。

**修复**：在 `api_key_container` 创建后设置固定宽度 200px。

```python
# settings_page.py — 在 api_key_container.setLayout(api_key_inner) 之后添加：
api_key_container.setFixedWidth(200)
```

这一行即可让 API Key 容器与其他 ComboBox 完全等宽，左边缘对齐。

---

### 微调 2：按钮高度偏小

**截图表现**：「检查模型」「下载缺失模型」和「保存设置」按钮高度看起来偏矮。

**修复**：

```python
# settings_page.py — _build_model_section 中：
# 改前
self._btn_check_models.setFixedSize(96, 32)
self._btn_download_models.setFixedSize(120, 32)

# 改后
self._btn_check_models.setFixedSize(96, 36)
self._btn_download_models.setFixedSize(120, 36)

# settings_page.py — _build 方法中保存按钮：
# 改前
save_btn.setFixedSize(148, 36)

# 改后
save_btn.setFixedSize(148, 40)
```

---

## 十五、四次审查——API Key 对齐终极修复 + 删除多余分隔线（2026-06-15）

> 三次审查方案中 `setFixedWidth(200)` 导致 API Key 输入框变得很短，且对齐仍未解决。本次找到真正根因。

---

### 问题 A：API Key 左边缘偏移（终极修复）

**真正根因**：Qt 的 `setLayout()` 会给 layout 自动添加默认 contentsMargins（Windows 平台通常为 9-11px）。

当前代码第 229-234 行：
```python
api_key_inner = QHBoxLayout()
api_key_inner.setSpacing(4)
api_key_inner.addWidget(self._api_key_entry, 1)
api_key_inner.addWidget(self._api_key_toggle)
api_key_container = QWidget()
api_key_container.setLayout(api_key_inner)   # ← Qt 自动给 api_key_inner 加了约 9px 的左右 margin！
```

`api_key_inner` 被 setLayout 到 QWidget 上后，Qt 自动设了 `contentsMargins(9, 9, 9, 9)`。这导致容器内部的 QLineEdit 不是从容器左边缘开始，而是向右偏移了 9px。这就是为什么 API Key 输入框的左边缘始终比其他 ComboBox 偏右。

**修复**：在 `api_key_inner` 创建后立即设置零边距，同时删除 `setFixedWidth(200)` 让容器自然宽度。

```python
# settings_page.py 第 229-237 行
# 改前
api_key_inner = QHBoxLayout()
api_key_inner.setSpacing(4)
api_key_inner.addWidget(self._api_key_entry, 1)
api_key_inner.addWidget(self._api_key_toggle)
api_key_container = QWidget()
api_key_container.setLayout(api_key_inner)
api_key_container.setStyleSheet("background: transparent; border: none;")
api_key_container.setFixedWidth(200)          # ← 删除此行
self._form_row(group, "API Key", api_key_container)

# 改后
api_key_inner = QHBoxLayout()
api_key_inner.setContentsMargins(0, 0, 0, 0)  # ← 关键！去掉 Qt 默认的 9px margin
api_key_inner.setSpacing(4)
api_key_inner.addWidget(self._api_key_entry, 1)
api_key_inner.addWidget(self._api_key_toggle)
api_key_container = QWidget()
api_key_container.setLayout(api_key_inner)
api_key_container.setStyleSheet("background: transparent; border: none;")
# 不设 setFixedWidth，让容器按内容自然宽度（和路径行行为一致）
self._form_row(group, "API Key", api_key_container)
```

加一行 `setContentsMargins(0, 0, 0, 0)` 即可彻底解决对齐问题。删除 `setFixedWidth(200)` 避免输入框变得很短。

---

### 问题 B：转写引擎和 AI 增强之间出现多余分隔线

**截图表现**：
- 转写引擎卡片内，「转写模式」和「标点恢复」之间有一条水平分隔线
- AI 增强卡片内，「接入模式」（含提示文字）和「本地 LLM」之间有一条水平分隔线

这两条分隔线在原型图中不存在，应删除。

**修复 1：删除转写引擎分隔线**

```python
# settings_page.py 第 149-152 行 — 删除以下 4 行
sep = QFrame()
sep.setFixedHeight(1)
sep.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
group.layout().addWidget(sep)
```

**修复 2：删除 AI 增强分隔线**

```python
# settings_page.py 第 246-251 行 — 删除以下 6 行
# 分隔线（接入模式和本地 LLM 之间）
sep_ai = QFrame()
sep_ai.setFixedHeight(1)
sep_ai.setStyleSheet(f"background-color: #F3F4F6; border: none;")
group.layout().addWidget(sep_ai)
group.layout().addSpacing(4)
```

---

### 修改汇总（四次审查）

| 修改 | 文件 | 行号 | 操作 |
|------|------|------|------|
| FIX-A | settings_page.py | 230 | 添加 `api_key_inner.setContentsMargins(0, 0, 0, 0)` |
| FIX-A | settings_page.py | 236 | 删除 `api_key_container.setFixedWidth(200)` |
| FIX-B1 | settings_page.py | 149-152 | 删除 sep QFrame 分隔线（4 行） |
| FIX-B2 | settings_page.py | 246-251 | 删除 sep_ai QFrame + addSpacing（6 行） |

共 3 处改动，非常简单。

---

## 十六、五次审查——API Key 下边框遮挡 + 按钮高度微调（2026-06-15）

> 四次审查后对齐问题已修复。本次修复两个残留小问题。

---

### 问题 A：API Key 输入框底部边框显示不全

**截图表现**：API Key 输入框的下框线似乎被遮挡了一点，显示不完全。而其他输入框（如转写模型、模型厂商等 ComboBox）的下边框显示正常。

**根因分析**：

QLineEdit 设置了 `setFixedHeight(32)`。但 Qt 的默认 QSS 已经给 QLineEdit 加了 `padding: 8px 12px`（来自 styles.py），加上 1px border 和 border-radius: 6px。计算实际需要的高度：

- padding-top: 8px
- 内容行高: ~16px
- padding-bottom: 8px
- border-top: 1px
- border-bottom: 1px
- **总计: 34px**

但 `setFixedHeight(32)` 强制高度为 32px，不够 34px。Qt 会裁剪底部 2px 的渲染区域，导致底部 border 显示不全。

对比 ComboBox 没有 setFixedHeight，使用的是 styleHint 计算出的自然高度（约 36-40px），所以显示正常。

**修复方案**：删除 API Key QLineEdit 的 `setFixedHeight(32)`，让它按 QSS padding 自然计算高度。

```python
# settings_page.py — API Key QLineEdit 创建处
# 改前
self._api_key_entry = QLineEdit()
self._api_key_entry.setPlaceholderText("输入 API Key…")
self._api_key_entry.setEchoMode(QLineEdit.Password)
self._api_key_entry.setMinimumWidth(240)
self._api_key_entry.setFixedHeight(32)    # ← 删除此行

# 改后
self._api_key_entry = QLineEdit()
self._api_key_entry.setPlaceholderText("输入 API Key…")
self._api_key_entry.setEchoMode(QLineEdit.Password)
self._api_key_entry.setMinimumWidth(240)
# 不设 setFixedHeight，让 QSS padding 自动决定高度（约 36px，和 ComboBox 一致）
```

**验证方法**：删除后 API Key 输入框高度应与其他 ComboBox 对齐，底部边框完整显示。

---

### 问题 B：模型管理按钮和保存设置按钮视觉高度偏小

**截图表现**：「检查模型」「下载缺失模型」以及「保存设置」按钮在实际运行中看起来比原型设计中的按钮明显偏小。

**原型设计规格**（mockup-settings.html）：
- 普通按钮 `.btn`: `height: 32px; padding: 0 16px;`
- 保存按钮 `.btn-save`: `height: 36px; padding: 0 24px; font-size: 14px;`

**当前代码值**：
- 检查模型: `setFixedSize(96, 36)` — 高度 36px（已超过原型 32px）
- 下载缺失模型: `setFixedSize(120, 36)` — 高度 36px（已超过原型 32px）
- 保存设置: `setFixedSize(148, 40)` — 高度 40px（已超过原型 36px）

**根因分析**：虽然 setFixedSize 的数值已经超过原型，但按钮看起来仍然偏小，原因是两个因素叠加：

**因素 1：QSS 样式级联导致 padding 未被覆盖**

当前按钮的 inline stylesheet（第 315-327 行）：
```python
self._btn_check_models.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
    }}
""")
```

这段 inline QSS **没有设置 `padding`**。而全局样式（styles.py 第 148-158 行）定义了：
```css
QPushButton {
    padding: 0 16px;
    min-height: 20px;
}
```

Qt 的样式级联机制：当 widget 有自己的 stylesheet 时，未在其中指定的属性仍会从 application stylesheet 继承。因此全局的 `padding: 0 16px` 仍然作用于这些按钮。虽然 padding 只有水平方向（上下为 0），不影响高度，但说明 inline QSS 并未完全覆盖全局样式。

**因素 2：宽度不够，视觉比例失调**

原型中按钮在浏览器里渲染时，浏览器会给按钮额外的 UA 样式（如 user-agent default padding），使得 32px 的按钮在浏览器中视觉高度约 38-40px。而 Qt 严格按 setFixedSize 渲染，36px 就是 36px，没有浏览器那样的「视觉膨胀」。

加上宽度仅 96px / 120px，在宽大的卡片内显得特别矮小。

**修复方案**：增加按钮尺寸，并在 inline QSS 中显式设置 `padding` 和 `min-height` 防止全局样式干扰。

```python
# settings_page.py 第 313-327 行 — 检查模型按钮
# 改前
self._btn_check_models = QPushButton("检查模型")
self._btn_check_models.setFixedSize(96, 36)
self._btn_check_models.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {C_BTN_HOVER};
    }}
""")

# 改后
self._btn_check_models = QPushButton("检查模型")
self._btn_check_models.setFixedSize(120, 40)
self._btn_check_models.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0 16px;
        min-height: 40px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {C_BTN_HOVER};
    }}
""")
```

```python
# settings_page.py 第 332-346 行 — 下载缺失模型按钮
# 改前
self._btn_download_models = QPushButton("下载缺失模型")
self._btn_download_models.setFixedSize(120, 36)

# 改后
self._btn_download_models = QPushButton("下载缺失模型")
self._btn_download_models.setFixedSize(150, 40)
self._btn_download_models.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_SUCCESS};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0 16px;
        min-height: 40px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: #059669;
    }}
""")
```

```python
# settings_page.py 第 118-119 行 — 保存设置按钮
# 改前
save_btn.setFixedSize(148, 40)

# 改后
save_btn.setFixedSize(160, 44)
save_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0 24px;
        min-height: 44px;
        font-size: 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {C_BTN_HOVER};
    }}
""")
```

### 修改汇总（五次审查——按钮高度）

| 修改 | 文件 | 行号 | 改前 | 改后 |
|------|------|------|------|------|
| FIX-B1 | settings_page.py | 314 | `setFixedSize(96, 36)` | `setFixedSize(120, 40)` + 显式 padding/min-height |
| FIX-B2 | settings_page.py | 333 | `setFixedSize(120, 36)` | `setFixedSize(150, 40)` + 显式 padding/min-height |
| FIX-B3 | settings_page.py | 119 | `setFixedSize(148, 40)` | `setFixedSize(160, 44)` + 显式 padding/min-height + 去掉 cssClass="save" |

关键点：每个按钮的 inline QSS 必须显式设置 `padding` 和 `min-height`，防止全局 QPushButton 样式的级联覆盖。宽度也适当增加，让按钮在卡片中有更协调的视觉比例。
