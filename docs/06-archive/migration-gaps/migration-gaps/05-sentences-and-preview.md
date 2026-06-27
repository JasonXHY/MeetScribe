# 深度排查：sentences参数 + 转写预览Markdown渲染

> **用户决策（2026-06-25）**：Markdown渲染采用方案B — QTextBrowser + markdown库（+2-5MB增量）。

## 问题概述

1. `_open_speaker_modal` 未传递 `sentences` 参数给 SpeakerDialog
2. 转写预览和AI摘要预览使用纯文本显示，缺少markdown格式化

## 问题1：sentences参数未传递

### 差异分析

**旧版**：从 `handler._sentences` 获取句子数据，传递给 SpeakerDialog
**新版**：完全遗漏了 sentences 的获取和传递

### 影响

- SpeakerDialog 中无法显示逐句对齐信息
- 声纹比对时缺少时间戳参考

### 修复

在 `home_page.py` 的 `_open_speaker_modal` 中恢复 sentences 获取和传递。

## 问题2：转写预览Markdown渲染

### 当前现状

项目当前没有进行任何Markdown渲染，全部以纯文本方式显示。

### 各方案体积对比

| 方案 | 打包增量 | 渲染能力 | 推荐度 |
|------|---------|---------|-------|
| A. QPlainTextEdit（当前） | 0 MB | 纯文本 | 当前方案 |
| B. QTextBrowser + markdown库 | +2-5 MB | 基础富文本 | 推荐 |
| C. 正则自实现 | 0 MB | 仅4种基础语法 | 极致轻量 |
| D. QWebEngineView | +200-300 MB | 完整浏览器 | 不推荐 |

### 建议

选择方案B（QTextBrowser + markdown库）。体积增量仅2-5MB，相对于项目已有的几百MB完全可忽略。
