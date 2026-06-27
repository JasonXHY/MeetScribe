# MiMo Code 指令：说话人列表 UI 修复（第二轮）

> **⚠️ 已废弃** — 此方案（FIX-V6~V11）未被实施，已被 `docs/mimo-voiceprint-fix-3.md`（FIX-V12~V17）完全替代。请使用第三轮方案。

> 对应文档：`docs/ui-fix-plan.md` 第十七节
> 目标文件：`src/gui/voiceprint_page.py`
> 修复内容：选中项无高亮、hover 无反馈、间距偏紧、缺少选中指示条

---

## 背景

六次审查的 FIX-V1 ~ FIX-V5 已实施，但说话人列表仍有可见 UI 问题。核心原因是 `QListWidget` + `setItemWidget()` 模式下，Qt 的 `::item:selected` / `::item:hover` QSS 无法可靠地渲染到自定义 widget 的背景上（Windows 平台层叠冲突）。

---

## 修改 1：新增 `SpeakerItemWidget` 类

在 `VoiceprintPage` 类定义之前（约第 320 行之前），新增以下类：

```python
class SpeakerItemWidget(QWidget):
    """说话人列表项自定义 widget，自行管理选中/hover 背景色"""

    def __init__(self, name, sample_count, color, parent=None):
        super().__init__(parent)
        self._selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 彩色圆形头像
        avatar = QLabel(name[0] if name else "?")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {color};
            color: white; border-radius: 16px;
            font-size: 13px; font-weight: bold;
        """)
        layout.addWidget(avatar)

        # 名字 + 样本数
        info_layout = QVBoxLayout()
        info_layout.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {C_TXT1}; font-size: 13px; font-weight: 500;"
            " background: transparent; border: none;"
        )
        info_layout.addWidget(name_lbl)
        meta_lbl = QLabel(f"{sample_count} 个样本")
        meta_lbl.setStyleSheet(
            f"color: {C_TXT3}; font-size: 11px;"
            " background: transparent; border: none;"
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
        """鼠标进入 — hover 背景"""
        if not self._selected:
            self.setStyleSheet(
                "SpeakerItemWidget {"
                " background-color: #F9FAFB;"
                " border-radius: 6px;"
                " border-left: 3px solid transparent;"
                "}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开 — 恢复"""
        if not self._selected:
            self._apply_style()
        super().leaveEvent(event)

    def _apply_style(self):
        """应用当前状态样式"""
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

## 修改 2：修改 `refresh_list()` 中的 item 创建逻辑

替换 `refresh_list()` 方法中 `for name, profile in speakers.items():` 循环体（约第 534-569 行）：

**改前**（第 534-569 行）：
```python
for name, profile in speakers.items():
    # 创建带彩色头像的自定义widget
    item_widget = QWidget()
    item_layout = QHBoxLayout(item_widget)
    item_layout.setContentsMargins(10, 10, 10, 10)
    item_layout.setSpacing(10)

    # 彩色圆形头像
    avatar = QLabel(name[0] if name else "?")
    avatar.setFixedSize(32, 32)
    avatar.setAlignment(Qt.AlignCenter)
    color_idx = hash(name) % len(SPEAKER_COLORS)
    avatar.setStyleSheet(f"""
        background-color: {SPEAKER_COLORS[color_idx]};
        color: white; border-radius: 16px;
        font-size: 13px; font-weight: bold;
    """)
    item_layout.addWidget(avatar)

    # 名字 + 样本数
    info_layout = QVBoxLayout()
    info_layout.setSpacing(1)
    name_lbl = QLabel(name)
    name_lbl.setStyleSheet(f"color: {C_TXT1}; font-size: 13px; font-weight: 500; background: transparent; border: none;")
    info_layout.addWidget(name_lbl)
    meta_lbl = QLabel(f"{len(profile.embeddings)} 个样本")
    meta_lbl.setStyleSheet(f"color: {C_TXT3}; font-size: 11px; background: transparent; border: none;")
    info_layout.addWidget(meta_lbl)
    item_layout.addLayout(info_layout)
    item_layout.addStretch()

    list_item = QListWidgetItem()
    list_item.setSizeHint(QSize(0, 52))
    list_item.setData(Qt.UserRole, name)
    self._speaker_list.addItem(list_item)
    self._speaker_list.setItemWidget(list_item, item_widget)
```

**改后**：
```python
for name, profile in speakers.items():
    color_idx = hash(name) % len(SPEAKER_COLORS)
    color = SPEAKER_COLORS[color_idx]
    sample_count = len(profile.embeddings)

    item_widget = SpeakerItemWidget(name, sample_count, color)

    list_item = QListWidgetItem()
    list_item.setSizeHint(QSize(0, 56))  # 从 52 增加到 56，增加间距
    list_item.setData(Qt.UserRole, name)
    self._speaker_list.addItem(list_item)
    self._speaker_list.setItemWidget(list_item, item_widget)
```

---

## 修改 3：修改 `_on_speaker_select()` 方法

替换 `_on_speaker_select` 方法（约第 586-591 行）：

**改前**：
```python
def _on_speaker_select(self, current, previous):
    """选中说话人"""
    if current:
        name = current.data(Qt.UserRole)
        self._selected_speaker = name
        self._show_speaker_detail(name)
```

**改后**：
```python
def _on_speaker_select(self, current, previous):
    """选中说话人"""
    # 更新上一个选中项的高亮
    if previous:
        prev_widget = self._speaker_list.itemWidget(previous)
        if prev_widget and hasattr(prev_widget, 'set_selected'):
            prev_widget.set_selected(False)
    # 更新当前选中项的高亮
    if current:
        curr_widget = self._speaker_list.itemWidget(current)
        if curr_widget and hasattr(curr_widget, 'set_selected'):
            curr_widget.set_selected(True)
        name = current.data(Qt.UserRole)
        self._selected_speaker = name
        self._show_speaker_detail(name)
```

---

## 修改 4：修改 QListWidget 样式

替换 `_speaker_list` 的样式表（约第 426-444 行）：

**改前**：
```python
self._speaker_list = QListWidget()
self._speaker_list.setStyleSheet(f"""
    QListWidget {{
        background: transparent; border: none;
        font-family: {FONT_FAMILY}; font-size: 12px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 10px 12px;
        border-radius: 6px;
        margin: 0 4px 2px 4px;
        border: none;
    }}
    QListWidget::item:selected {{
        background-color: {C_ACCENT_LT}; color: {C_TXT1};
    }}
    QListWidget::item:hover {{
        background-color: #F9FAFB;
    }}
""")
```

**改后**：
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
        margin: 1px 4px 1px 4px;
        border: none;
    }}
    QListWidget::item:selected {{
        background-color: transparent;
        color: {C_TXT1};
    }}
    QListWidget::item:hover {{
        background-color: transparent;
    }}
""")
```

关键点：`::item:selected` 和 `::item:hover` 都改为 `transparent`，把背景色管理权完全交给 `SpeakerItemWidget`，避免 Qt 层叠冲突。

---

## 改动汇总

| 序号 | 修改内容 | 位置 |
|------|---------|------|
| 1 | 新增 `SpeakerItemWidget` 类 | VoiceprintPage 之前，约第 320 行 |
| 2 | `refresh_list()` 使用新 widget | 第 534-569 行 |
| 3 | `_on_speaker_select()` 更新高亮 | 第 586-591 行 |
| 4 | QListWidget CSS 改为 transparent | 第 426-444 行 |

总共修改 4 处，新增约 50 行代码，无需修改其他文件。
