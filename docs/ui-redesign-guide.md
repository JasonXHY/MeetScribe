# 侧耳倾听 UI 重新设计方案

> 版本：v1.1
> 日期：2026-06-14
> 作者：QoderWork（设计）+ MiMo Code（实施）
> 状态：待实施
> 更新：v1.1 新增 Lucide 统一图标系统 + 文件表格列宽优化

---

## 一、背景与目标

### 1.1 为什么重新设计

从 customtkinter 迁移到 PySide6 后，现有 UI 存在三类系统性问题：

| 问题类别 | 根因 | 影响范围 |
|----------|------|----------|
| **布局引擎差异** | customtkinter `grid` 全局共享列权重 vs PySide6 每行独立 `QHBoxLayout` | 文件列表列对齐错位 |
| **框架特性差异** | CSS border 三角 trick 在 Qt QSS 中不生效 | ComboBox 箭头显示为方块 |
| **逻辑遗漏** | `USER_FRIENDLY_KEYWORDS` 定义了但三个入口都没调用 | 日志过滤不工作 |

修补这些根本性问题的成本接近重写，因此选择 **方案 B：基于 PySide6 完全重新设计 UI**。

### 1.2 设计目标

- 遵循 Windows 11 Fluent Design 风格
- 信息密度适中，专业但不冰冷
- 核心操作（录音→转写→查看结果）不超过 3 次点击
- 所有状态可见、错误可恢复
- 代码层面使用 PySide6 原生布局，不手动拼接

### 1.3 分工

| 角色 | 职责 |
|------|------|
| **QoderWork** | UI 设计、设计规范、HTML Mockup、实施指南 |
| **MiMo Code** | PySide6 代码实施、测试、GitHub 维护 |

---

## 二、设计规范

### 2.1 色彩系统

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg` | `#F8F9FA` | 页面背景 |
| `--surface` | `#FFFFFF` | 卡片/面板背景 |
| `--surface-hover` | `#F3F4F6` | 卡片 hover |
| `--border` | `#E5E7EB` | 边框/分隔线 |
| `--border-focus` | `#3B82F6` | 聚焦边框 |
| `--text-primary` | `#111827` | 标题/主要文字 |
| `--text-secondary` | `#6B7280` | 辅助文字/标签 |
| `--text-tertiary` | `#9CA3AF` | 占位符/禁用 |
| `--text-inverse` | `#FFFFFF` | 深色背景上的文字 |
| `--accent` | `#3B82F6` | 主操作按钮/链接/选中态 |
| `--accent-hover` | `#2563EB` | 主操作 hover |
| `--accent-light` | `#EFF6FF` | 选中行背景 |
| `--success` | `#10B981` | 成功/完成/下载 |
| `--warning` | `#F59E0B` | 警告/暂停 |
| `--error` | `#EF4444` | 错误/删除/录音按钮 |
| `--purple` | `#8B5CF6` | AI 摘要按钮 |

状态色映射：

```python
STATUS_COLORS = {
    "pending":    "#9CA3AF",  # 灰色
    "processing": "#3B82F6",  # 蓝色
    "done":       "#10B981",  # 绿色
    "failed":     "#EF4444",  # 红色
}
```

### 2.2 字体系统

```python
FONT_BODY = "Microsoft YaHei, Segoe UI, sans-serif"
FONT_MONO = "Cascadia Code, Consolas, monospace"
```

字号层级：

| 级别 | 大小 | 字重 | 用途 |
|------|------|------|------|
| Display | 24px | 700 | 页面标题 |
| Title | 16px | 600 | 卡片标题 |
| Body | 13px | 400 | 正文/控件文字 |
| Caption | 12px | 400 | 辅助说明/表单标签 |
| Small | 11px | 400 | 注释/状态文字/表头 |
| Tiny | 10px | 400 | 版本号 |

