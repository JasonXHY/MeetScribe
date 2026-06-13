# UI 优化方案（第三轮）— 最终版

> 日期：2026-06-11
> 关联文档：`2026-06-10-ui-optimization-round2-final.md`（上轮方案）、`2026-06-11-ui-optimization-round3-review.md`（审阅）、`2026-06-11-ui-optimization-round3-review-response.md`（回应）
> 协作模式：QoderWork 写方案 → MiMo Code 审方案 + 实施 → 用户测试验收
> 本文档用途：5 个问题的最终修复方案，已经过双方讨论确认，可直接实施

---

## 一、文件列表列头与数据列仍然错位

### 现象

上轮方案使用固定 16px 占位列补偿滚动条宽度，但实际效果仍然错位。

### 根因分析

经实测验证，`CTkScrollbar` 的逻辑宽度为 16px，但 Windows 125% DPI 缩放下（`ScalingTracker.get_widget_scaling()` 返回 1.25），实际渲染宽度为 **20px**（16 × 1.25 = 20）。占位列只预留了 16px，差了 4px。

```
验证命令：
s = ctk.CTkScrollbar(root, orientation='vertical')
s.pack(side='right')
root.update()
print(s.winfo_width())  # 输出 20（不是 16）
print(ctk.ScalingTracker.get_widget_scaling(s))  # 输出 1.25
```

### 修复方案（`src/gui/file_list_view.py`）

**不要硬编码占位宽度**，改为渲染后动态获取滚动条实际宽度。

**修改 `_setup_ui()` 中的占位列配置和 `_on_canvas_configure` 回调：**

```python
def _setup_ui(self):
    col_weights = [0, 4, 2, 1, 1, 1, 1]
    for i, w in enumerate(col_weights):
        self.grid_columnconfigure(i, weight=w)

    # 占位列：初始给 16px，渲染后用实际滚动条宽度更新
    self._scrollbar_placeholder = 16
    self.grid_columnconfigure(7, weight=0, minsize=self._scrollbar_placeholder)

    # 表头标签代码不变（row=0, column=0~6）
    # ...

    # 分隔线、scroll_container 代码不变（columnspan=8）
    # ...

    # Canvas 配置回调中动态更新占位列宽度
    self._scrollbar_measured = False

    def _on_canvas_configure(event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        # 调试日志（保留，使用 debug 级别不影响正常运行）
        logger.debug(
            f"[Layout] Canvas={event.width}x{event.height}, "
            f"scroll_container={self._scroll_container.winfo_width()}x{self._scroll_container.winfo_height()}, "
            f"FileListView={self.winfo_width()}x{self.winfo_height()}, "
            f"scrollbar={self._scrollbar.winfo_width()}px"
        )
        # 首次渲染后测量滚动条实际宽度，更新占位列
        if not self._scrollbar_measured:
            self._scrollbar_measured = True
            self.update_idletasks()  # 强制完成所有布局计算
            actual_w = self._scrollbar.winfo_width()
            if actual_w <= 0:
                # 兜底：用 DPI 缩放因子计算
                from customtkinter import ScalingTracker
                scaling = ScalingTracker.get_widget_scaling(self._scrollbar)
                actual_w = int(16 * scaling)
            if actual_w != self._scrollbar_placeholder:
                self._scrollbar_placeholder = actual_w
                self.grid_columnconfigure(7, weight=0, minsize=actual_w)
    self._canvas.bind("<Configure>", _on_canvas_configure)
```

**关键点**：
1. `update_idletasks()` 确保所有 widget 完成布局计算后再测量
2. DPI 兜底：如果 `winfo_width()` 仍返回 0，用 `ScalingTracker.get_widget_scaling()` 计算
3. `_on_canvas_configure` 在首次渲染时被触发，更新后表头 grid 自动重排，与数据区对齐
4. 调试日志作为正式实施的一部分保留（`logger.debug` 级别），用于后续排查高度问题

---

## 二、文件列表滚轮失效 + 设置页滚轮共存

### 设计约束（硬性要求）

