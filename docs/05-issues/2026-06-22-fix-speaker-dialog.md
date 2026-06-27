# MiMo Code 指令：发言人管理对话框 UI 修复

> **⚠️ 已废弃** — 此方案（FIX-D1~D6）未被实施，已被 `docs/mimo-voiceprint-fix-3.md`（FIX-D7~D12）完全替代。请使用第三轮方案。

> 对应文档：`docs/ui-fix-plan.md` 第十八节
> 目标文件：`src/gui/dialogs.py`
> 修复内容：对话框太小、"接受"按钮不可见、"保存到音色库"截断、行间距过紧

---

## 修改 1：对话框最小尺寸

**位置**：`SpeakerDialog.__init__()` 第 320 行

**改前**：
```python
self.setMinimumSize(540, 600)
```

**改后**：
```python
self.setMinimumSize(800, 560)
self.resize(880, 600)
```

---

## 修改 2：布局边距和间距

**位置**：`SpeakerDialog._build()` 第 337-338 行

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

## 修改 3："接受"按钮尺寸和字号

**位置**：`SpeakerDialog._add_match_suggestion()` 第 611-616 行

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
accept_btn.setFixedSize(56, 26)
accept_btn.setStyleSheet(f"""
    QPushButton {{ background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 4px; font-size: 12px;
        padding: 2px 8px; }}
""")
```

---

## 修改 4："保存到音色库"按钮宽度

**位置**：`SpeakerDialog._refresh_speaker_list()` 第 508-513 行

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
    QPushButton {{ background-color: {C_ACCENT}; color: white;
        border: none; border-radius: 4px; font-size: 12px;
        padding: 4px 12px; }}
""")
```

---

## 修改 5：行内元素间距

**位置**：`SpeakerDialog._refresh_speaker_list()` 第 455 行

**改前**：
```python
row.setSpacing(6)
```

**改后**：
```python
row.setSpacing(10)
```

---

## 修改 6：音色库下拉框宽度和字号

**位置**：`SpeakerDialog._refresh_speaker_list()` 第 485 行和第 486-497 行

**改前**：
```python
combo.setFixedWidth(140)
combo.setStyleSheet(f"""
    QComboBox {{
        border: 1px solid {C_BORDER}; border-radius: 4px;
        padding: 2px 4px; font-family: {FONT_FAMILY}; font-size: 11px;
        background-color: {C_BG};
    }}
    ...
""")
```

**改后**：
```python
combo.setFixedWidth(150)
combo.setStyleSheet(f"""
    QComboBox {{
        border: 1px solid {C_BORDER}; border-radius: 4px;
        padding: 4px 8px; font-family: {FONT_FAMILY}; font-size: 12px;
        background-color: {C_BG};
    }}
    ...
""")
```

---

## 改动汇总

| 序号 | 修改内容 | 位置 |
|------|---------|------|
| 1 | 对话框最小尺寸 540→800，初始 resize(880,600) | 第 320 行 |
| 2 | 布局 margins 16→20，spacing 12→14 | 第 337-338 行 |
| 3 | "接受"按钮 40×20→56×26，字号 10→12px | 第 611-616 行 |
| 4 | "保存到音色库"按钮宽度 100→120，字号 11→12px | 第 508-513 行 |
| 5 | 行内 spacing 6→10 | 第 455 行 |
| 6 | 下拉框宽度 140→150，字号 11→12px | 第 485-497 行 |

总共修改 6 处，全部在 `dialogs.py` 一个文件中。