### 2.3 间距系统（4px 基数）

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-1` | 4px | 最小间距 |
| `--space-2` | 8px | 紧凑间距 |
| `--space-3` | 12px | 标准间距 |
| `--space-4` | 16px | 卡片内 padding |
| `--space-5` | 20px | 卡片间距 |
| `--space-6` | 24px | 页面边距 |

### 2.4 圆角系统

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 4px | 小按钮/标签 |
| `--radius-md` | 6px | 输入框/下拉框/按钮 |
| `--radius-lg` | 8px | 卡片/面板 |
| `--radius-xl` | 12px | 弹窗 |

### 2.5 组件规范

#### 按钮

| 类型 | 背景 | 文字 | 高度 | 圆角 | 用途 |
|------|------|------|------|------|------|
| Primary | `--accent` | 白色 | 32px | 6px | 主操作 |
| Danger | `--error` | 白色 | 32px | 6px | 录音/删除 |
| Success | `--success` | 白色 | 32px | 6px | 开始转写/下载 |
| Purple | `--purple` | 白色 | 32px | 6px | AI 摘要 |
| Secondary | 透明+边框 | `--text-secondary` | 32px | 6px | 次要操作 |
| Icon | 透明 | `--text-secondary` | 28x28 | 4px | 图标按钮 |

所有同级按钮统一 font-weight 和高度，按钮组间距 8px。

#### 输入框

- 高度 32px，padding 0 12px
- 边框 1px solid `--border`，圆角 6px
- 聚焦边框色 `--border-focus`

#### ComboBox

- 高度 32px，padding 0 28px 0 12px
- **箭头必须用 SVG data URI 小三角**（不使用 CSS border trick）
- 背景 `#F9FAFB`，hover `#F3F4F6`

#### CheckBox

- 尺寸 16x16px
- 选中态用 `QPainter` 画白色对勾 + `--accent` 背景

#### Card

- 背景白色，边框 1px solid `--border`，圆角 8px，padding 16px

#### FormRow

- 标签固定宽度 100px，右对齐，颜色 `--text-secondary`
- 使用 `QFormLayout` 实现自动对齐，**不要用手动 QHBoxLayout 拼接**

### 2.6 图标系统（Lucide 统一风格）

**v1.1 更新：采用 Lucide Icons 作为统一图标库。**

Lucide 是开源线性图标集（ISC 许可证），特点是：
- 统一 24x24 网格，2px 描边
- 线性风格，干净专业
- 覆盖 1000+ 图标，风格完全一致

**图标模块位置**：`src/gui/icons.py`

**使用方式**：

```python
from gui.icons import (
    icon_play, icon_preview, icon_open_folder,
    icon_speaker, icon_retry, icon_export, icon_delete,
    icon_api_key_visible, icon_api_key_hidden,
    icon_status_done, icon_status_failed,
    icon_status_pending, icon_status_processing,
    icon_ai_summary, icon_merge, icon_add, icon_search, icon_save,
    create_icon,  # 自定义图标
    IconColors,    # 颜色常量
)

# 使用便捷函数
btn.setIcon(icon_play())                    # 绿色播放图标
btn.setIcon(icon_preview())                 # 蓝色预览图标
btn.setIcon(icon_delete())                  # 红色删除图标

# 自定义颜色
btn.setIcon(icon_play(IconColors.PRIMARY))  # 蓝色播放图标

# 使用通用函数
icon = create_icon("sparkles", "#8B5CF6", 16)  # 紫色 AI 图标
```

**完整图标列表**：

| 图标名 | 便捷函数 | 用途 | 默认颜色 |
|--------|---------|------|---------|
| play | `icon_play()` | 转写按钮 | success |
| pause | `icon_pause()` | 暂停按钮 | warning |
| square | `icon_stop()` | 停止按钮 | default |
| mic | `icon_mic()` | 麦克风 | error |
| eye | `icon_preview()` / `icon_api_key_visible()` | 预览 / API Key 显示 | primary |
| eye-off | `icon_api_key_hidden()` | API Key 隐藏 | default |
| folder-open | `icon_open_folder()` | 打开文件夹 | default |
| user | `icon_speaker()` | 发言人管理 | purple |
| rotate-ccw | `icon_retry()` | 重新转写 | warning |
| download | `icon_export()` | 导出结果 | primary |
| trash-2 | `icon_delete()` | 删除 | error |
| check-circle | `icon_status_done()` | 完成状态 | success |
| x-circle | `icon_status_failed()` | 失败状态 | error |
| circle | `icon_status_pending()` | 待处理状态 | disabled |
| loader | `icon_status_processing()` | 处理中状态 | primary |
| sparkles | `icon_ai_summary()` | AI 摘要 | purple |
| merge | `icon_merge()` | 合并转写 | default |
| plus | `icon_add()` | 添加按钮 | default |
| search | `icon_search()` | 搜索 | default |
| save | `icon_save()` | 保存 | default |
| check | - | CheckBox 对勾 | white |
| chevron-down | - | ComboBox 箭头 | default |

**技术实现**：
- 使用 `QSvgRenderer` 将 SVG 数据渲染为 `QPixmap`
- 再封装为 `QIcon`，支持多 DPI
- 所有图标内嵌在 `icons.py` 中，无需外部文件

### 2.7 动效规范

