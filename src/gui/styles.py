"""
侧耳倾听 GUI 样式常量和配置常量（PySide6 版本）
"""

import os

# ── Color Palette (Windows 11 Light Fluent) ──────────────────
C_BG         = "#F3F3F3"
C_SIDEBAR    = "#FAFAFA"
C_CARD       = "#FFFFFF"
C_BORDER     = "#E5E5E5"
C_ACCENT     = "#0067C0"
C_ACCENT_LT  = "#E8F0FE"
C_SUCCESS    = "#0F7B0F"
C_WARN       = "#9D5D00"
C_ERROR      = "#C42B1C"
C_TXT1       = "#1A1A1A"
C_TXT2       = "#616161"
C_TXT3       = "#757575"
C_BTN_HOVER  = "#005BA1"

# ── Constants ────────────────────────────────────────────────
APP_VERSION  = "1.0"
APP_NAME     = "侧耳倾听"
APP_NAME_EN  = "MeetScribe"
FONT_FAMILY  = "Microsoft YaHei, Segoe UI, sans-serif"
TOPBAR_H     = 44
ASSETS_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
ICON_PNG     = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO     = os.path.join(ASSETS_DIR, "icon.ico")

# ── Font Sizes ───────────────────────────────────────────────
FONT_SIZE_PAGE_TITLE = 22      # 页面标题
FONT_SIZE_SECTION_TITLE = 16   # 区域标题
FONT_SIZE_BRAND = 16           # 品牌名称
FONT_SIZE_NAV = 13             # 导航按钮
FONT_SIZE_BODY = 12            # 正文/表格/按钮
FONT_SIZE_CAPTION = 11         # 注释/辅助
FONT_SIZE_SMALL = 10           # 版本号/模式提示
FONT_SIZE_TIMER = 22           # 计时器
FONT_SIZE_LOG = 11             # 日志区

# ── Default Values ──────────────────────────────────────────
DEFAULT_SPK_QUALITY = 0.85     # 默认说话人质量评分
DEFAULT_DEBOUNCE_MS = 200      # 默认防抖毫秒数
POLL_INTERVAL_MIN_MS = 50      # 最小轮询间隔
POLL_INTERVAL_MAX_MS = 500     # 最大轮询间隔

# ── Spacing ──────────────────────────────────────────────────
SPACING_PAGE_MARGIN = 20       # 页面左右边距
SPACING_CARD_PADDING = 14      # 卡片内部 padding
SPACING_CARD_RADIUS = 8        # 卡片圆角
SPACING_BUTTON_GAP = 4         # 按钮间距
SPACING_CARD_GAP = 6           # 卡片间垂直间距
SPACING_TOPBAR_PADDING = 16    # TopBar 内边距
SPACING_ROW_GAP = 2            # 表格行间距
SPACING_STATUS_BAR_H = 28      # 状态栏高度

# ── Button Sizes ─────────────────────────────────────────────
BTN_SIZE_PRIMARY = (90, 32)    # 主操作按钮
BTN_SIZE_SECONDARY = (80, 32)  # 次要按钮
BTN_SIZE_ICON = (28, 26)       # 操作图标按钮
BTN_SIZE_QUEUE = (24, 24)      # 队列管理按钮
BTN_SIZE_SMALL = (50, 22)      # 日志清除按钮
BTN_RADIUS = 6                 # 按钮圆角
BTN_RADIUS_ICON = 4            # 图标按钮圆角

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
MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models_cache")

# ── Speaker Colors ───────────────────────────────────────────
SPEAKER_COLORS = [
    "#4A90D9", "#E67E22", "#27AE60", "#E74C3C",
    "#9B59B6", "#1ABC9C", "#F39C12", "#2C3E50",
    "#16A085", "#C0392B", "#2980B9", "#8E44AD",
]

# ── Icons ──────────────────────────────────────────────────
ICON_STATUS = {
    "pending": "○",
    "processing": "⏳",
    "done": "✓",
    "failed": "✗",
}

ICON_ACTION = {
    "preview": "👁",
    "open": "📂",
    "speaker": "👤",
    "retry": "🔄",
    "stop": "⏹",
    "transcribe": "▶",
    "export": "📤",
}

ICON_COLOR = {
    "pending": "#757575",
    "processing": "#007bff",
    "done": "#28a745",
    "failed": "#dc3545",
}

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
    border-radius: 6px;
}}

/* Button */
QPushButton {{
    background-color: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
    color: {C_TXT1};
}}
QPushButton:hover {{
    background-color: {C_ACCENT_LT};
}}
QPushButton:disabled {{
    color: {C_TXT3};
    border-color: {C_TXT3};
}}
QPushButton:pressed {{
    background-color: #E8E8E8;
}}

/* Primary Button */
QPushButton[cssClass="primary"] {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {C_BTN_HOVER};
}}
QPushButton[cssClass="primary"]:pressed {{
    background-color: #004A8C;
}}
QPushButton[cssClass="primary"]:disabled {{
    background-color: {C_TXT3};
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
    padding: 6px 10px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
    background-color: white;
}}
QLineEdit:focus {{
    border-color: {C_ACCENT};
}}

/* ComboBox */
QComboBox {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    padding-right: 24px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
    background-color: #F8F8F8;
    min-height: 22px;
}}
QComboBox:hover {{
    background-color: #E8E8E8;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23616161'/%3E%3C/svg%3E");
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
    padding: 4px 8px;
    min-height: 24px;
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
    background: #C0C0C0;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #A0A0A0;
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
    background: #C0C0C0;
    border-radius: 4px;
    min-width: 30px;
}}

/* CheckBox */
QCheckBox {{
    spacing: 8px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
    color: {C_TXT1};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #B0B0B0;
    border-radius: 3px;
    background-color: white;
}}
QCheckBox::indicator:checked {{
    background-color: white;
    border: 2px solid {C_ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {C_ACCENT};
}}

/* RadioButton */
QRadioButton {{
    spacing: 8px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {C_BORDER};
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
    padding: 6px 16px;
    margin-right: 2px;
    font-family: {FONT_FAMILY};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: white;
    color: {C_ACCENT};
    font-weight: bold;
}}

/* ProgressBar */
QProgressBar {{
    border: none;
    background-color: #E0E0E0;
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
    background-color: #2C2C2C;
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
}}
"""