**主页文件列表滚轮和设置页滚轮必须同时正常工作。** 上两轮优化的教训：
- 用 `bind_all`（不带 add）→ 覆盖 CTkScrollableFrame → 设置页滚轮失效
- 用 `bind`（Canvas 级别）→ 无法捕获子控件事件 → 文件列表滚轮失效
- 用 `bind_all(add="+")` + Enter/Leave 动态添加/移除 → `unbind_all` 会连带移除 CTkScrollableFrame 的处理器 → 设置页滚轮在切回主页后可能失效；且 `create_window` 内嵌控件会触发 Leave 闪烁（审阅 Q3 确认）

### 现象

当前状态：设置页滚轮正常，文件列表滚轮失效。

### 根因

`_data_frame` 通过 `Canvas.create_window()` 嵌入，其内部子控件（CTkLabel、CTkButton）**不在** tkinter widget hierarchy 中作为 Canvas 的子节点。因此：

- `self._canvas.bind("<MouseWheel>")` 只在鼠标直接悬停在 Canvas 空白区域时触发
- 鼠标悬停在 `_data_frame` 内的 Label/Button 上时，事件目标不是 Canvas，`bind` 不触发
- 而 `CTkScrollableFrame` 用 `bind_all("<MouseWheel>", handler, add="+")` 工作正常，因为 `bind_all` 捕获所有 widget 上的事件

### 修复方案（`src/gui/file_list_view.py`）— 坐标检查 + 持久全局绑定

**核心思路**：放弃 Enter/Leave + 标记位的方式（因为 `create_window` 内嵌控件会触发 Leave 闪烁，见审阅回应 Q3），改为：
- 初始化时一次性 `bind_all(add="+")` 注册全局处理器，**永不 unbind**
- 处理器内部用 **坐标检查** 判断鼠标是否在 FileListView 区域内
- 设置页的 CTkScrollableFrame 同样用 `bind_all(add="+")`，两者通过各自的坐标/层级检查互斥

**替换原有的滚轮绑定代码（约第 126-131 行），并新增实例方法**：

```python
# 在 _setup_ui() 末尾，替换原有滚轮绑定代码：
# ── 鼠标滚轮绑定 ──
# 设计目标：文件列表滚轮 和 设置页 CTkScrollableFrame 滚轮 共存
# 原理：
#   - CTkScrollableFrame 用 bind_all(add="+") + check_if_master_is_canvas() 控制
#   - 文件列表也用 bind_all(add="+") + 坐标检查控制
#   - 两者处理器共存于全局绑定链中，各自独立判断是否响应
#   - 不使用 unbind_all，避免移除对方的处理器
self.bind_all("<MouseWheel>", self._on_file_list_mousewheel, add="+")
```

```python
# 新增实例方法（在 FileListView 类中）：
def _on_file_list_mousewheel(self, event):
    """全局 MouseWheel 处理器 — 坐标检查版"""
    if not self.winfo_exists():
        return
    try:
        # 获取 FileListView 在屏幕上的区域
        rx = self.winfo_rootx()
        ry = self.winfo_rooty()
        rw = self.winfo_width()
        rh = self.winfo_height()
        # event.x_root / event.y_root 是鼠标在屏幕上的绝对坐标
        if rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    except Exception:
        pass
```

### 为什么这个方案能共存

| 场景 | 文件列表处理器 | CTkScrollableFrame 处理器 | 结果 |
|------|-------------|-------------------------|------|
| 鼠标在文件列表上滚动 | 坐标在区域内 → 滚动 | `check_if_master_is_canvas()` 返回 True → 滚动 settings canvas（但 settings 被 grid_forget，无实际效果） | **只有文件列表动** |
| 鼠标在设置页滚动 | 坐标不在区域内 → 跳过 | `check_if_master_is_canvas()` 返回 True → 正常滚动 | **只有设置页动** |
| 鼠标在其他区域滚动 | 坐标不在区域内 → 跳过 | `check_if_master_is_canvas()` 返回 False → 跳过 | **都不滚动** |