| 交互 | 动效 | 时长 |
|------|------|------|
| 按钮 hover | 背景色过渡 | 150ms |
| 按钮 pressed | 背景色变深 | 50ms |
| 列表项选中 | 背景色渐变 | 100ms |
| 录音指示点闪烁 | opacity 循环 | 1000ms |

---

## 三、页面布局

### 3.1 主页

```
┌─────────────────────────────────────────┐
│ [TopBar - 44px]                          │
├─────────────────────────────────────────┤
│ 主页                          共 N 个文件 │
├─────────────────────────────────────────┤
│ [录音控制栏 - 56px]                      │
│ ● 状态  模式▼  计时器  录音/暂停/停止    │
├─────────────────────────────────────────┤
│ [工具栏]                                 │
│ 添加文件 | 开始转写 | AI摘要 | 合并 | ... │
├─────────────────────────────────────────┤
│ QGridLayout:                            │
│ 队列 | 文件名 | 主题 | 时长 | 大小 | 状态 │ 操作 │
│   1  │ file.wav │      │ 03:00│ 1MB │ ✓  │ ▶   │
├─────────────────────────────────────────┤
│ [运行日志 - 120px 固定高度]               │
│ [09:30] 录音已开始                       │
└─────────────────────────────────────────┘
```

### 3.2 设置页

```
┌─────────────────────────────────────────┐
│ 设置                                     │
├─────────────────────────────────────────┤
│ ┌─ 存储路径 ─────────────────────────┐  │
│ │ QFormLayout:                        │  │
│ │ 录音保存目录  [___________] [浏览] │  │
│ │ 转写输出目录  [___________] [浏览] │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ 转写引擎 ─────────────────────────┐  │
│ │ QFormLayout:                        │  │
│ │ 标点恢复    [自动 (ct-punc)  ▼]    │  │
│ │ 乱码过滤    [开启 (中文模式) ▼]    │  │
│ │ VAD 灵敏度  [适中 (推荐)     ▼]    │  │
│ │ 运算设备    [CPU             ▼]    │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ AI 增强 ──────────────────────────┐  │
│ │ QFormLayout:                        │  │
│ │ 模型厂商    [小米             ▼]   │  │
│ │ 摘要模型    [mimo-v2.5-pro   ▼]   │  │
│ │ API Key     [•••••••••••] 👁       │  │
│ │ 接入模式    [按量计费         ▼]   │  │
│ │   Token Plan=包月 | 按量=按用量    │  │
│ │ 本地 LLM    [关闭             ▼]   │  │
│ │ 自动摘要    [转写后自动生成   ▼]   │  │
│ │ 转写纠错    [关闭             ▼]   │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ 模型管理 ─────────────────────────┐  │
│ │ 模型缓存: C:\...\models_cache      │  │
│ │ SenseVoice  语音识别模型  368M 已缓存│  │
│ │ CAM++       说话人识别模型 800M 已缓存│ │
│ │ [检查模型]  [下载缺失模型]          │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ 音频设备 ─────────────────────────┐  │
│ │ ☑ 使用 VB-Audio Cable（推荐）      │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ 通知 ─────────────────────────────┐  │
│ │ ☑ 启用系统通知                     │  │
│ └────────────────────────────────────┘  │
│                                         │
│ ┌─ 关于 ─────────────────────────────┐  │
│ │ 侧耳倾听 v1.0 — 本地会议录音转写助手│  │
│ │ 制作者：刘家诚                      │  │
│ │ 引擎: FunASR SenseVoice + CAM++    │  │
│ │ AI: 支持国内主流云端模型厂商        │  │
│ │ 支持格式: WAV/MP3/M4A/FLAC/OGG     │  │
│ └────────────────────────────────────┘  │
│                                         │
│           [保存设置]                     │
└─────────────────────────────────────────┘
```

### 3.3 音色库页

```
┌─────────────────────────────────────────┐
│ 音色库管理                     [+添加音色]│
├──────────────────┬──────────────────────┤
│ 说话人列表        │ 详情                  │
│ [搜索框]          │                      │
│ ┌──────────────┐ │ 张三    [编辑][删除] │
│ │ 👤 张三      │ │ ─────────────────     │
│ │   3个样本    │ │ 基本信息              │
│ │──────────────│ │ 样本数    3           │
│ │ 👤 李四      │ │ 创建时间  2026-06-14  │
│ │   1个样本    │ │ 平均质量  0.90        │
│ └──────────────┘ │ ─────────────────     │
│                   │ 声纹样本              │
│                   │ 样本1  录音  质量:0.92│
│                   │ 样本2  录音  质量:0.88│
├──────────────────┴──────────────────────┤
│ 共 2 个说话人，4 个样本                   │
└─────────────────────────────────────────┘
```

### 3.4 添加音色弹窗

