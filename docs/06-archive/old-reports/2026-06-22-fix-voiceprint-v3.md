# MiMo Code 指令：音色库页 + 发言人管理 UI 终极修复（第三轮）

> 对应文档：`docs/ui-fix-plan.md` 第十九节
> 目标文件：`src/gui/voiceprint_page.py` + `src/gui/dialogs.py`
> 修复编号：FIX-V12 ~ FIX-V17（音色库页）+ FIX-D7 ~ FIX-D12（发言人管理对话框）
> **此方案完全替代第二轮 FIX-V6~V11 和八次审查 FIX-D1~D6**

---

## 背景

第二轮审查（FIX-V6~V11）和八次审查（FIX-D1~D6）的方案均未被实施。当前代码仍为原始状态，存在以下问题：

**音色库页（voiceprint_page.py）**：
1. `setItemWidget()` + `::item:selected` QSS 在 Windows 上层叠冲突，选中高亮不可见
2. `::item` QSS padding 与 widget margins 双重叠加
3. sizeHint 偏紧
4. hover 无反馈、无选中指示条、点击 widget 空白区域无法选中

**发言人管理对话框（dialogs.py）**：
1. 对话框宽度 540px 太窄，每行元素被严重挤压
2. "接受"按钮 40×20px + **全局 QPushButton padding 未覆盖**，文字完全不可见
3. "保存到音色库"按钮 100px 偏小，文字被截断
4. 行内间距 6px 过紧，音色库下拉框 140px 偏小

---

## 修改 1：新增 `SpeakerItemWidget` 类

在 `VoiceprintPage` 类定义之前（`class VoiceprintPage(QWidget):` 之前），新增以下完整类定义。**直接复制，不要修改**：

```python
class SpeakerItemWidget(QWidget):
    """说话人列表项 — 自管理选中/hover 背景色，绕过 Qt setItemWidget QSS 冲突"""

    clicked = Signal()  # 点击信号

    def __init__(self, name, sample_count, color, parent=None):
        super().__init__(parent)
        self._selected = False
        self._name = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 彩色圆形头像
        avatar = QLabel(name[0] if name else "?")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white; border-radius: 16px;
                font-size: 13px; font-weight: bold;
            }}
        """)
        layout.addWidget(avatar)

        # 名字 + 样本数
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"QLabel {{ color: {C_TXT1}; font-size: 13px; font-weight: 500;"
            " background: transparent; border: none; }}"
        )
        info_layout.addWidget(name_lbl)
        meta_lbl = QLabel(f"{sample_count} 个样本")
        meta_lbl.setStyleSheet(
            f"QLabel {{ color: {C_TXT3}; font-size: 11px;"
            " background: transparent; border: none; }}"
        )
        info_layout.addWidget(meta_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()

        self._apply_style()

    def set_selected(self, selected):
        """切换选中状态"""
        if self._selected != selected:
            self._selected = selected
            self._apply_style()

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet("""
                SpeakerItemWidget {
                    background-color: #F9FAFB;
                    border-radius: 6px;
                }
            """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._selected:
            self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """点击时发送选中信号"""
        self.clicked.emit()
        super().mousePressEvent(event)

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                SpeakerItemWidget {{
                    background-color: {C_ACCENT_LT};
                    border-radius: 6px;
                    border-left: 3px solid {C_ACCENT};
                }}
            """)
        else:
            self.setStyleSheet("""
                SpeakerItemWidget {
                    background-color: transparent;
                    border-radius: 6px;
                    border-left: 3px solid transparent;
                }
            """)
```

---

## 修改 2：修改 QListWidget 样式表

找到 `_build()` 方法中的 `self._speaker_list = QListWidget()` 及其后续的 `setStyleSheet` 调用（约第 425-444 行），**整段替换**为：

```python
self._speaker_list = QListWidget()
self._speaker_list.setStyleSheet(f"""
    QListWidget {{
        background: transparent; border: none;
        font-family: {FONT_FAMILY}; font-size: 12px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 0px;
        border-radius: 6px;
        margin: 1px 4px;
        border: none;
        background: transparent;
    }}
    QListWidget::item:selected {{
        background: transparent;
        color: {C_TXT1};
    }}
    QListWidget::item:hover {{
        background: transparent;
    }}
""")
```

**关键变化**：
- `::item` 的 `padding` 从 `10px 12px` → `0px`（由 SpeakerItemWidget 内部管理）
- `::item:selected` 和 `::item:hover` 的 `background-color` 全部改为 `transparent`
- `::item` 增加 `background: transparent`

---

## 修改 3：替换 `refresh_list()` 中的循环体

