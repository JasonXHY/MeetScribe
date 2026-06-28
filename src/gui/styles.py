"""
侧耳倾听 GUI 样式常量和配置常量（PySide6 UI 重新设计版）

基于 ui-redesign-guide.md v1.1 设计规范
"""

import os
import sys
from utils import get_data_dir

# ── Color Palette (Windows 11 Light Fluent + 新设计系统) ──────
C_BG         = "#F8F9FA"   # 页面背景
C_SIDEBAR    = "#FAFAFA"
C_CARD       = "#FFFFFF"
C_BORDER     = "#E5E7EB"   # 边框
C_ACCENT     = "#3B82F6"   # 主色蓝
C_ACCENT_LT  = "#EFF6FF"   # 选中行背景
C_SUCCESS    = "#10B981"   # 成功绿
C_WARN       = "#F59E0B"   # 警告黄
C_ERROR      = "#EF4444"   # 错误红
C_PURPLE     = "#8B5CF6"   # AI 紫
C_TXT1       = "#111827"   # 标题/主要文字
C_TXT2       = "#6B7280"   # 辅助文字/标签
C_TXT3       = "#9CA3AF"   # 占位符/禁用
C_BTN_HOVER  = "#2563EB"   # 主操作 hover

# ── Status Colors ────────────────────────────────────────────
STATUS_COLORS = {
    "pending":    "#9CA3AF",  # 灰色
    "processing": "#3B82F6",  # 蓝色
    "done":       "#10B981",  # 绿色
    "failed":     "#EF4444",  # 红色
}

# ── Constants ────────────────────────────────────────────────
APP_VERSION  = "1.0"
APP_NAME     = "侧耳倾听"
APP_NAME_EN  = "MeetScribe"
FONT_FAMILY  = "Microsoft YaHei, Segoe UI, sans-serif"
FONT_MONO    = "Cascadia Code, Consolas, monospace"
TOPBAR_H     = 44

# 资源目录：打包模式用 sys._MEIPASS，开发模式用 __file__ 计算
if getattr(sys, 'frozen', False):
    ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
else:
    ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")

ICON_PNG     = os.path.join(ASSETS_DIR, "logo_256x256.png")
ICON_ICO     = os.path.join(ASSETS_DIR, "logo.ico")

# ── Font Sizes ───────────────────────────────────────────────
FONT_SIZE_DISPLAY = 24      # Display - 页面标题
FONT_SIZE_TITLE = 16        # Title - 卡片标题
FONT_SIZE_BRAND = 16        # 品牌名称
FONT_SIZE_NAV = 13          # 导航按钮
FONT_SIZE_BODY = 13         # Body - 正文/控件文字
FONT_SIZE_CAPTION = 12      # Caption - 辅助说明/表单标签
FONT_SIZE_SMALL = 11        # Small - 注释/状态文字/表头
FONT_SIZE_TINY = 10         # Tiny - 版本号
FONT_SIZE_TIMER = 24        # 计时器
FONT_SIZE_LOG = 11          # 日志区

# ── Default Values ──────────────────────────────────────────
DEFAULT_SPK_QUALITY = 0.85     # 默认说话人质量评分
DEFAULT_DEBOUNCE_MS = 200      # 默认防抖毫秒数
POLL_INTERVAL_MIN_MS = 50      # 最小轮询间隔
POLL_INTERVAL_MAX_MS = 500     # 最大轮询间隔

# ── Spacing System (4px base) ────────────────────────────────
SPACING_1 = 4               # 最小间距
SPACING_2 = 8               # 紧凑间距
SPACING_3 = 12              # 标准间距
SPACING_4 = 16              # 卡片内 padding
SPACING_5 = 20              # 卡片间距
SPACING_6 = 24              # 页面边距

# Legacy spacing constants (for backward compatibility)
SPACING_PAGE_MARGIN = 24
SPACING_CARD_PADDING = 16
SPACING_CARD_RADIUS = 8
SPACING_BUTTON_GAP = 8
SPACING_CARD_GAP = 20
SPACING_TOPBAR_PADDING = 16
SPACING_ROW_GAP = 2
SPACING_STATUS_BAR_H = 28

# ── Button Sizes ─────────────────────────────────────────────
BTN_SIZE_PRIMARY = (90, 32)
BTN_SIZE_SECONDARY = (80, 32)
BTN_SIZE_ICON = (28, 28)
BTN_SIZE_QUEUE = (24, 24)
BTN_SIZE_SMALL = (50, 22)
BTN_RADIUS = 6
BTN_RADIUS_ICON = 4

# ── File Dialog Filters ──────────────────────────────────────
AUDIO_EXTENSIONS = [
    ("音频文件", "*.wav *.mp3 *.m4a *.flac *.ogg *.oga *.opus"),
    ("WAV", "*.wav"), ("MP3", "*.mp3"), ("M4A", "*.m4a"),
    ("FLAC", "*.flac"), ("OGG/OGA", "*.ogg *.oga *.opus"),
    ("所有文件", "*.*"),
]

# ── Output Formats ───────────────────────────────────────────
OUTPUT_FORMATS = {
    "Markdown (推荐)": "md",
    "LLM Markdown": "llm-md",
    "HTML 网页 (带颜色)": "html",
    "纯文本 (txt)": "txt",
    "SRT 字幕": "srt",
    "JSON 数据": "json",
}

# ── Model Cache ──────────────────────────────────────────────
# frozen 模式：模型缓存在 AppData 目录
# 开发模式：使用数据目录下的 models_cache/
if getattr(sys, 'frozen', False):
    MODEL_CACHE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'MeetScribe', 'models')
else:
    MODEL_CACHE_DIR = os.path.join(get_data_dir(), "models_cache")