```
┌─────────────────────────────┐
│ 添加新说话人                  │
│ 录音朗读以下文本，系统将自动  │
│ 提取声纹                      │
├─────────────────────────────┤
│ 说话人姓名                    │
│ [请输入姓名           ]      │
│                             │
│ ┌─ 请朗读以下文本 ────────┐ │
│ │ 你好，我是{姓名}，      │ │
│ │ 这是我的声纹样本。      │ │
│ │ ─────────────────────── │ │
│ │ ● 准备就绪              │ │
│ └─────────────────────────┘ │
│                             │
│ [开始录音]  [保存]    [取消] │
└─────────────────────────────┘
```

---

## 四、HTML Mockup 文件

以下 Mockup 文件可直接在浏览器中预览，作为 PySide6 实施的视觉参考：

| 页面 | 文件路径 | 说明 |
|------|---------|------|
| 主页 | `mockup-home.html` | 含录音栏、文件表格、日志区 |
| 设置页 | `mockup-settings.html` | 含所有设置分组 |
| 音色库页 | `mockup-voiceprint.html` | 含添加音色弹窗 |

Mockup 文件位于 `C:\MeetScribe\docs\redesign\` 目录下。

---

## 五、MiMo Code 实施指南

### 5.1 必须遵守的 7 条规则

1. **布局用 QFormLayout**（设置页表单）或 **QGridLayout**（文件列表），**不要用 QHBoxLayout 手动拼接**
2. **所有图标用 QIcon + QPainter**，不要用 emoji
3. **ComboBox 箭头用 SVG data URI**，不要用 CSS border 三角
4. **CheckBox 选中态用 QPainter** 画对勾，不要用 SVG data URI
5. **全局样式写在 styles.py** 的 `MAIN_STYLESHEET` 中，不要写 inline style
6. **同级按钮统一 font-weight 和高度**
7. **日志过滤**：`USER_FRIENDLY_KEYWORDS` 必须在 `_log()`、`_append_log()` 和 `GUILogHandler._poll_queue()` 中使用

### 5.2 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `icons.py` | **新增** | Lucide 统一图标模块（基于 SVG + QSvgRenderer） |
| `styles.py` | **重写** | 新色彩系统 + 全局 QSS |
| `file_list_view.py` | **重写** | QTableWidget 表格 + Lucide 图标 + 列宽比例 |
| `settings_page.py` | **重写** | QFormLayout 表单 + SVG ComboBox + Lucide 图标 |
| `voiceprint_page.py` | **重写** | 左右分栏 + AddVoiceDialog 重设计 |
| `home_page.py` | **微调** | 工具栏按钮样式统一 + _log 日志过滤 |
| `recording_bar.py` | **微调** | 按钮样式统一 + Lucide 图标 |
| `app.py` | **微调** | GUILogHandler 日志过滤 |
| `topbar.py` | **不变** | 已正常工作 |
| `transcription.py` | **不变** | 已正常工作 |
| `dialogs.py` | **不变** | 已正常工作 |
| `first_launch.py` | **不变** | 已正常工作 |

### 5.3 各文件详细实施要求

#### 5.3.1 styles.py（重写）

**当前问题**：
- 色值是旧版 customtkinter 风格（`C_ACCENT=#0067C0`），需要更新为新设计色板
- ComboBox 箭头用的 SVG data URI 已正确，但需要验证在 PySide6 中渲染正常
- CheckBox 选中态只改了边框色，没有画对勾
- 缺少 Danger/Success/Purple 按钮样式

**实施要求**：

