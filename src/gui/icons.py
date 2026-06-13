"""
侧耳倾听 图标模块（基于 Lucide Icons）

统一使用 Lucide 线性图标风格，24x24 网格，2px 描边。
所有图标通过 QSvgRenderer 渲染为 QPixmap，再封装为 QIcon。

Lucide Icons 许可证：ISC License (https://lucide.dev/license)
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from PySide6.QtSvg import QSvgRenderer

# ── Lucide SVG 数据 ──────────────────────────────────────────
# 所有图标基于 24x24 网格，stroke-width="2"
# 使用 {color} 占位符，渲染时替换为实际颜色

ICON_SVGS = {
    # ── 播放/录音 ──
    "play": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>',

    "pause": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>',

    "square": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/></svg>',

    "mic": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>',

    # ── 文件操作 ──
    "file-text": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>',

    "folder-open": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 2H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2Z"/></svg>',

    "download": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',

    "trash-2": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>',

    # ── 用户/说话人 ──
    "user": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',

    "users": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',

    # ── 状态/反馈 ──
    "check": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',

    "x": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',

    "alert-circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>',

    "clock": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',

    # ── 导航/交互 ──
    "eye": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',

    "eye-off": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>',

    "chevron-down": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',

    "search": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',

    "plus": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>',

    "save": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',

    "rotate-ccw": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>',

    "more-horizontal": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>',

    # ── 状态指示 ──
    "circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="{color}" stroke="none"><circle cx="12" cy="12" r="6"/></svg>',

    "loader": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/><path d="m16.2 16.2 2.9 2.9"/><path d="M12 18v4"/><path d="m4.9 19.1 2.9-2.9"/><path d="M2 12h4"/><path d="m4.9 4.9 2.9 2.9"/></svg>',

    "check-circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>',

    "x-circle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>',

    # ── AI ──
    "sparkles": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>',

    "merge": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 6 4-4 4 4"/><path d="M12 2v10"/><path d="M6 12H2v2a4 4 0 0 0 4 4h16v-2h-2a4 4 0 0 1-4-4V6h-6Z"/></svg>',
}


# ── 颜色常量 ─────────────────────────────────────────────────
class IconColors:
    """图标颜色常量，与设计规范一致"""
    DEFAULT   = "#6B7280"  # 默认灰色
    PRIMARY   = "#3B82F6"  # 主色蓝
    SUCCESS   = "#10B981"  # 成功绿
    WARNING   = "#F59E0B"  # 警告黄
    ERROR     = "#EF4444"  # 错误红
    PURPLE    = "#8B5CF6"  # AI 紫
    WHITE     = "#FFFFFF"  # 白色（深色背景上）
    DISABLED  = "#D1D5DB"  # 禁用态


# ── 图标创建函数 ──────────────────────────────────────────────
def create_icon(name: str, color: str = IconColors.DEFAULT, size: int = 16) -> QIcon:
    """
    创建 QIcon 从 Lucide SVG 数据。

    Args:
        name: 图标名称（ICON_SVGS 中的 key）
        color: 颜色值（十六进制）
        size: 图标尺寸（px）

    Returns:
        QIcon 实例
    """
    if name not in ICON_SVGS:
        raise ValueError(f"Unknown icon: {name}")

    svg_data = ICON_SVGS[name].format(color=color)

    renderer = QSvgRenderer(svg_data.encode("utf-8"))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)


def create_multi_size_icon(name: str, color: str = IconColors.DEFAULT,
                           sizes: tuple = (16, 24, 32)) -> QIcon:
    """
    创建多尺寸 QIcon（支持不同 DPI）。

    Args:
        name: 图标名称
        color: 颜色值
        sizes: 支持的尺寸元组

    Returns:
        QIcon 实例（带多尺寸支持）
    """
    if name not in ICON_SVGS:
        raise ValueError(f"Unknown icon: {name}")

    svg_data = ICON_SVGS[name].format(color=color)
    renderer = QSvgRenderer(svg_data.encode("utf-8"))

    icon = QIcon()
    for size in sizes:
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()

        icon.addPixmap(pixmap, QIcon.Normal, QIcon.Off)

    return icon


# ── 便捷函数（带颜色预设）──────────────────────────────────────

def icon_play(color=None):
    """播放/转写图标"""
    return create_icon("play", color or IconColors.SUCCESS)

def icon_pause(color=None):
    """暂停图标"""
    return create_icon("pause", color or IconColors.WARNING)

def icon_stop(color=None):
    """停止图标"""
    return create_icon("square", color or IconColors.DEFAULT)

def icon_mic(color=None):
    """麦克风图标"""
    return create_icon("mic", color or IconColors.ERROR)

def icon_preview(color=None):
    """预览图标"""
    return create_icon("eye", color or IconColors.PRIMARY)

def icon_open_folder(color=None):
    """打开文件夹图标"""
    return create_icon("folder-open", color or IconColors.DEFAULT)

def icon_speaker(color=None):
    """发言人管理图标"""
    return create_icon("user", color or IconColors.PURPLE)

def icon_retry(color=None):
    """重新转写图标"""
    return create_icon("rotate-ccw", color or IconColors.WARNING)

def icon_export(color=None):
    """导出图标"""
    return create_icon("download", color or IconColors.PRIMARY)

def icon_delete(color=None):
    """删除图标"""
    return create_icon("trash-2", color or IconColors.ERROR)

def icon_api_key_visible(color=None):
    """API Key 显示图标（眼睛）"""
    return create_icon("eye", color or IconColors.DEFAULT)

def icon_api_key_hidden(color=None):
    """API Key 隐藏图标（斜线眼睛）"""
    return create_icon("eye-off", color or IconColors.DEFAULT)

def icon_status_done(color=None):
    """完成状态图标"""
    return create_icon("check-circle", color or IconColors.SUCCESS)

def icon_status_failed(color=None):
    """失败状态图标"""
    return create_icon("x-circle", color or IconColors.ERROR)

def icon_status_pending(color=None):
    """待处理状态图标"""
    return create_icon("circle", color or IconColors.DISABLED)

def icon_status_processing(color=None):
    """处理中状态图标"""
    return create_icon("loader", color or IconColors.PRIMARY)

def icon_ai_summary(color=None):
    """AI 摘要图标"""
    return create_icon("sparkles", color or IconColors.PURPLE)

def icon_merge(color=None):
    """合并转写图标"""
    return create_icon("merge", color or IconColors.DEFAULT)

def icon_add(color=None):
    """添加图标"""
    return create_icon("plus", color or IconColors.DEFAULT)

def icon_search(color=None):
    """搜索图标"""
    return create_icon("search", color or IconColors.DEFAULT)

def icon_save(color=None):
    """保存图标"""
    return create_icon("save", color or IconColors.DEFAULT)


# ── 状态色映射 ────────────────────────────────────────────────
STATUS_ICONS = {
    "pending":    icon_status_pending,
    "processing": icon_status_processing,
    "done":       icon_status_done,
    "failed":     icon_status_failed,
}

STATUS_COLORS = {
    "pending":    "#D1D5DB",
    "processing": "#3B82F6",
    "done":       "#10B981",
    "failed":     "#EF4444",
}


def get_status_icon(status: str) -> QIcon:
    """根据状态获取对应图标"""
    func = STATUS_ICONS.get(status, icon_status_pending)
    return func()

def get_status_color(status: str) -> str:
    """根据状态获取对应颜色"""
    return STATUS_COLORS.get(status, "#D1D5DB")
