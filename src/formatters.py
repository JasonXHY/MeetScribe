import json
import csv
import io
from datetime import timedelta


class TranscriptFormatter:
    """转写结果格式化器"""

    @staticmethod
    def format_json(segments, speakers=None, metadata=None):
        """JSON 格式输出"""
        data = {
            "metadata": metadata or {},
            "segments": segments,
            "speakers": speakers or [],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def format_srt(segments, speakers=None):
        """SRT 字幕格式"""
        lines = []
        for i, seg in enumerate(segments, 1):
            start = TranscriptFormatter._ms_to_srt_time(seg["start"])
            end = TranscriptFormatter._ms_to_srt_time(seg["end"])
            speaker = ""
            if speakers and "speaker" in seg:
                spk_id = seg["speaker"]
                if spk_id < len(speakers):
                    speaker = f"[{speakers[spk_id]}] "

            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(f"{speaker}{seg['text']}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_txt(segments, speakers=None):
        """纯文本格式"""
        lines = []
        for seg in segments:
            speaker = ""
            if speakers and "speaker" in seg:
                spk_id = seg["speaker"]
                if spk_id < len(speakers):
                    speaker = f"[{speakers[spk_id]}] "

            lines.append(f"{speaker}{seg['text']}")

        return "\n".join(lines)

    @staticmethod
    def format_md(segments, speakers=None):
        """Markdown 格式"""
        lines = ["# 转写结果\n"]

        current_speaker = None
        for seg in segments:
            spk_id = seg.get("speaker", -1)

            if speakers and spk_id != current_speaker:
                if spk_id < len(speakers):
                    lines.append(f"\n## {speakers[spk_id]}\n")
                current_speaker = spk_id

            lines.append(seg["text"])

        return "\n".join(lines)

    @staticmethod
    def format_csv(segments, speakers=None):
        """CSV 格式"""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["序号", "开始时间", "结束时间", "说话人", "内容"])

        for i, seg in enumerate(segments, 1):
            start = TranscriptFormatter._ms_to_time_str(seg["start"])
            end = TranscriptFormatter._ms_to_time_str(seg["end"])
            speaker = ""
            if speakers and "speaker" in seg:
                spk_id = seg["speaker"]
                if spk_id < len(speakers):
                    speaker = speakers[spk_id]

            writer.writerow([i, start, end, speaker, seg["text"]])

        return output.getvalue()

    @staticmethod
    def format_vtt(segments, speakers=None):
        """WebVTT 格式"""
        lines = ["WEBVTT\n"]

        for i, seg in enumerate(segments, 1):
            start = TranscriptFormatter._ms_to_vtt_time(seg["start"])
            end = TranscriptFormatter._ms_to_vtt_time(seg["end"])
            speaker = ""
            if speakers and "speaker" in seg:
                spk_id = seg["speaker"]
                if spk_id < len(speakers):
                    speaker = f"[{speakers[spk_id]}] "

            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(f"{speaker}{seg['text']}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _ms_to_srt_time(ms):
        """毫秒转 SRT 时间格式"""
        td = timedelta(milliseconds=ms)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        seconds = int(td.total_seconds() % 60)
        millis = int(td.total_seconds() * 1000 % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @staticmethod
    def _ms_to_vtt_time(ms):
        """毫秒转 WebVTT 时间格式"""
        td = timedelta(milliseconds=ms)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        seconds = int(td.total_seconds() % 60)
        millis = int(td.total_seconds() * 1000 % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"

    @staticmethod
    def _ms_to_time_str(ms):
        """毫秒转时间字符串"""
        td = timedelta(milliseconds=ms)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        seconds = int(td.total_seconds() % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
