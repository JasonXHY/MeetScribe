# Logo 集成指令 — MiMo Code

## 一、素材清单

已在 `C:\侧耳倾听\assets\` 下新增以下 Logo 素材：

| 文件 | 尺寸 | 用途 |
|------|------|------|
| `logo.ico` | 多尺寸 (256/128/96/64/48/32/24/16) | Windows 窗口图标、任务栏图标 |
| `logo_256x256.png` | 256×256 | 高清显示场景 |
| `logo_48x48.png` | 48×48 | 任务栏托盘图标 |
| `logo_32x32.png` | 32×32 | 桌面快捷方式、窗口标题栏 |
| `logo_16x16.png` | 16×16 | 小图标场景 |
| `logo-source.html` | SVG 源文件 | 设计源文件，可在浏览器中查看 |

旧文件 `icon.ico` 和 `icon.png` 保留作为备份，不再使用。

## 二、代码修改

### 1. 修改 `src/gui/styles.py`

将第 41-42 行的图标路径：

```python
ICON_PNG     = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO     = os.path.join(ASSETS_DIR, "icon.ico")
```

改为：

```python
ICON_PNG     = os.path.join(ASSETS_DIR, "logo_256x256.png")
ICON_ICO     = os.path.join(ASSETS_DIR, "logo.ico")
```

### 2. 确认 `src/gui/app.py` 无需修改

`app.py` 第 96 行 `self.setWindowIcon(QIcon(ICON_ICO))` 会自动引用新的 `ICON_ICO`，无需改动。

### 3. 托盘图标（如有）

如果系统托盘使用了 `ICON_PNG`，会自动指向新的 256x256 PNG。

## 三、验证

修改后运行程序确认：
1. 窗口标题栏显示新 Logo（蓝色渐变底 + 耳朵 + 声波）
2. 任务栏图标正确显示
3. 系统托盘图标正确显示
4. `alt+tab` 切换时图标正确

## 四、设计规格

- **配色**：深浅蓝渐变（#1E40AF → #2563EB → #3B82F6）
- **图形**：耳朵轮廓（#93C5FD）+ 内耳（#BFDBFE）+ 三条声波（由细到粗，1:3:6）
- **圆角**：256px 版本圆角 56px，小尺寸等比缩小
- **格式**：PNG-32（带 Alpha 通道），ICO 多尺寸打包