```python
# 1. 更新色值
C_BG      = "#F8F9FA"   # 页面背景（原 #F3F3F3）
C_CARD    = "#FFFFFF"
C_BORDER  = "#E5E7EB"   # 边框（原 #E5E5E5）
C_ACCENT  = "#3B82F6"   # 主色（原 #0067C0）
C_SUCCESS = "#10B981"   # 新增
C_ERROR   = "#EF4444"   # 更新（原 #C42B1C）
C_WARN    = "#F59E0B"   # 更新（原 #9D5D00）

# 2. 添加 QPainter 图标绘制函数
def create_icon(painter_func, size=16):
    """创建 QIcon，通过 painter_func 绘制"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter_func(painter, size)
    painter.end()
    return QIcon(pixmap)

def draw_eye_icon(painter, size):
    """绘制眼睛图标（API Key 显示）"""
    # 椭圆轮廓
    painter.setPen(QPen(QColor("#6B7280"), 1.5))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QRectF(2, 5, 12, 8))
    # 中心圆
    painter.setBrush(QColor("#6B7280"))
    painter.drawEllipse(QRectF(5.5, 7.5, 3, 3))

def draw_eye_off_icon(painter, size):
    """绘制斜线眼睛图标（API Key 隐藏）"""
    # 椭圆轮廓
    painter.setPen(QPen(QColor("#6B7280"), 1.5))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QRectF(2, 5, 12, 8))
    # 斜线
    painter.drawLine(QPointF(2, 12), QPointF(14, 4))

def draw_check_icon(painter, size):
    """绘制对勾图标（CheckBox 选中）"""
    painter.setPen(QPen(QColor("#FFFFFF"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(QPointF(2.5, 6), QPointF(5, 8.5))
    painter.drawLine(QPointF(5, 8.5), QPointF(9.5, 3.5))

def draw_play_icon(painter, size):
    """绘制播放三角形"""
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#FFFFFF"))
    path = QPainterPath()
    path.moveTo(4, 2)
    path.lineTo(12, 8)
    path.lineTo(4, 14)
    path.closeSubpath()
    painter.drawPath(path)

# 3. 更新 MAIN_STYLESHEET
# - 添加 Danger/Success/Purple 按钮样式
# - CheckBox::indicator:checked 背景色 + 对勾
# - 确保 ComboBox::down-arrow 使用 SVG data URI
```

#### 5.3.2 file_list_view.py（重写）

**v1.1 更新：使用 QTableWidget 替代 QGridLayout，原生支持列宽比例调整。**

**当前问题（根因分析）**：
- 每行数据使用独立的 `QHBoxLayout`，列宽不共享 → 列对齐错位
- 没有 `addStretch()` → 数据行垂直居中而不是顶部对齐
- 操作按钮用 emoji → 渲染不一致

**实施要求**：

```python
# 使用 QTableWidget 替代 QGridLayout
# 原生支持列宽比例调整，窗口缩放时保持比例

from PySide6.QtWidgets import QTableWidget, QHeaderView
from gui.icons import icon_play, icon_preview, icon_open_folder, ...

class FileListView(QWidget):
    # 列定义：(标题, 初始宽度比例, 对齐方式)
    # v1.1 优化：文件名列较窄，主题列较宽，操作列表头居中
    COLUMNS = [
        ("队列",   0.04, Qt.AlignCenter),
        ("文件名", 0.22, Qt.AlignLeft | Qt.AlignVCenter),
        ("主题",   0.25, Qt.AlignLeft | Qt.AlignVCenter),
        ("时长",   0.10, Qt.AlignCenter),
        ("大小",   0.10, Qt.AlignCenter),
        ("状态",   0.10, Qt.AlignCenter),
        ("操作",   0.19, Qt.AlignCenter),  # 操作列表头居中
    ]

    def _setup_table(self):
        """配置表格属性"""
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)

        # 关键：设置列宽模式为 Interactive，初始按比例设置
        for i, (_, ratio, _) in enumerate(self.COLUMNS):
            header.setSectionResizeMode(i, QHeaderView.Interactive)

    def resizeEvent(self, event):
        """窗口大小变化时按比例调整列宽"""
        super().resizeEvent(event)
        self._adjust_column_widths()

    def _adjust_column_widths(self):
        """按比例调整列宽"""
        total_width = self._table.viewport().width()
        for i, (_, ratio, _) in enumerate(self.COLUMNS):
            width = int(total_width * ratio)
            self._table.setColumnWidth(i, width)

    def _create_action_buttons(self, row, file_info):
        """创建操作按钮（使用 Lucide 图标）"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)

        status = file_info.get("status", "pending")

        if status == "done":
            buttons = [
                ("预览", icon_preview(), lambda: self._on_action("preview", path)),
                ("打开", icon_open_folder(), lambda: self._on_action("open_folder", path)),
                ("发言人", icon_speaker(), lambda: self._on_action("speaker", path)),
                ("重试", icon_retry(), lambda: self._on_action("retry", path)),
                ("导出", icon_export(), lambda: self._on_action("export", path)),
            ]
        elif status == "failed":
            buttons = [("重试", icon_retry(), ...)]
        elif status == "processing":
            buttons = [("停止", icon_stop(), ...)]
        else:
            buttons = [
                ("转写", icon_play(), ...),
                ("删除", icon_delete(), ...),
            ]

        for text, icon, callback in buttons:
            btn = QPushButton()
            btn.setIcon(icon)
            btn.setToolTip(text)
            btn.setFixedSize(26, 26)
            # 样式统一：透明背景，hover 变灰
            btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; border-radius: 4px; }
                QPushButton:hover { background: #F3F4F6; }
                QPushButton:pressed { background: #E5E7EB; }
            """)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
```