> **技术说明**：`_data_frame` 通过 `create_window` 嵌入 Canvas，其 `master` 仍是 `_canvas`，所以 CTkScrollableFrame 的 `check_if_master_is_canvas()` 对文件列表内的控件也会返回 True。但这不会造成问题——当文件列表可见时，设置页被 `grid_forget()`，其 canvas 的 scrollregion 为空，`yview_scroll` 调用无实际效果。

### 验证清单（实施后必须逐一测试）

1. **主页文件列表**：鼠标悬停在文件名上滚动 → 列表应滚动
2. **主页文件列表**：鼠标悬停在操作按钮上滚动 → 列表应滚动
3. **主页文件列表**：鼠标悬停在空白区域滚动 → 列表应滚动
4. **设置页面**：滚动到各设置区域 → 页面应正常滚动
5. **主页 → 设置**：在主页滚过列表后切到设置页 → 设置页滚轮应正常
6. **设置 → 主页**：在设置页滚过后切回主页 → 文件列表滚轮应正常

---

## 三、文件列表高度不自适应窗口大小

### 现象

文件列表可视区域偏小，且不随窗口高度变化自适应伸缩。

### 排查结果

布局链路分析（以 720px 窗口高度为例）：

```
MeetScribeApp (720px)
├── topbar row=0 weight=0 (44px)
├── content row=1 weight=1 (648px)  ← 正确填充
│   └── HomePage (648px, grid row=0 sticky="nsew")
│       ├── row=0 weight=0: title (~48px)
│       ├── row=1 weight=0: record bar (56px + 6px pady)
│       ├── row=2 weight=1: file card  ← 应该填满剩余空间
│       │   ├── row=0 weight=0: toolbar (~50px)
│       │   └── row=1 weight=1: FileListView  ← 应该填满
│       │       ├── row=0 weight=0: header (~28px)
│       │       └── row=2 weight=1: scroll_container  ← 应该填满
│       └── row=3 weight=0: log area (120px)
└── status bar row=2 weight=0 (28px)
```

从 grid 配置看，weight 链路正确。但需要排查以下可能的问题点：

1. **`card.grid_rowconfigure(1, weight=1)` 是否被 FileListView 内部的 grid 影响**：FileListView 自身的 `grid_rowconfigure(2, weight=1)` 作用域在 FileListView 内部，不影响外部 card 的 grid。
2. **`sticky="nsew"` 是否完整传递**：FileListView 在 card 中是 `grid(row=1, sticky="nsew")`，FileListView 内部的 scroll_container 也是 `grid(row=2, sticky="nsew")`。链路正确。
3. **日志区域 `sticky="sew"`**：log_card 在 row=3 使用 `sticky="sew"`（不含 n），这不影响 row=2 的扩展。

### 修复方案

**Step 1：确认 FileListView 的 `grid_rowconfigure` 正确**

检查 FileListView 的 `_setup_ui()` 中：

```python
# 确认 row=2 的 weight=1 已设置（已有）
self.grid_rowconfigure(2, weight=1)
```

**Step 2：确认 scroll_container 的 rowconfigure**

`_scroll_container` 内部只有 row=0（canvas），需要设置 weight=1：

```python
# 当前代码已有：
self._scroll_container.grid_columnconfigure(0, weight=1)
# 新增：
self._scroll_container.grid_rowconfigure(0, weight=1)
```

**Step 3：加调试日志，用实测数据判断后续**

调试日志已合并在问题 1 的 `_on_canvas_configure` 中（输出 Canvas、scroll_container、FileListView、scrollbar 的实际尺寸）。MiMo Code 实施后请运行程序，查看日志数据：

- 如果 Canvas 高度随窗口变化 → 问题已解决
- 如果 Canvas 高度固定不变 → 需要进一步排查

**Step 4：如果仍不自适应的备选方案**

根据调试日志数据，可能需要：

```python
# 方案 A：设极小最小高度，让 grid weight 来扩展
self._canvas.configure(height=1)

# 方案 B：在 _on_canvas_configure 中强制高度
# （已由 itemconfig width=event.width 处理宽度，高度类似）
```

