#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe AI 服务模块
封装云端 API（会议摘要）和本地 Ollama LLM（说话人姓名提取）
"""

import json
import logging
from openai import OpenAI

logger = logging.getLogger("MeetScribe")

# ── 默认配置 ──────────────────────────────────────────────

# 云端 API
_DEFAULT_MODEL = "mimo-v2.5-pro"
_CLOUD_TIMEOUT = 120  # 秒（长文本摘要可能需要更长时间）

# 本地 Ollama
_OLLAMA_DEFAULT_URL = "http://localhost:11434/v1"
_OLLAMA_DEFAULT_MODEL = "qwen3:1.7b"
_OLLAMA_TIMEOUT = 10  # 秒


class AIService:
    """
    MeetScribe AI 服务

    提供两项核心能力：
    1. generate_summary   — 调用云端大模型生成结构化会议纪要
    2. extract_speaker_names — 调用本地 Ollama 从转写文本中提取说话人真实姓名
    """

    def __init__(
        self,
        vendor: str = "",
        model: str = None,
        access_mode: str = "按量计费",
        api_key: str = "",
        ollama_url: str = None,
        ollama_model: str = None,
        ollama_enabled: bool = True,
    ):
        """
        初始化 AI 服务

        Args:
            vendor:       AI 厂商名称（如 "小米"、"智谱" 等）
            model:        模型名称，默认 mimo-v2.5-pro
            access_mode:  访问模式（"按量计费" 或 "token_plan"）
            api_key:      云端 API Key（必填才能使用摘要功能）
            ollama_url:   Ollama 服务地址，默认 http://localhost:11434/v1
            ollama_model: Ollama 模型名称，默认 qwen3:1.7b
            ollama_enabled: 是否启用本地 Ollama LLM（默认 True）
        """
        self.vendor = vendor
        self.model = model or _DEFAULT_MODEL
        self.access_mode = access_mode
        self.api_key = api_key
        self.base_url = self._resolve_base_url()

        self.ollama_enabled = ollama_enabled
        self.ollama_url = ollama_url or _OLLAMA_DEFAULT_URL
        self.ollama_model = ollama_model or _OLLAMA_DEFAULT_MODEL

        # 延迟初始化客户端实例（避免未使用时也要建立连接）
        self._ai_client = None
        self._ollama_client = None

    def _resolve_base_url(self):
        """从 model_registry 查表获取 base URL"""
        from model_registry import get_base_url
        # Normalize model name to lowercase for registry lookup
        model_lower = self.model.lower() if self.model else ""
        return get_base_url(self.vendor, model_lower, self.access_mode)

    # ── 客户端属性 ────────────────────────────────────────

    @property
    def ai_client(self):
        """获取云端 OpenAI 兼容客户端（懒加载）"""
        if self._ai_client is None:
            if not self.api_key:
                return None
            self._ai_client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={"api-key": self.api_key},
                timeout=_CLOUD_TIMEOUT,
            )
        return self._ai_client

    @property
    def ollama_client(self) -> OpenAI:
        """获取本地 Ollama OpenAI 兼容客户端（懒加载）"""
        if self._ollama_client is None:
            self._ollama_client = OpenAI(
                base_url=self.ollama_url,
                api_key="ollama",  # Ollama 不校验 key，但 SDK 要求非空
            )
        return self._ollama_client

    # ── 公开方法 ──────────────────────────────────────────

    def generate_correction(self, transcript: str, model: str = None) -> str:
        """
        调用 LLM 对 ASR 转写结果进行纠错后处理

        修正内容：语音识别错字、无意义乱码 token、标点补充、去除口语填充词。
        不改变原意、不增删内容、保留说话人标签和时间戳格式。

        Args:
            transcript: ASR 原始转写文本（Markdown 格式，含时间戳和说话人标签）
            model:      指定模型名称，默认使用构造函数中的配置

        Returns:
            str: 纠错后的转写文本；若失败则返回 None（调用方应保留原文）
        """
        if not self.api_key or not self.ai_client:
            logger.warning("未配置云端 API Key，跳过 LLM 纠错")
            return None

        use_model = model or self.model

        system_prompt = (
            "你是一位专业的语音转写纠错助手。以下是语音识别（ASR）自动生成的会议转写文本，"
            "请对其进行纠错校对。\n\n"
            "纠错规则：\n"
            "1. 修正语音识别的错字、同音词误识别（如 \u201c领导师\u201d\u2192\u201c领导的\u201d、"
            "\u201c批量新店\u201d\u2192\u201c批量新增\u201d）\n"
            "2. 删除无意义的乱码 token（如日文假名混合碎片：\u3069\u3044、\u3066\u6211\u306a、\u3042、\u30bb 等）\n"
            "3. 去除口语中的纯填充词（\u201c呃\u201d\u3001\u201c嗯\u201d\u3001\u201c啊\u201d作为语气词时），"
            "但保留有实际语义的语气词\n"
            "4. 补充缺失的标点符号（逗号、句号、问号），使语句通顺可读\n"
            "5. 删除只有标点或空白的无效段落\n\n"
            "严格要求：\n"
            "- 保持原文意思不变，不得添加原文中没有的内容\n"
            "- 保留所有说话人标签（如 Speaker 1、**[00:00] xxx**）和时间戳不变\n"
            "- 保留原始的段落结构和 Markdown 格式\n"
            "- 如果某段文字无法确定正确内容，保持原样不修改\n"
            "- 直接输出纠错后的完整文本，不要输出解释说明"
        )

        # 按段落分块处理，避免超出上下文窗口
        chunks = self._split_transcript_chunks(transcript, max_chars=4000)
        corrected_chunks = []

        logger.info(f"LLM 纠错: {len(chunks)} 个分块，模型 {use_model}")

        for i, chunk in enumerate(chunks):
            logger.info(f"  纠错分块 {i+1}/{len(chunks)} ({len(chunk)} 字)...")
            try:
                response = self.ai_client.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"以下是需要纠错的转写文本：\n\n{chunk}"},
                    ],
                    max_completion_tokens=4096,
                    temperature=0.1,
                    timeout=_CLOUD_TIMEOUT,
                )
                result = response.choices[0].message.content
                if result and result.strip():
                    corrected_chunks.append(result.strip())
                else:
                    # LLM 返回空，保留原文
                    corrected_chunks.append(chunk)
            except Exception as e:
                logger.warning(f"LLM 纠错分块 {i+1} 失败: {e}，保留原文")
                corrected_chunks.append(chunk)

        corrected = "\n\n".join(corrected_chunks)
        if corrected == transcript:
            logger.info("LLM 纠错完成（无变化）")
            return None
        logger.info("LLM 纠错完成")
        return corrected

    @staticmethod
    def _split_transcript_chunks(text: str, max_chars: int = 4000) -> list:
        """
        将转写文本按说话人段落分块，每块不超过 max_chars 字符。
        在说话人标签处断开，保证每块内容完整。
        """
        if len(text) <= max_chars:
            return [text]

        lines = text.split("\n")
        chunks = []
        current = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            # 如果当前行是说话人段落起始，且当前块已较大，则换块
            is_speaker_start = (
                line.startswith("[") and "**" in line
            ) or line.startswith("## ")
            if is_speaker_start and current_len > max_chars * 0.5 and current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += line_len

        if current:
            chunks.append("\n".join(current))

        return chunks if chunks else [text]

    def generate_summary(self, transcript: str, model: str = None,
                         voiceprint_matches: dict = None) -> str:
        """
        调用云端大模型生成结构化会议纪要

        Args:
            transcript:          会议转写文本（Markdown 或纯文本均可）
            model:               指定模型名称，默认使用构造函数中的配置
            voiceprint_matches:  音色库匹配结果，格式 {spk_id: {"name": str, "confidence": str}}

        Returns:
            str: 结构化的会议纪要文本；若失败则返回以 "[错误]" 开头的提示信息
        """
        if not self.api_key or not self.ai_client:
            return "[错误] 未配置云端 API Key，无法生成会议摘要。请在设置中填写 API Key。"

        use_model = model or self.model

        # 构建已知说话人信息
        known_speakers_section = ""
        if voiceprint_matches:
            known_lines = []
            for spk_id, info in voiceprint_matches.items():
                known_lines.append(f"- Speaker {spk_id + 1} = {info['name']}（音色库匹配，置信度: {info['confidence']}）")
            known_speakers_section = "\n\n【已识别的说话人（音色库匹配结果，请在参会人员中使用这些姓名）】\n" + "\n".join(known_lines)

        # 构造系统提示词：要求模型输出结构化的中文会议纪要
        system_prompt = (
            "你是一位专业的会议纪要整理助手。请根据提供的会议转写内容，"
            "整理出结构化的会议纪要。\n\n"
            "## 输出格式\n\n"
            "### 会议主题\n"
            "（用 10-20 个字概括会议核心主题）\n\n"
            "### 参会人员\n"
            "列出所有参会人员，每人一行。\n\n"
            "规则：\n"
            "- 【必须】使用 `[Speaker N] 姓名` 格式，不要直接用姓名作为标识符\n"
            "- 如果该说话人已被音色库识别（见下方\u201c已识别的说话人\u201d），"
            "直接使用该姓名，格式为 `[Speaker N] 姓名`，不要添加任何角色推断\n"
            "- 如果转写内容中显示该说话人的真实姓名（如自我介绍、称呼），"
            "直接使用该姓名，格式为 `[Speaker N] 姓名`\n"
            "- 只有在完全无法确定姓名时，才根据发言内容推断角色，"
            "格式为 `[Speaker N]（角色推断：XXX）`\n"
            "- 【禁止】使用\u201c未识别姓名\u201d、\u201c未知\u201d、\u201cUnknown\u201d等占位符\n\n"
            "示例格式（必须严格遵守）：\n"
            "- [Speaker 1] 万斌\n"
            "- [Speaker 2] 宋琳琳\n"
            "- [Speaker 3]（角色推断：项目经理）\n\n"
            "### 讨论要点\n"
            "（分条列出讨论的核心内容，每条包含简要标题和详细说明）\n\n"
            "### 决策事项\n"
            "（列出会议中做出的决定；如无则注明\u201c本次会议无明确决策\u201d）\n\n"
            "### 待办事项\n"
            "（列出需要后续跟进的任务，注明负责人和截止时间）\n\n"
            "## 写作要求\n"
            "- 语言简洁、专业，保留关键数据和具体细节\n"
            "- 在讨论要点和待办事项中，使用人名而非 Speaker 编号\n"
            f"{known_speakers_section}"
        )

        logger.info(f"正在调用云端 API 生成会议摘要（厂商: {self.vendor}, 模型: {use_model}）...")

        try:
            response = self.ai_client.chat.completions.create(
                model=use_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"以下是会议转写内容，请整理会议纪要：\n\n{transcript}"},
                ],
                max_completion_tokens=4096,
                temperature=0.3,
                timeout=_CLOUD_TIMEOUT,
            )

            summary = response.choices[0].message.content
            if not summary or not summary.strip():
                logger.warning("云端 API 返回了空内容")
                return "[错误] 云端 API 返回了空内容，请重试。"

            logger.info("会议摘要生成成功")
            return summary.strip()

        except Exception as e:
            error_msg = f"调用云端 API 生成摘要失败: {e}"
            logger.error(error_msg)
            return f"[错误] 生成会议摘要失败：{e}"

    def extract_speaker_names(self, transcript: str, speaker_ids: list, model: str = None) -> dict:
        """
        调用本地 Ollama LLM 从转写文本中提取说话人真实姓名

        通过分析转写内容中的称呼、自我介绍等上下文线索，
        尝试将 Speaker ID 映射到真实姓名。

        Args:
            transcript:   会议转写文本
            speaker_ids:  说话人 ID 列表，如 [0, 1, 2] 或 ["0", "1"]
            model:        指定 Ollama 模型名称，默认使用构造函数中的配置

        Returns:
            dict: 说话人 ID 到姓名的映射，如 {"0": "张三", "1": "李四"}
                  如果无法提取或 Ollama 不可用，返回空字典
        """
        if not speaker_ids:
            return {}

        if not self.ollama_enabled:
            logger.info("本地 Ollama 已禁用，跳过说话人姓名提取")
            return {}

        use_model = model or self.ollama_model

        # 统一将 speaker_ids 转为字符串列表
        str_ids = [str(sid) for sid in speaker_ids]
        ids_display = ", ".join(str_ids)

        # 构造提取提示词
        system_prompt = (
            "你是一位擅长从会议记录中提取信息的助手。"
            "请根据会议转写内容中的称呼、自我介绍、对话上下文等线索，"
            "识别出每位说话人的真实姓名。\n\n"
            "要求：\n"
            "- 仅输出 JSON 格式，不要输出任何其他内容\n"
            "- JSON 的 key 为说话人 ID（字符串），value 为推测的真实姓名\n"
            "- 如果无法确定某位说话人的姓名，不要包含在 JSON 中\n"
            "- 不要编造姓名，只根据文本中的实际线索推断"
        )

        user_prompt = (
            f"以下是会议转写内容，其中说话人以 Speaker ID 标记（ID 列表: {ids_display}）。\n"
            f"请提取每位说话人的真实姓名，返回 JSON。\n\n"
            f"{transcript}"
        )

        logger.info(f"正在调用本地 Ollama 提取说话人姓名（模型: {use_model}）...")

        try:
            response = self.ollama_client.chat.completions.create(
                model=use_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_completion_tokens=256,
                temperature=0.1,
                timeout=_OLLAMA_TIMEOUT,
            )

            raw = response.choices[0].message.content
            if not raw or not raw.strip():
                logger.warning("Ollama 返回了空内容，无法提取说话人姓名")
                return {}

            # 解析 LLM 返回的 JSON
            result = self._parse_speaker_json(raw.strip())
            if result:
                logger.info(f"成功提取说话人姓名: {result}")
            else:
                logger.warning("Ollama 返回内容无法解析为有效的说话人映射")
            return result

        except Exception as e:
            # Ollama 未运行或连接失败时，优雅降级
            error_str = str(e).lower()
            if "connection" in error_str or "timeout" in error_str or "refused" in error_str:
                logger.warning(
                    f"本地 Ollama 服务不可用（{e}），跳过说话人姓名提取。"
                    "请确认 Ollama 已启动：ollama serve"
                )
            else:
                logger.error(f"调用 Ollama 提取说话人姓名失败: {e}")
            return {}

    # ── 内部方法 ──────────────────────────────────────────

    @staticmethod
    def _parse_speaker_json(raw: str) -> dict:
        """
        解析 LLM 返回的 JSON 文本，提取说话人姓名映射

        处理 LLM 可能用 ```json ... ``` 包裹、或混入解释文本的情况。

        Args:
            raw: LLM 返回的原始文本

        Returns:
            dict: 解析后的 {speaker_id: name} 映射，失败返回空字典
        """
        text = raw.strip()

        # 尝试剥离 Markdown 代码块包裹
        if "```" in text:
            # 提取 ``` 和 ``` 之间的内容
            parts = text.split("```")
            for part in parts:
                # 去掉可能的语言标识符（如 "json"）
                part = part.strip()
                if part.lower().startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    text = part
                    break

        # 尝试直接解析
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                # 确保 key 和 value 都是字符串
                return {str(k): str(v) for k, v in data.items() if v}
            return {}
        except json.JSONDecodeError:
            pass

        # 最后尝试从文本中找到第一个 { ... } 块
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items() if v}
            except json.JSONDecodeError:
                pass

        return {}