**完整实现文件**：`src/gui/file_list_view_new.py`（可直接替换原文件）

#### 5.3.3 settings_page.py（重写）

**当前问题**：
- 所有行都用 `QHBoxLayout` 手动拼接标签+控件
- API Key 眼睛图标显示为红点（SVG 渲染失败）
- ComboBox 箭头不显示三角形

**实施要求**：

```python
from PySide6.QtWidgets import QFormLayout, QLineEdit, QComboBox, QCheckBox

class SettingsPage(QWidget):
    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        main_layout = QVBoxLayout(container)
        
        # 页面标题
        title = QLabel("设置")
        title.setStyleSheet("font-size:22px; font-weight:700;")
        main_layout.addWidget(title)
        
        # ── 存储路径 ──
        self._build_section(main_layout, "存储路径", self._build_path_card)
        
        # ── 转写引擎 ──
        self._build_section(main_layout, "转写引擎", self._build_engine_card)
        
        # ── AI 增强 ──
        self._build_section(main_layout, "AI 增强", self._build_ai_card)
        
        # ... 其他分组
        
        scroll.setWidget(container)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
    
    def _build_section(self, parent, title_text, builder_func):
        """构建一个设置分组"""
        label = QLabel(f"  {title_text}")
        label.setStyleSheet("font-size:13px; font-weight:600; color:#6B7280;")
        parent.addWidget(label)
        
        card = QFrame()
        card.setProperty("cssClass", "card")
        builder_func(card)
        parent.addWidget(card)
    
    def _build_path_card(self, card):
        """使用 QFormLayout 构建路径设置"""
        layout = QFormLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.setLabelAlignment(Qt.AlignRight)
        
        # 录音保存目录
        rec_row = QHBoxLayout()
        self._rec_dir_entry = QLineEdit()
        rec_row.addWidget(self._rec_dir_entry, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(64)
        rec_row.addWidget(browse_btn)
        layout.addRow("录音保存目录", rec_row)
        
        # 转写输出目录
        out_row = QHBoxLayout()
        self._out_dir_entry = QLineEdit()
        out_row.addWidget(self._out_dir_entry, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(64)
        out_row.addWidget(browse_btn)
        layout.addRow("转写输出目录", out_row)
    
    def _build_ai_card(self, card):
        """AI 增强设置"""
        layout = QFormLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.setLabelAlignment(Qt.AlignRight)
        
        # 模型厂商
        self._vendor_combo = QComboBox()
        self._vendor_combo.addItems(["小米", "智谱", "阿里", "百度", "DeepSeek"])
        layout.addRow("模型厂商", self._vendor_combo)
        
        # API Key（关键：用 QPainter 图标替代 emoji）
        api_row = QHBoxLayout()
        self._api_key_entry = QLineEdit()
        self._api_key_entry.setEchoMode(QLineEdit.Password)
        api_row.addWidget(self._api_key_entry, 1)
        
        self._api_key_toggle = QPushButton()
        self._api_key_toggle.setFixedSize(32, 32)
        self._api_key_toggle.setIcon(create_icon(draw_eye_icon))
        self._api_key_toggle.clicked.connect(self._toggle_api_key)
        api_row.addWidget(self._api_key_toggle)
        
        layout.addRow("API Key", api_row)
```

#### 5.3.4 voiceprint_page.py（重写）

**当前问题**：
- AddVoiceDialog 布局松散，顶部大量空白
- 录音状态显示不够直观
- 列表项选中效果不明显

**实施要求**：