**不猜测，用数据说话。** 请先加日志实测，再决定是否需要额外调整。

---

## 四、设置页"关于"区域信息过时 + 缺少制作者

### 现象

1. "关于"区域显示 "MeetScribe **v3.0**"，但 TopBar 显示 "**v0.9**"，版本号矛盾
2. 没有显示制作者"刘家诚"
3. AI 引擎描述 "Ollama 本地 (姓名提取)" 可能已过时

### 根因

`_build_about_section()` 硬编码了旧版本信息（第 373-378 行），且从未包含制作者字段。

### 修复方案（`src/gui/styles.py` + `src/gui/settings_page.py` + `src/gui/topbar.py`）

**Step 1：在 `styles.py` 顶部常量区域定义版本常量**

```python
# 在 styles.py 顶部常量区域添加（不是末尾）：
APP_VERSION = "0.9"   # 待用户确认最终版本号
APP_NAME = "MeetScribe"
```

**Step 2：`topbar.py` 引用常量**

```python
from .styles import APP_VERSION, APP_NAME

# 替换硬编码版本号（约第 73 行）：
# 原：text=f"v0.9 | FunASR"
# 改：text=f"v{APP_VERSION} | FunASR"
```

**Step 3：重写 `_build_about_section()`**

```python
def _build_about_section(self, parent):
    """构建关于部分"""
    self._s_title(parent, "关于")
    about_card = self._s_card(parent)
    about_f = ctk.CTkFrame(about_card, fg_color="transparent")
    about_f.pack(fill="x", padx=16, pady=14)

    # 软件名称 + 版本号（引用常量，与 topbar 保持一致）
    ctk.CTkLabel(
        about_f, text=f"{APP_NAME} v{APP_VERSION}  —  会议录音转写助手",
        font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        text_color=C_TXT1, anchor="w",
    ).pack(anchor="w", pady=(0, 4))

    # 制作者
    ctk.CTkLabel(
        about_f, text="制作者：刘家诚",
        font=ctk.CTkFont(family=FONT_FAMILY, size=12),
        text_color=C_TXT2, anchor="w",
    ).pack(anchor="w", pady=2)

    # 技术栈信息
    for line in [
        "引擎: FunASR SenseVoice + CAM++ + ct-punc (本地推理)",
        "AI: MiMo 云端 (摘要 / 纠错)",
        "支持格式: WAV / MP3 / M4A / FLAC / OGG / OGA / OPUS",
    ]:
        ctk.CTkLabel(
            about_f, text=line,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=C_TXT2, anchor="w",
        ).pack(anchor="w", pady=2)
```

**关键变更**：
- 版本号统一引用 `APP_VERSION` 常量，消除多处硬编码
- 新增"制作者：刘家诚"行
- 移除 "Ollama 本地 (姓名提取)" 描述（如确实不再使用；如果仍在使用则保留）
- 软件名称行加粗，与其他行形成层次
- 版本号具体值（v0.9 / v1.0 / v3.2）待用户确认，后续只需改 `styles.py` 一处

---

## 五、API Key 输入框优化（加宽 + 明文/密文切换）

### 现象

API Key 输入框 width=180，对于 40+ 字符的 API Key 太短，无法完整核对。且只有密文显示（`show="*"`），没有切换明文的按钮。

### 修复方案（`src/gui/settings_page.py`）

修改 `_build_ai_section()` 中的 API Key 行（约第 178-190 行）：

