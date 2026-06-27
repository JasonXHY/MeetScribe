# 迁移Gap修复方案 — 请mimo复核

## 背景

QoderWork对 C:\侧耳倾听\docs\migration-gaps\ 下的5个迁移问题进行了深度排查，用户已逐一确认修复方案。请mimo复核以下4个修复方案，重点检查：
1. 方案是否可行，有没有遗漏的改动点
2. 修改是否会影响到现有正常工作的功能（特别是话题显示、转写流程）
3. 代码位置和行号是否准确
4. 有没有潜在的副作用或风险

---

## 修复项1：声纹embedding保存恢复

**决策**：方案A — 最小修复

**问题**：transcription.py 中 _save_embeddings_to_disk() 方法在迁移时丢失，导致每次转写产生的 _speaker_embeddings 仅存于内存，程序退出后全部丢失。

**修复内容**：

1. 在 transcription.py 中恢复 _save_embeddings_to_disk() 方法
   - 参考旧版实现：C:\Users\kingdee\Desktop\侧耳倾听-评审材料\src_old\transcription.py 第360-399行
   - 遍历 self._current_batch_paths，每个文件生成 {base}_embeddings.json
   - 保存格式：{spk_id: {"vector": [...], "quality": 0.85}}

2. 在 _on_done() 方法中，声纹匹配之后、资源清理之前调用它
   - 位置：transcription.py 约第287-321行的 _on_done() 方法

3. 可选：在 TranscriptionHandler.__init__() 或 start() 中预加载历史embeddings

**涉及文件**：
- C:\侧耳倾听\src\gui\transcription.py

**详细文档**：C:\侧耳倾听\docs\migration-gaps\01-embeddings-save-missing.md

---

## 修复项2：转写后处理异步化

**决策**：方案A — QThread包装AI调用 + 每步状态更新

**问题**：转写完成后的所有后处理（AI纠错5-120s、声纹匹配0.5s、姓名应用0.1-10s、AI摘要10-120s）都在主线程同步执行，总阻塞17-250秒，UI完全冻结。

**额外Bug**：_apply_speaker_names() 在 auto_summary 消息和 _on_done() 中各执行一次，没有防重入保护。

**修复内容**：

1. 创建 AICorrectionWorker(QThread) 和 AISummaryWorker(QThread)
   - 将 _generate_correction() 和 _generate_summary() 移入QThread
   - 通过信号回调结果，主线程不阻塞

2. 每个后处理步骤前后更新状态
   - 新增信号 post_process_status = Signal(str)
   - 发射 "正在进行AI纠错..."、"正在声纹匹配..."、"正在生成摘要..." 等

3. 修复 _apply_speaker_names() 重复执行
   - 增加 _names_applied 防重入标记

4. 处理线程生命周期（程序退出时等待/终止Worker线程）

**依赖关系（必须保持的串行顺序）**：
- AI纠错 -> AI摘要（摘要需要纠错后的文本）
- 声纹匹配 -> 姓名应用（confirmed集合决定优先级）
- 声纹匹配 -> AI摘要（摘要prompt需要声纹信息）

**涉及文件**：
- C:\侧耳倾听\src\gui\transcription.py

**详细文档**：C:\侧耳倾听\docs\migration-gaps\03-auto-correction-summary-sync.md

---

## 修复项3：任务状态显示修复

**决策**：做第一步和第二步，进度条暂不做

**问题1（P0）**：home_page.py 第600-603行 _on_progress_updated() 用 hasattr(progress, 'stage') 检查dict，对dict调用hasattr检查的是属性而非键，永远返回False，进度文本从未更新。

**问题2（P0）**：转写过程中 _btn_ai_summary 未被禁用，用户可能误操作。

**问题3**：停止按钮信号混淆 — 转写时启用的stop_btn连接的是 _stop_recording 而非停止转写。

**修复内容**：

**第一步：修复hasattr bug + 按钮状态管理**

1. 修改 _on_progress_updated() — home_page.py 第600-603行
   - 改为 isinstance(progress, dict) + dict键访问
   - 兼容 hasattr 分支（以防未来传入对象）

2. 转写开始时禁用AI摘要按钮 — home_page.py 约第943-959行
   - 添加 self._btn_ai_summary.setEnabled(False)
   - 转写完成时恢复

**第二步：增加后处理状态显示**

1. 在 transcription.py 中新增信号 post_process_status = Signal(str)
2. 在每个后处理步骤前发射状态文本
3. 在 home_page.py 中连接此信号到 _recording_bar.update_queue_status()

**涉及文件**：
- C:\侧耳倾听\src\gui\home_page.py
- C:\侧耳倾听\src\gui\transcription.py

**详细文档**：C:\侧耳倾听\docs\migration-gaps\04-progress-display.md

---

## 修复项4：Markdown渲染

**决策**：方案B — QTextBrowser + markdown库

**问题**：AI摘要中的markdown内容以纯文本显示，阅读体验差。

**修复内容**：

1. requirements.txt 添加 markdown>=3.4.0

2. 修改 PreviewDialog（dialogs.py）
   - 将 QPlainTextEdit 替换为 QTextBrowser
   - _show_transcript() 保持 setPlainText()
   - _show_summary() 使用 markdown.markdown() 转HTML后 setHtml()
   - 添加基础CSS样式

3. PyInstaller打包：hiddenimports 添加 markdown，体积增量约2-5MB

**涉及文件**：
- C:\侧耳倾听\src\gui\dialogs.py
- C:\侧耳倾听\requirements.txt

**详细文档**：C:\侧耳倾听\docs\migration-gaps\05-sentences-and-preview.md

---

## 复核要点

请mimo重点检查：

1. **功能安全性**：以上修改是否影响当前正常功能？特别是：
   - 话题显示（已确认修复，不能破坏）
   - 转写流程完整性
   - file_history.json / voiceprint_library.json 读写

2. **线程安全**：修复项2的QThread方案
   - Worker线程中是否访问了Qt GUI对象？（不允许）
   - 信号槽连接方式是否正确？（跨线程需QueuedConnection）
   - 程序退出时线程是否能安全终止？

3. **数据一致性**：修复项1的embedding保存
   - 保存时机是否正确？
   - 加载时是否需要校验？

4. **遗漏检查**：
   - _on_progress_updated 还有没有其他连接点？
   - _apply_speaker_names() 防重入标记是否影响其他逻辑？

5. **代码位置确认**：行号是否准确？（代码可能已被修改）