找到 `refresh_list()` 方法中的 `for name, profile in speakers.items():` 循环（约第 534-569 行），**将整个循环体替换**为：

```python
for name, profile in speakers.items():
    color_idx = hash(name) % len(SPEAKER_COLORS)
    color = SPEAKER_COLORS[color_idx]
    sample_count = len(profile.embeddings)

    item_widget = SpeakerItemWidget(name, sample_count, color)

    list_item = QListWidgetItem()
    list_item.setSizeHint(QSize(0, 56))
    list_item.setData(Qt.UserRole, name)
    self._speaker_list.addItem(list_item)
    self._speaker_list.setItemWidget(list_item, item_widget)

    # 点击 widget 时自动选中对应 item
    item_widget.clicked.connect(
        lambda item=list_item: self._speaker_list.setCurrentItem(item)
    )
```

**替换范围**：从 `for name, profile in speakers.items():` 到 `self._speaker_list.setItemWidget(list_item, item_widget)` 这整个循环体（约 36 行代码）。

**注意**：`total_samples` 和后续代码保持不变。

---

## 修改 4：修改 `_on_speaker_select()` 方法

找到 `_on_speaker_select` 方法（约第 586-591 行），**整个方法替换**为：

```python
def _on_speaker_select(self, current, previous):
    """选中说话人 — 更新高亮状态"""
    # 取消上一个选中项的高亮
    if previous:
        prev_widget = self._speaker_list.itemWidget(previous)
        if prev_widget and hasattr(prev_widget, 'set_selected'):
            prev_widget.set_selected(False)
    # 设置当前选中项的高亮
    if current:
        curr_widget = self._speaker_list.itemWidget(current)
        if curr_widget and hasattr(curr_widget, 'set_selected'):
            curr_widget.set_selected(True)
        name = current.data(Qt.UserRole)
        self._selected_speaker = name
        self._show_speaker_detail(name)
```

---

## 修改汇总

| 序号 | 修改内容 | 位置 | 替换行数 |
|------|---------|------|----------|
| 1 | 新增 `SpeakerItemWidget` 类 | `class VoiceprintPage` 之前 | 新增约 70 行 |
| 2 | QListWidget 样式全 transparent | `_build()` 中，约第 425-444 行 | 替换约 20 行 |
| 3 | `refresh_list()` 使用 SpeakerItemWidget | `refresh_list()` 中，约第 534-569 行 | 替换约 36 行 |
| 4 | `_on_speaker_select()` 高亮管理 | 约第 586-591 行 | 替换约 6 行 |

**总计**：4 处修改，新增约 70 行，替换约 62 行。

---

# 第二部分：发言人管理对话框修复（dialogs.py）

> 修复编号：FIX-D7 ~ FIX-D12
> 目标文件：`src/gui/dialogs.py`
> ⚠️ **关键发现**：全局 QPushButton 样式（`styles.py`）定义了 `padding: 0 16px`，此值会被所有未在本地 stylesheet 中显式设置 `padding` 的按钮继承。这是"接受"按钮文字不可见的隐藏根因。

---

## 修改 5：对话框最小宽度 + 初始尺寸（FIX-D7）

找到 `SpeakerDialog.__init__` 中的 `setMinimumSize`（约第 331 行）：

**改前**：
```python
self.setMinimumSize(540, 600)
```

**改后**：
```python
self.setMinimumSize(820, 560)
self.resize(900, 600)
```

---

## 修改 6：布局边距和间距（FIX-D8）

找到 `SpeakerDialog._build()` 中的布局设置（约第 348-349 行）：

**改前**：
```python
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(12)
```

**改后**：
```python
layout.setContentsMargins(20, 20, 20, 20)
layout.setSpacing(14)
```

---

## 修改 7："接受"按钮（FIX-D9）— 最高优先级

找到 `_add_match_suggestion()` 方法中的 accept_btn（约第 622-627 行），**整段替换**：

**改前**：
```python
accept_btn = QPushButton("接受")
accept_btn.setFixedSize(40, 20)
accept_btn.setStyleSheet(f"""
    QPushButton {{ background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 3px; font-size: 10px; }}
""")
```

**改后**：
```python
accept_btn = QPushButton("接受")
accept_btn.setFixedSize(60, 28)
accept_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 4px; font-size: 12px;
        padding: 0 8px;
        min-height: 0px;
    }}
""")
```

**⚠️ 关键**：必须显式设置 `padding: 0 8px;` 和 `min-height: 0px;`，否则会继承全局 QPushButton 的 `padding: 0 16px` 和 `min-height: 20px`，导致文字再次被裁剪。

---

## 修改 8："保存到音色库"按钮（FIX-D10）

找到 `_refresh_speaker_list()` 中的 save_btn（约第 519-524 行），**整段替换**：