```python
# --- Row 3: API Key ---
r_api = ctk.CTkFrame(card, fg_color="transparent")
r_api.pack(fill="x", padx=16, pady=(4, 4))
ctk.CTkLabel(r_api, text="API Key", width=90, anchor="w",
             font=ctk.CTkFont(family=FONT_FAMILY, size=12),
             text_color=C_TXT2).pack(side="left")
self._api_key_var = ctk.StringVar()
self._api_key_entry = ctk.CTkEntry(
    r_api, textvariable=self._api_key_var, show="*",
    width=280, height=30, corner_radius=6,
    font=ctk.CTkFont(family=FONT_FAMILY, size=12),
    border_color=C_BORDER, fg_color=C_BG,
)
self._api_key_entry.pack(side="left", padx=(0, 4))

# 明文/密文切换按钮（复用项目现有 emoji 风格，与 ICON_ACTION["preview"] 一致）
self._api_key_visible = False
self._api_key_toggle = ctk.CTkButton(
    r_api, text="👁", width=30, height=30, corner_radius=6,
    font=ctk.CTkFont(family=FONT_FAMILY, size=14),
    fg_color=C_BG, text_color=C_TXT2, border_width=1, border_color=C_BORDER,
    hover_color="#EAEAEA",
    command=self._toggle_api_key_visibility,
)
self._api_key_toggle.pack(side="left")
```

**新增切换方法**：

```python
def _toggle_api_key_visibility(self):
    """切换 API Key 明文/密文显示"""
    self._api_key_visible = not self._api_key_visible
    if self._api_key_visible:
        self._api_key_entry.configure(show="")
        self._api_key_toggle.configure(text="🔒")
    else:
        self._api_key_entry.configure(show="*")
        self._api_key_toggle.configure(text="👁")
```

**变更要点**：
- Entry width: 180 → 280（加宽 100px，足够显示完整 API Key）
- 新增 👁/🔒 切换按钮，点击切换 show="" / show="*"
- 按钮风格与"浏览"按钮一致（`fg_color=C_BG, border_width=1, border_color=C_BORDER`）
- emoji 图标直接复用项目现有的（`ICON_ACTION["preview"]` 已使用 "👁"），无需替换为 Unicode 符号

---

## 六、修正汇总

| # | 问题 | 文件 | 改动要点 |
|---|------|------|---------|
| 1 | 列头错位 | `file_list_view.py` | 动态测量滚动条实际宽度 + `update_idletasks()` + DPI 兜底 |
| 2 | 滚轮共存 | `file_list_view.py` | 坐标检查 + 持久 bind_all(add="+")，不用 unbind_all |
| 3 | 高度不自适应 | `file_list_view.py` | scroll_container 加 grid_rowconfigure(0, weight=1) + 调试日志实测 |
| 4 | 关于信息过时 | `styles.py` + `settings_page.py` + `topbar.py` | APP_VERSION 常量 + 制作者 + 统一引用 |
| 5 | API Key 太短 | `settings_page.py` | Entry 加宽到 280px + 眼睛切换按钮（复用现有 emoji） |

---

## 七、文件变更索引

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/gui/styles.py` | 修改 | 顶部新增 APP_VERSION / APP_NAME 常量 |
| `src/gui/file_list_view.py` | 修改 | 问题 1（动态滚动条宽度 + 调试日志）+ 问题 2（坐标检查 bind_all 修复）+ 问题 3（rowconfigure） |
| `src/gui/settings_page.py` | 修改 | 问题 4（关于区域重写，引用 APP_VERSION）+ 问题 5（API Key 加宽+切换按钮） |
| `src/gui/topbar.py` | 修改 | 版本号改用 APP_VERSION 常量 |

---

## 八、实施注意事项

1. **问题 1、2、3 都在 `file_list_view.py` 的 `_setup_ui()` 方法中，请合并修改，不要分别 patch**
2. **问题 2 的滚轮共存是硬性要求**：坐标检查方案是唯一的正式方案，不要用 `unbind_all`（会移除 CTkScrollableFrame 的处理器）。实施后必须按验证清单逐一测试 6 个场景
3. **问题 3 加 `grid_rowconfigure(0, weight=1)` 后需要实际拖拽窗口测试高度是否跟随变化**，同时查看调试日志中的尺寸数据
4. **问题 4 的版本号 `APP_VERSION = "0.9"` 需与用户确认最终值**，后续只需改 styles.py 一处
5. **问题 5 的 emoji 图标**直接复用项目现有风格（`ICON_ACTION["preview"]` 已使用 "👁"），无需替换
