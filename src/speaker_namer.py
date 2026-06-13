#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeetScribe 说话人姓名提取模块
通过正则表达式 + 可选 LLM 兜底，从会议转写文本中识别各说话人的真实姓名
"""

import re
import logging
from collections import defaultdict

logger = logging.getLogger("MeetScribe")


class SpeakerNamer:
    """从会议转写文本中提取说话人真实姓名"""

    # ──────────────────────────────────────────────────────────
    #  中文姓名正则模式
    # ──────────────────────────────────────────────────────────

    # 常见中文姓氏（复姓 + 高频单姓），用于限定匹配范围，避免误提取
    _COMMON_SURNAMES = (
        # 复姓
        "欧阳|司马|上官|诸葛|司徒|令狐|宇文|慕容|皇甫|东方|"
        # 高频单姓（覆盖 >95% 人口）
        "王|李|张|刘|陈|杨|赵|黄|周|吴|徐|孙|胡|朱|高|林|"
        "何|郭|马|罗|梁|宋|郑|谢|韩|唐|冯|于|董|萧|程|曹|"
        "袁|邓|许|傅|沈|曾|彭|吕|苏|卢|蒋|蔡|贾|丁|魏|薛|"
        "叶|阎|余|潘|杜|戴|夏|钟|汪|田|任|姜|范|方|石|姚|"
        "谭|廖|邹|熊|金|陆|郝|孔|白|崔|康|毛|邱|秦|江|史|"
        "顾|侯|邵|孟|龙|万|段|雷|钱|汤|尹|黎|易|常|武|乔|"
        "贺|赖|龚|文|庞|樊|兰|殷|施|陶|洪|翟|安|颜|倪|严|"
        "牛|温|芦|季|俞|章|鲁|葛|伍|韦|申|尤|毕|聂|丛|焦"
    )

    # 姓氏字符类（含复姓首字），用于宽泛匹配
    _SURNAME_CHAR = (
        r"[\u4e00-\u9fff]"  # 退化为任意汉字，在非严格位置使用
    )

    # ── 自报姓名类 ──────────────────────────────────────────
    # "我姓蒋" / "我姓张"
    _PAT_XING = re.compile(
        r"我姓(?P<name>(?:" + _COMMON_SURNAMES + r")[\u4e00-\u9fff]{0,2})"
    )
    # "我是蒋博" / "我叫蒋博"
    _PAT_SHI_JIAO = re.compile(
        r"我(?:是|叫)(?P<name>(?:" + _COMMON_SURNAMES + r")[\u4e00-\u9fff]{0,3})"
    )

    # ── 称呼类（他人提及） ──────────────────────────────────
    # "X老师" / "X部长" / "X总" / "X总经理" / "X主任" / "X经理"
    # "X处长" / "X科长" / "X博士" / "X工"
    #
    # 使用双模式策略，平衡召回率与精确度：
    #   模式 A（严格）：首字须为已知姓氏，后接 0-2 字 + 任意称呼
    #                  → 覆盖 "张工"、"蒋博老师"、"王总" 等
    #   模式 B（宽松）：任意汉字 2-3 字 + 仅双字及以上称呼
    #                  → 覆盖非常见姓氏如 "腾飞部长"、"欧阳明主任" 等
    #                  → 排除单字称呼（"总"/"工"），避免 "施工"、"这个总" 等误匹配
    _TITLE_ALL = (
        r"(?P<title_a>老师|部长|总经理|总|主任|经理|处长|科长|博士|工)"
    )
    _TITLE_LONG = (
        r"(?P<title_b>老师|部长|总经理|主任|经理|处长|科长|博士)"
    )
    _PAT_TITLE_STRICT = re.compile(
        r"(?P<name>(?:" + _COMMON_SURNAMES + r")[\u4e00-\u9fff]{0,2})"
        + _TITLE_ALL
    )
    _PAT_TITLE_OPEN = re.compile(
        r"(?P<name>[\u4e00-\u9fff]{2,3})" + _TITLE_LONG
    )

    # ── 转写文本行解析：[00:01:23] Speaker 1: 内容 ──────────
    _PAT_LINE = re.compile(
        r"^\[(?:\d{1,2}:)?\d{2}:\d{2}\]\s+Speaker\s+(?P<sid>\d+)\s*[:：]\s*(?P<text>.+)$"
    )

    # ── 姓氏首字校验（编译一次，用于快速判断字符串是否以已知姓氏开头）──
    _PAT_STARTS_WITH_SURNAME = re.compile(
        r"^(?:" + _COMMON_SURNAMES + r")"
    )

    # ──────────────────────────────────────────────────────────
    #  公开方法
    # ──────────────────────────────────────────────────────────

    def extract_names_regex(
        self, transcript: str, speaker_ids: list
    ) -> dict:
        """
        纯正则方式提取说话人姓名。

        Parameters
        ----------
        transcript : str
            完整转写文本（多行，每行格式: [HH:MM:SS] Speaker N: 内容）
        speaker_ids : list
            需要识别的说话人 ID 列表，如 ["0", "1", "4"]

        Returns
        -------
        dict
            映射 {speaker_id: 姓名}，仅包含成功识别的说话人
            示例: {"0": "蒋博", "4": "腾飞部长"}
        """
        # 将 speaker_ids 统一为字符串
        sid_set = {str(s) for s in speaker_ids}

        # 按说话人 ID 分组转写文本行
        segments = self._parse_transcript(transcript, sid_set)

        result = {}
        for sid in sid_set:
            lines = segments.get(sid, [])
            if not lines:
                logger.debug(f"Speaker {sid}: 未找到对应转写行，跳过")
                continue

            name = self._extract_name_for_lines(lines)
            if name:
                result[sid] = name
                logger.info(f"Speaker {sid}: 正则匹配到姓名 -> {name}")
            else:
                logger.debug(f"Speaker {sid}: 正则未匹配到姓名")

        logger.info(
            f"正则提取完成: {len(result)}/{len(sid_set)} 个说话人已识别"
        )
        return result

    def extract_names(
        self,
        transcript: str,
        speaker_ids: list,
        ai_service=None,
    ) -> dict:
        """
        提取说话人姓名（正则优先 + 可选 LLM 兜底）。

        Parameters
        ----------
        transcript : str
            完整转写文本
        speaker_ids : list
            需要识别的说话人 ID 列表
        ai_service : object, optional
            AI 服务实例（来自 ai_service.py），需具备
            extract_speaker_names(transcript, speaker_ids) 方法

        Returns
        -------
        dict
            映射 {speaker_id: 姓名}
        """
        # 第一步：正则提取
        regex_result = self.extract_names_regex(transcript, speaker_ids)

        # 找出正则未覆盖的说话人
        sid_set = {str(s) for s in speaker_ids}
        missing = sid_set - set(regex_result.keys())

        if not missing:
            logger.info("所有说话人均已通过正则识别，无需 LLM 兜底")
            return regex_result

        # 第二步：LLM 兜底
        if ai_service is None:
            logger.info(
                f"有 {len(missing)} 个说话人未识别，但未提供 ai_service，跳过 LLM 兜底"
            )
            return regex_result

        logger.info(
            f"对 {len(missing)} 个未识别说话人启用 LLM 兜底: {missing}"
        )
        try:
            llm_result = ai_service.extract_speaker_names(
                transcript, list(missing)
            )
            if llm_result and isinstance(llm_result, dict):
                # 合并：LLM 结果仅补充正则未覆盖的部分
                for sid, name in llm_result.items():
                    sid_str = str(sid)
                    if sid_str in missing and name:
                        regex_result[sid_str] = name
                        logger.info(
                            f"Speaker {sid_str}: LLM 识别到姓名 -> {name}"
                        )
            else:
                logger.warning("LLM 返回结果无效或为空")
        except Exception as e:
            logger.error(f"LLM 兜底提取姓名失败: {e}", exc_info=True)

        logger.info(
            f"最终提取完成: {len(regex_result)}/{len(sid_set)} 个说话人已识别"
        )
        return regex_result

    # ──────────────────────────────────────────────────────────
    #  内部方法
    # ──────────────────────────────────────────────────────────

    def _parse_transcript(self, transcript: str, sid_set: set) -> dict:
        """
        解析转写文本，按说话人 ID 分组返回各行内容。

        Returns
        -------
        dict
            {speaker_id: [text_line_1, text_line_2, ...]}
        """
        segments = defaultdict(list)
        for raw_line in transcript.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = self._PAT_LINE.match(line)
            if m:
                sid = m.group("sid")
                if sid in sid_set:
                    segments[sid].append(m.group("text"))
            else:
                # 非标准行（如无时间戳的纯文本），尝试按上下文归入前一个说话人
                # 这里简单跳过，避免误归
                pass
        return dict(segments)

    def _extract_name_for_lines(self, lines: list) -> str | None:
        """
        对单个说话人的所有文本行进行姓名提取。
        统计所有候选姓名的出现频次，返回最高频的那个。

        Parameters
        ----------
        lines : list[str]
            该说话人的所有文本行（已去除时间戳和 Speaker 前缀）

        Returns
        -------
        str or None
            最高频姓名，或 None（未匹配）
        """
        # name -> 出现次数
        name_freq = defaultdict(int)

        for text in lines:
            candidates = self._find_all_candidates(text)
            # 同一行内同一姓名只计一次（去重），避免重复计数
            for name in set(candidates):
                name_freq[name] += 1

        if not name_freq:
            return None

        # 按频次降序排列，取最高频；频次相同时取较长的姓名
        # （更长的姓名通常更完整，如 "腾飞部长" 优于 "腾飞"）
        best = max(
            name_freq.keys(),
            key=lambda n: (name_freq[n], len(n)),
        )
        logger.debug(f"候选姓名频次: {dict(name_freq)}, 最佳: {best}")
        return best

    def _find_all_candidates(self, text: str) -> list:
        """
        从单行文本中提取所有候选姓名。

        Returns
        -------
        list[str]
            候选姓名列表（可能包含重复）
        """
        candidates = []

        # ── 自报姓名 ──
        for pat in (self._PAT_XING, self._PAT_SHI_JIAO):
            for m in pat.finditer(text):
                name = m.group("name").strip()
                if self._is_valid_name(name):
                    candidates.append(name)

        # ── 称呼类（双模式：严格 + 宽松）──
        seen_spans = set()  # 避免两个模式对同一文本段重复匹配

        for pat, title_group in (
            (self._PAT_TITLE_STRICT, "title_a"),
            (self._PAT_TITLE_OPEN, "title_b"),
        ):
            for m in pat.finditer(text):
                # 跳过已被严格模式匹配覆盖的文本段
                span = m.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                raw_name = m.group("name").strip()
                title = m.group(title_group).strip()

                # 对宽松模式的匹配，额外校验首字是否为已知姓氏
                # 防止贪婪量词吞入前面的无关字（如 "得腾飞部长" → "腾飞部长"）
                if pat is self._PAT_TITLE_OPEN:
                    if not self._starts_with_surname(raw_name):
                        continue

                full_match = raw_name + title  # 例如 "张工"、"腾飞部长"

                # 优先添加"姓名+称呼"完整形式（如 "张工"、"腾飞部长"）
                # 即使 raw_name 只有 1 个字（单姓），full_match 也可能通过校验
                if self._is_valid_name(full_match):
                    candidates.append(full_match)

                # 同时尝试提取纯姓名部分（不带称呼后缀）
                # 仅在纯姓名 >= 2 字且通过校验时添加，例如 "蒋博" 从 "蒋博老师" 中提取
                if len(raw_name) >= 2 and self._is_valid_name(raw_name):
                    candidates.append(raw_name)

        return candidates

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """
        校验候选字符串是否像一个合法的中文姓名。
        基本规则：2-4 个汉字，排除明显的非姓名词汇。
        """
        if not name:
            return False

        # 必须全是汉字
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,5}", name):
            return False

        # 排除常见的非姓名高频词（可根据实际使用持续补充）
        _BLACKLIST = {
            "大家", "各位", "我们", "他们", "你们", "自己",
            "今天", "明天", "后天", "昨天", "每天",
            "这个", "那个", "什么", "怎么", "为什么",
            "一个", "两个", "几个", "每个",
            "可以", "可能", "应该", "必须",
            "谢谢", "感谢", "欢迎", "辛苦",
            "不是", "没有", "好的", "对的",
            "老师", "部长", "经理", "主任", "博士",  # 单独出现时不算姓名
            "施工", "工资", "工作", "工程", "工具",  # 常见词恰好含姓+称呼字
        }
        if name in _BLACKLIST:
            return False

        return True

    @classmethod
    def _starts_with_surname(cls, text: str) -> bool:
        """检查字符串是否以已知姓氏开头"""
        if not text:
            return False
        return bool(cls._PAT_STARTS_WITH_SURNAME.match(text))