```python
class VoiceprintPage(QWidget):
    def _build(self):
        layout = QVBoxLayout(self)
        
        # 页面标题 + 添加按钮
        header = QHBoxLayout()
        title = QLabel("音色库管理")
        title.setStyleSheet("font-size:22px; font-weight:700;")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("+ 添加音色")
        add_btn.setProperty("cssClass", "primary")
        add_btn.clicked.connect(self._add_speaker)
        header.addWidget(add_btn)
        layout.addLayout(header)
        
        # 左右分栏
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：说话人列表
        self._list_panel = self._build_list_panel()
        splitter.addWidget(self._list_panel)
        
        # 右侧：详情
        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        
        splitter.setSizes([280, 600])  # 1:2 比例
        layout.addWidget(splitter)
        
        # 状态栏
        self._status_label = QLabel("共 0 个说话人，0 个样本")
        self._status_label.setStyleSheet("font-size:11px; color:#9CA3AF;")
        layout.addWidget(self._status_label)


class AddVoiceDialog(QDialog):
    """添加音色弹窗"""
    
    PRESET_TEXT = "你好，我是{姓名}，这是我的声纹样本。"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加新说话人")
        self.setFixedSize(440, 360)  # 紧凑尺寸
        self._build()
    
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("添加新说话人")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        layout.addWidget(title)
        
        subtitle = QLabel("录音朗读以下文本，系统将自动提取声纹")
        subtitle.setStyleSheet("font-size:12px; color:#9CA3AF;")
        layout.addWidget(subtitle)
        
        # 姓名输入
        name_label = QLabel("说话人姓名")
        name_label.setStyleSheet("font-size:12px; color:#6B7280;")
        layout.addWidget(name_label)
        
        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("请输入姓名")
        layout.addWidget(self._name_entry)
        
        # 预设文本卡片
        preset_card = QFrame()
        preset_card.setProperty("cssClass", "card")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(16, 12, 16, 12)
        
        preset_title = QLabel("请朗读以下文本：")
        preset_title.setStyleSheet("font-size:12px; font-weight:600; color:#6B7280;")
        preset_layout.addWidget(preset_title)
        
        preset_text = QLabel(self.PRESET_TEXT)
        preset_text.setStyleSheet("font-size:13px; color:#111827;")
        preset_layout.addWidget(preset_text)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background:#E5E7EB;")
        preset_layout.addWidget(line)
        
        # 录音状态
        self._rec_indicator = QLabel("●")
        self._rec_indicator.setStyleSheet("color:#D1D5DB; font-size:8px;")
        self._rec_status = QLabel("准备就绪")
        self._rec_status.setStyleSheet("font-size:12px; color:#9CA3AF;")
        
        rec_row = QHBoxLayout()
        rec_row.addWidget(self._rec_indicator)
        rec_row.addWidget(self._rec_status)
        rec_row.addStretch()
        preset_layout.addLayout(rec_row)
        
        layout.addWidget(preset_card)
        
        # 按钮
        btn_row = QHBoxLayout()
        self._record_btn = QPushButton("开始录音")
        self._record_btn.setFixedWidth(120)
        self._record_btn.setStyleSheet(
            "background:#EF4444; color:white; border:none; font-weight:600;")
        self._record_btn.clicked.connect(self._toggle_recording)
        btn_row.addWidget(self._record_btn)
        
        self._save_btn = QPushButton("保存")
        self._save_btn.setFixedWidth(80)
        self._save_btn.setEnabled(False)
        btn_row.addWidget(self._save_btn)
        
        btn_row.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)
        
        layout.addLayout(btn_row)
```

#### 5.3.5 日志过滤（home_page.py + app.py 微调）

**当前问题**：`USER_FRIENDLY_KEYWORDS` 定义了但三个入口都没调用。

**home_page.py 修改**：

```python
# 在 _log() 方法中添加过滤
def _log(self, msg):
    """日志输出（仅显示用户关心的信息）"""
    if not any(kw in msg for kw in USER_FRIENDLY_KEYWORDS):
        return  # 过滤掉技术日志
    # ... 原有的日志显示逻辑
```

**app.py 修改**：

```python
# GUILogHandler._poll_queue() 中添加过滤
def _poll_queue(self):
    try:
        while not self._log_queue.empty():
            msg = self._log_queue.get_nowait()
            # 过滤技术日志
            if not any(kw in msg for kw in USER_FRIENDLY_KEYWORDS):
                continue
            if self._log_area:
                self._log_area.appendPlainText(msg)
    except queue.Empty:
        pass

# _append_log() 中添加过滤
def _append_log(self, msg):
    if not any(kw in msg for kw in USER_FRIENDLY_KEYWORDS):
        return
    # ... 原有的日志显示逻辑
```

#### 5.3.6 recording_bar.py（微调）

**当前问题**：
- 录音中按钮没有 :pressed 状态
- 暂停/停止按钮样式不够统一

**修改要点**：

```python
# 1. 开始录音按钮：Danger 样式
self.record_btn = QPushButton("开始录音")
self.record_btn.setProperty("cssClass", "danger")
self.record_btn.setFixedSize(90, 32)

# 2. 暂停按钮：录音中时红色边框
self.pause_btn = QPushButton("暂停")
self.pause_btn.setFixedSize(60, 32)
# 录音中激活时：
self.pause_btn.setStyleSheet(
    "border:1px solid #EF4444; color:#EF4444; background:transparent;")

# 3. 停止按钮：灰色边框
self.stop_btn = QPushButton("停止")
self.stop_btn.setFixedSize(60, 32)
```

---

## 六、与旧版 UI 对比：查缺补漏

### 6.1 新设计保留的旧版功能