**改前**：
```python
save_btn = QPushButton("保存到音色库")
save_btn.setFixedSize(100, 28)
save_btn.setStyleSheet(f"""
    QPushButton {{ background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 4px; font-size: 11px; }}
""")
```

**改后**：
```python
save_btn = QPushButton("保存到音色库")
save_btn.setFixedSize(120, 28)
save_btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 4px; font-size: 12px;
        padding: 0 10px;
        min-height: 0px;
    }}
""")
```

---

## 修改 9：行内间距 + 音色库下拉框（FIX-D11）

**9a. 行内间距**（约第 466 行）：

**改前**：
```python
row.setSpacing(6)
```

**改后**：
```python
row.setSpacing(10)
```

**9b. 音色库下拉框**（约第 496-508 行），**整段替换**：

**改前**：
```python
combo.setFixedWidth(140)
combo.setStyleSheet(f"""
    QComboBox {{
        border: 1px solid {C_BORDER}; border-radius: 4px;
        padding: 2px 4px; font-family: {FONT_FAMILY}; font-size: 11px;
        background-color: {C_BG};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
    }}
""")
```

**改后**：
```python
combo.setFixedWidth(150)
combo.setStyleSheet(f"""
    QComboBox {{
        border: 1px solid {C_BORDER}; border-radius: 4px;
        padding: 2px 6px; font-family: {FONT_FAMILY}; font-size: 12px;
        background-color: {C_BG};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
    }}
""")
```

---

## 修改 10：建议标签样式（FIX-D12）

找到 `_add_match_suggestion()` 中的 suggestion_label（约第 618-619 行）：

**改前**：
```python
suggestion_label = QLabel(f"可能是 {matched_name} ({confidence_pct}%)")
suggestion_label.setStyleSheet(f"color: #0067C0; font-size: 11px;")
```

**改后**：
```python
suggestion_label = QLabel(f"可能是 {matched_name} ({confidence_pct}%)")
suggestion_label.setStyleSheet(f"QLabel {{ color: {C_ACCENT}; font-size: 12px; font-weight: 500; }}")
```

---

## 全部修改汇总

| 序号 | 修改内容 | 文件 | 位置 |
|------|---------|------|------|
| 1 | 新增 `SpeakerItemWidget` 类 | voiceprint_page.py | `class VoiceprintPage` 之前 |
| 2 | QListWidget 样式全 transparent | voiceprint_page.py | `_build()` 约第 425-444 行 |
| 3 | `refresh_list()` 使用 SpeakerItemWidget | voiceprint_page.py | 约第 534-569 行 |
| 4 | `_on_speaker_select()` 高亮管理 | voiceprint_page.py | 约第 586-591 行 |
| 5 | 对话框最小宽度 820px | dialogs.py | 约第 331 行 |
| 6 | 布局边距和间距 | dialogs.py | 约第 348-349 行 |
| 7 | "接受"按钮 60×28 + padding 覆盖 | dialogs.py | 约第 622-627 行 |
| 8 | "保存到音色库"按钮 120px + padding 覆盖 | dialogs.py | 约第 519-524 行 |
| 9 | 行间距 10px + 下拉框 150px | dialogs.py | 约第 466, 496-508 行 |
| 10 | 建议标签样式 | dialogs.py | 约第 618-619 行 |

**总计**：2 个文件，10 处修改。

---

## 验证清单

**音色库页（voiceprint_page.py）**：
- [ ] 说话人列表每项显示：彩色头像 + 姓名 + "N 个样本" 副标题
- [ ] 选中某一项时，背景变为浅蓝色 (#EFF6FF)，左侧有 3px 蓝色指示条
- [ ] 切换选中项时，旧项高亮消失，新项高亮出现
- [ ] 鼠标悬停在非选中项上时，背景变为浅灰色 (#F9FAFB)
- [ ] 鼠标离开时，背景恢复透明
- [ ] 点击 item 的任意区域（包括 widget 空白处）都能选中该项
- [ ] 列表项间距合理，不拥挤也不过分稀疏
- [ ] 右侧详情面板正常显示选中说话人的信息

**发言人管理对话框（dialogs.py）**：
- [ ] 对话框打开时宽度约 900px，所有元素完整可见
- [ ] 拉宽/缩窄对话框时，"接受"按钮始终显示完整文字"接受"
- [ ] "保存到音色库"按钮显示完整文字，不被截断
- [ ] 每行元素（色标、标签、输入框、建议、按钮、下拉框、百分比）间距合理
- [ ] 音色库下拉框能完整显示 "(从音色库选择)" 文字
- [ ] 建议标签 "可能是 XX (NN%)" 文字清晰可读