# ── Speaker Colors ───────────────────────────────────────────
SPEAKER_COLORS = [
    "#4A90D9", "#E67E22", "#27AE60", "#E74C3C",
    "#9B59B6", "#1ABC9C", "#F39C12", "#2C3E50",
    "#16A085", "#C0392B", "#2980B9", "#8E44AD",
]

# ── Tooltips ──────────────────────────────────────────────────
TOOLTIPS = {
    "preview": "预览转写结果",
    "open": "打开文件夹",
    "speaker": "管理发言人",
    "retry": "重新转写",
    "stop": "停止转写",
    "transcribe": "开始转写",
    "export": "导出结果",
    "move_up": "上移",
    "move_down": "下移",
    "remove": "从队列移除",
}

# ── QSS 样式表 ──────────────────────────────────────────────
MAIN_STYLESHEET = f"""
/* 全局 */
QMainWindow, QDialog {{
    background-color: {C_BG};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

/* Frame - 仅卡片样式 */
QFrame[cssClass="card"] {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}}

/* Button - 默认 */
QPushButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 0 16px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    font-weight: 500;
    color: {C_TXT2};
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #F3F4F6;
}}
QPushButton:disabled {{
    color: {C_TXT3};
    border-color: #D1D5DB;
}}
QPushButton:pressed {{
    background-color: #E5E7EB;
}}

/* Primary Button */
QPushButton[cssClass="primary"] {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    font-weight: 500;
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {C_BTN_HOVER};
}}
QPushButton[cssClass="primary"]:pressed {{
    background-color: #1D4ED8;
}}
QPushButton[cssClass="primary"]:disabled {{
    background-color: #93C5FD;
}}

/* Danger Button */
QPushButton[cssClass="danger"] {{
    background-color: {C_ERROR};
    color: white;
    border: none;
    font-weight: 500;
}}
QPushButton[cssClass="danger"]:hover {{
    background-color: #DC2626;
}}
QPushButton[cssClass="danger"]:pressed {{
    background-color: #B91C1C;
}}

/* Success Button */
QPushButton[cssClass="success"] {{
    background-color: {C_SUCCESS};
    color: white;
    border: none;
    font-weight: 500;
}}
QPushButton[cssClass="success"]:hover {{
    background-color: #059669;
}}
QPushButton[cssClass="success"]:pressed {{
    background-color: #047857;
}}
QPushButton[cssClass="success"]:disabled {{
    background-color: #6EE7B7;
}}

/* Purple Button (AI) */
QPushButton[cssClass="purple"] {{
    background-color: {C_PURPLE};
    color: white;
    border: none;
    font-weight: 500;
}}
QPushButton[cssClass="purple"]:hover {{
    background-color: #7C3AED;
}}
QPushButton[cssClass="purple"]:pressed {{
    background-color: #6D28D9;
}}

/* Save Button */
QPushButton[cssClass="save"] {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    font-size: 14px;
}}
QPushButton[cssClass="save"]:hover {{
    background-color: {C_BTN_HOVER};
}}

/* Danger Outline Button */
QPushButton[cssClass="danger-outline"] {{
    background-color: transparent;
    color: {C_ERROR};
    border: 1px solid #FCA5A5;
    font-weight: 500;
}}
QPushButton[cssClass="danger-outline"]:hover {{
    background-color: #FEF2F2;
}}

/* Label */
QLabel {{
    background-color: transparent;
    border: none;
    font-family: {FONT_FAMILY};
}}

/* LineEdit */
QLineEdit {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    background-color: white;
    min-height: 20px;
}}
QLineEdit:focus {{
    border-color: {C_ACCENT};
}}

/* ComboBox */
QComboBox {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    padding-right: 28px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    background-color: #F9FAFB;
    min-height: 20px;
}}
QComboBox:hover {{
    background-color: #F3F4F6;
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%239CA3AF'/%3E%3C/svg%3E");
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: white;
    border: 1px solid {C_BORDER};
    selection-background-color: {C_ACCENT_LT};
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    min-height: 28px;
}}

/* ScrollArea */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #D1D5DB;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #9CA3AF;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #D1D5DB;
    border-radius: 4px;
    min-width: 30px;
}}

/* CheckBox */
QCheckBox {{
    spacing: 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {C_TXT1};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid #D1D5DB;
    border-radius: 4px;
    background-color: white;
}}
QCheckBox::indicator:checked {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
    image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 12 12'%3E%3Cpolyline points='2 6 5 9 10 3' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
}}
QCheckBox::indicator:hover {{
    border-color: {C_ACCENT};
}}

/* RadioButton */
QRadioButton {{
    spacing: 8px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid #D1D5DB;
    border-radius: 8px;
    background-color: white;
}}
QRadioButton::indicator:checked {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
}}

/* TabWidget */
QTabWidget::pane {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    background-color: white;
}}
QTabBar::tab {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background-color: white;
    color: {C_ACCENT};
    font-weight: 500;
}}

/* ProgressBar */
QProgressBar {{
    border: none;
    background-color: #E5E7EB;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {C_ACCENT};
    border-radius: 3px;
}}

/* ToolTip */
QToolTip {{
    background-color: #1F2937;
    color: white;
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}}

/* TableWidget */
QTableWidget {{
    background-color: white;
    border: none;
    gridline-color: #F3F4F6;
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {C_ACCENT_LT};
    color: {C_TXT1};
}}
QHeaderView::section {{
    background-color: #F9FAFB;
    border: none;
    border-bottom: 1px solid {C_BORDER};
    border-right: 1px solid #F3F4F6;
    padding: 8px;
    font-family: {FONT_FAMILY};
    font-size: 11px;
    font-weight: 500;
    color: {C_TXT2};
}}
"""