| 功能 | 旧版实现 | 新设计 |
|------|---------|--------|
| 录音模式选择 | ComboBox（现场/线上） | 保留 ComboBox |
| 录音计时器 | 22px 粗体 | 保留 |
| 文件列表 7 列 | grid 布局 | QGridLayout（相同列结构） |
| 操作按钮（6个） | emoji | QIcon + QPainter |
| 设置页 7 个分组 | pack 布局 | QFormLayout |
| 音色库左右分栏 | 1:2 比例 | QSplitter 1:2 |
| AddVoiceDialog | 480x400 | 440x360（更紧凑） |
| 日志区域 | 固定高度 | 固定 120px |

### 6.2 新设计改进的点

| 改进项 | 旧版 | 新版 |
|--------|------|------|
| 文件列表列对齐 | 每行独立布局，列错位 | QGridLayout 共享列权重 |
| 文件列表顶部对齐 | 无 stretch，居中显示 | 底部 addStretch() |
| ComboBox 箭头 | CSS border 不生效 | SVG data URI |
| API Key 图标 | emoji 渲染为红点 | QPainter 绘制 |
| CheckBox 对勾 | 无对勾 | QPainter 画白色对勾 |
| 日志过滤 | 定义了但没用 | 三个入口都过滤 |
| About 文案 | 列举 11 家厂商 | "支持国内主流云端模型厂商" |
| 按钮样式 | 同级不统一 | 统一高度和 font-weight |
| 色值 | 旧版 Windows 10 风格 | 新版 Fluent Design |

### 6.3 新增的功能点

| 新增功能 | 说明 |
|----------|------|
| 音色库搜索 | 左侧列表顶部添加搜索框 |
| 录音状态动画 | 录音指示点 + 波形动画（可选） |
| 声纹质量评分徽章 | 绿色/黄色标签区分质量 |
| 文件计数显示 | 标题右侧显示"共 N 个文件" |

---

## 七、Git 提交规范

MiMo Code 完成实施后，请按以下规范提交：

### 7.1 提交信息格式

```
type(scope): description

body

🤖 Generated with [Qoder][https://qoder.com]
```

### 7.2 类型

- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 重构（不改变功能）
- `style`: 样式调整
- `docs`: 文档更新

### 7.3 建议的提交拆分

1. `feat(styles): 重写设计系统和全局 QSS` — styles.py
2. `refactor(file-list): 用 QGridLayout 替代 QHBoxLayout` — file_list_view.py
3. `refactor(settings): 用 QFormLayout 重写设置页` — settings_page.py
4. `refactor(voiceprint): 重写音色库页面和添加弹窗` — voiceprint_page.py
5. `fix(log-filter): 在三个入口添加日志过滤` — home_page.py + app.py
6. `style(recording-bar): 统一按钮样式和状态` — recording_bar.py

### 7.4 验证清单

实施完成后，请逐项验证：

**图标系统（Lucide）**：
- [ ] 所有操作按钮使用 Lucide 图标（不是 emoji）
- [ ] 图标风格统一（线性，2px 描边）
- [ ] 图标大小统一（26x26 按钮内）
- [ ] 操作按钮 hover 有背景色变化
- [ ] 录音中按钮有 :pressed 状态

**文件表格（QTableWidget）**：
- [ ] 文件列表 7 列对齐（表头和数据列宽一致）
- [ ] 文件列表数据行顶部对齐（不垂直居中）
- [ ] 窗口缩小时列按比例调整（文件名窄、主题宽）
- [ ] 操作列表头居中对齐
- [ ] 文件名列宽度 < 主题列宽度

**ComboBox / CheckBox**：
- [ ] ComboBox 下拉箭头显示为三角形
- [ ] API Key 眼睛图标正常显示（不是红点）
- [ ] CheckBox 选中时显示白色对勾

**日志过滤**：
- [ ] 日志区域只显示用户关心的信息（过滤技术日志）
- [ ] 三个入口都已添加过滤

**About 文案**：
- [ ] About 文案简化为"支持国内主流云端模型厂商"

**其他**：
- [ ] 录音模式选择使用 ComboBox（保留旧版交互）
- [ ] 添加音色弹窗紧凑无多余空白
- [ ] 音色库左右分栏比例 1:2
- [ ] 设置页表单标签右对齐

---

## 八、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-06-14 | v1.0 | 初始版本：完整 UI 重新设计方案 |
| 2026-06-14 | v1.1 | 新增 Lucide 统一图标系统；文件表格改用 QTableWidget + 列宽比例；操作列表头居中；文件名列缩窄、主题列加宽 |

---

> 本文档由 QoderWork 设计，供 MiMo Code 实施参考。
> 如有问题，请在 GitHub Issues 中反馈。
