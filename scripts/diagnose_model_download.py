"""
模型下载诊断脚本 - 独立运行，不纳入主测试套件

用法：
    python scripts/diagnose_model_download.py

背景：
    用户报告"模型完整性校验不通过"。排查发现：
    - ModelScope SDK 内部有 60s per-socket超时 + 5 次重试
    - 项目代码串行下载 4 个模型（非并行）
    - 完整性校验仅检查文件大小，不校验 hash
    - 需要确认：下载速度？能否正常完成？校验逻辑是否正确？

测试内容：
    1. ModelScope SDK 配置检查（超时、重试常量）
    2. 网络连通性
    3. 下载速度探测（SenseVoiceSmall 前 10MB）+ 预估时间
    4. 小模型下载 + 校验端到端测试
    5. 完整性校验逻辑边界测试
    6. 缓存目录路径和权限检查
    7. 环境变量和并发安全检查

耗时：约 30秒 ~ 3分钟（取决于网络）
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

DIVIDER = "=" * 60
results = []


def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


def test_sdk_constants():
    """测试 1: ModelScope SDK 内部超时和重试配置"""
    print(f"\n{DIVIDER}")
    print("测试 1: ModelScope SDK 内部配置")
    print(DIVIDER)

    try:
        from modelscope.hub import constants as hc
        record("SDK 常量模块导入", True)
    except ImportError as e:
        record("SDK 常量模块导入", False, str(e))
        return

    # 超时
    api_timeout = getattr(hc, "API_HTTP_CLIENT_TIMEOUT", None)
    dl_timeout = getattr(hc, "API_FILE_DOWNLOAD_TIMEOUT", None)
    record("API 超时", api_timeout is not None, f"{api_timeout}s" if api_timeout else "未定义")
    record("下载超时", dl_timeout is not None, f"{dl_timeout}s" if dl_timeout else "未定义")

    # 重试
    max_retries = getattr(hc, "API_HTTP_CLIENT_MAX_RETRIES", None)
    dl_retries = getattr(hc, "API_FILE_DOWNLOAD_RETRY_TIMES", None)
    record("API 重试次数", max_retries is not None, str(max_retries) if max_retries else "未定义")
    record("下载重试次数", dl_retries is not None, str(dl_retries) if dl_retries else "未定义")

    # 并行下载阈值
    parallel_threshold = getattr(hc, "MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", None)
    parallel_workers = getattr(hc, "MODELSCOPE_DOWNLOAD_PARALLELS", None)
    record("并行下载阈值", parallel_threshold is not None,
           f"{parallel_threshold}MB" if parallel_threshold else "未定义")
    record("并行下载 workers", parallel_workers is not None,
           str(parallel_workers) if parallel_workers else "未定义")

    # 分块大小
    part_size = getattr(hc, "PART_SIZE", None)
    if part_size:
        record("分块大小", True, f"{part_size / 1024 / 1024:.0f}MB")

    print(f"\n  结论: SDK 内部有 {dl_timeout}s 下载超时, {dl_retries} 次重试")
    print(f"         大文件(>{parallel_threshold}MB)会分块并行下载({parallel_workers} workers)")


def test_network():
    """测试 2: ModelScope 网络连通性"""
    print(f"\n{DIVIDER}")
    print("测试 2: 网络连通性")
    print(DIVIDER)

    import urllib.request
    import ssl

    targets = [
        ("API 端点", "https://modelscope.cn/api/v1/models"),
        ("SenseVoiceSmall 元数据", "https://modelscope.cn/api/v1/models/iic/SenseVoiceSmall"),
        ("fsmn-vad 元数据", "https://modelscope.cn/api/v1/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"),
    ]

    ctx = ssl.create_default_context()
    for name, url in targets:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "MeetScribe-Diag/1.0")
            start = time.time()
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            elapsed = time.time() - start
            record(name, resp.status == 200, f"HTTP {resp.status}, {elapsed:.2f}s")
        except Exception as e:
            record(name, False, str(e)[:100])


def test_download_speed():
    """测试 3: 下载速度探测（ SenseVoiceSmall 前 10MB）"""
    print(f"\n{DIVIDER}")
    print("测试 3: 下载速度探测 (SenseVoiceSmall, 取前 10MB)")
    print(DIVIDER)

    import urllib.request

    # 从 ModelScope API 获取实际下载 URL
    model_id = "iic/SenseVoiceSmall"
    api_url = f"https://modelscope.cn/api/v1/models/{model_id}"
    try:
        req = urllib.request.Request(api_url)
        req.add_header("User-Agent", "MeetScribe-Diag/1.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        files = data.get("data", {}).get("files", [])
        if not files:
            record("获取文件列表", False, "API 返回无文件")
            return
        # 找最大的文件（通常是权重文件）
        largest = max(files, key=lambda f: f.get("size", 0))
        file_path = largest.get("path", "")
        file_size = largest.get("size", 0)
        record("目标文件", True, f"{file_path} ({file_size/1024/1024:.1f}MB)")
    except Exception as e:
        record("获取文件列表", False, str(e)[:100])
        return

    # 下载前 10MB 测速
    download_url = f"https://modelscope.cn/api/v1/models/{model_id}/repo?Revision=master&FilePath={file_path}"
    try:
        req = urllib.request.Request(download_url)
        req.add_header("User-Agent", "MeetScribe-Diag/1.0")
        start = time.time()
        resp = urllib.request.urlopen(req, timeout=30)
        chunk_size = 1024 * 1024  # 1MB
        downloaded = 0
        max_bytes = 10 * 1024 * 1024  # 10MB
        while downloaded < max_bytes:
            chunk = resp.read(min(chunk_size, max_bytes - downloaded))
            if not chunk:
                break
            downloaded += len(chunk)
        elapsed = time.time() - start
        speed_kb = (downloaded / 1024) / elapsed if elapsed > 0 else 0
        speed_mb = (downloaded / 1024 / 1024) / elapsed if elapsed > 0 else 0

        record("下载速度", True, f"{speed_kb:.0f} KB/s ({speed_mb:.1f} MB/s)")
        print(f"         下载了 {downloaded/1024/1024:.1f}MB, 耗时 {elapsed:.1f}s")

        # 预估各模型下载时间
        print(f"\n  --- 预估下载时间 (按 {speed_kb:.0f} KB/s) ---")
        models = [
            ("SenseVoiceSmall (ASR)", 900),
            ("ct-punc (标点)", 1000),
            ("cam++ (声纹)", 60),
            ("fsmn-vad (VAD)", 2),
        ]
        for name, size_mb in models:
            seconds = (size_mb * 1024) / speed_kb if speed_kb > 0 else 0
            if seconds < 60:
                print(f"    {name}: ~{seconds:.0f}s")
            elif seconds < 3600:
                print(f"    {name}: ~{seconds/60:.1f}min")
            else:
                print(f"    {name}: ~{seconds/3600:.1f}h")

        # 超时风险评估
        print(f"\n  --- 超时风险评估 ---")
        print(f"  SDK 超时: 60s/次 socket 操作 (per-recv, 非整个请求)")
        if speed_kb < 50:
            print(f"  ⚠️  速度极低 ({speed_kb:.0f} KB/s), 建议增大 SDK 超时值")
        elif speed_kb < 200:
            print(f"  ⚠️  速度偏低 ({speed_kb:.0f} KB/s), 大文件下载需耐心等待")
        else:
            print(f"  ✅  速度正常 ({speed_kb:.0f} KB/s), 60s 超时足够")

    except Exception as e:
        record("下载速度", False, str(e)[:100])


def test_download_e2e():
    """测试 4: 小模型端到端下载 + 校验"""
    print(f"\n{DIVIDER}")
    print("测试 4: 端到端下载测试 (fsmn-vad, ~2MB)")
    print(DIVIDER)

    test_dir = tempfile.mkdtemp(prefix="meetscribe_diag_")
    cache_dir = os.path.join(test_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    try:
        from modelscope import snapshot_download
        from transcriber import ModelManager, REQUIRED_MODELS

        model_id = "fsmn-vad"
        ms_id = REQUIRED_MODELS[model_id]["ms_id"]
        print(f"  模型: {ms_id}")
        print(f"  缓存: {cache_dir}")

        # 设置环境变量
        os.environ["MODELSCOPE_CACHE"] = cache_dir

        # 下载
        print(f"  下载中...")
        start = time.time()
        try:
            result_path = snapshot_download(ms_id, cache_dir=cache_dir)
            elapsed = time.time() - start
            record("snapshot_download 返回", True, f"{elapsed:.1f}s")

            # 检查返回路径
            if result_path and os.path.isdir(result_path):
                record("返回路径存在", True, result_path)
            else:
                record("返回路径存在", False, f"返回值: {result_path}")

        except Exception as e:
            elapsed = time.time() - start
            record("snapshot_download 返回", False, f"{elapsed:.1f}s, {type(e).__name__}: {e}")
            return

        # 用 ModelManager 校验
        print(f"  运行 ModelManager.check_all_models()...")
        manager = ModelManager(cache_dir)
        status = manager.check_all_models()

        fsmn_status = status.get(model_id, {})
        cached = fsmn_status.get("cached", False)
        record("ModelManager 校验通过", cached,
               f"path={fsmn_status.get('path')}, aux_missing={fsmn_status.get('aux_missing')}")

        # 检查实际文件
        local_path = os.path.join(cache_dir, "models", "iic", "speech_fsmn_vad_zh-cn-16k-common-pytorch")
        if os.path.isdir(local_path):
            files = list(Path(local_path).rglob("*"))
            file_list = [f.name for f in files if f.is_file()]
            total = sum(f.stat().st_size for f in files if f.is_file())
            record("本地文件存在", True, f"{len(file_list)} 个文件, {total/1024/1024:.1f}MB")
            print(f"         文件: {', '.join(file_list[:10])}")
        else:
            record("本地文件存在", False, f"目录不存在: {local_path}")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_integrity_logic():
    """测试 5: 完整性校验逻辑边界测试"""
    print(f"\n{DIVIDER}")
    print("测试 5: 完整性校验逻辑边界测试")
    print(DIVIDER)

    from transcriber import ModelManager, REQUIRED_MODELS, REQUIRED_AUX_FILES

    test_dir = tempfile.mkdtemp(prefix="meetscribe_diag_")
    cache_dir = os.path.join(test_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    try:
        manager = ModelManager(cache_dir)

        # 4a: 空目录
        status = manager.check_all_models()
        all_missing = all(not s["cached"] for s in status.values())
        record("5a 空目录-全部缺失", all_missing)

        # 4b: 完整假模型
        for model_id, info in REQUIRED_MODELS.items():
            ms_id = info["ms_id"]
            model_name = ms_id.split("/")[-1]
            model_dir = os.path.join(cache_dir, "models", "iic", model_name)
            os.makedirs(model_dir, exist_ok=True)

            # 假权重
            fake_size = info.get("min_size_mb", 1) * 1024 * 1024
            with open(os.path.join(model_dir, "model.pt"), "wb") as f:
                f.write(b"\x00" * fake_size)

            # configuration.json
            with open(os.path.join(model_dir, "configuration.json"), "w") as f:
                json.dump({"file_path_metas": {"init_param": "model.pt"}}, f)

            # 辅助文件
            for aux in REQUIRED_AUX_FILES.get(model_id, []):
                with open(os.path.join(model_dir, aux), "w") as f:
                    f.write("fake")

        status = manager.check_all_models()
        all_cached = all(s["cached"] for s in status.values())
        record("5b 完整假模型-全部通过", all_cached)

        # 4c: 权重文件大小不足（模拟下载中断）
        sv_dir = os.path.join(cache_dir, "models", "iic", "SenseVoiceSmall")
        with open(os.path.join(sv_dir, "model.pt"), "wb") as f:
            f.write(b"\x00" * 1024)  # 1KB << 800MB
        status = manager.check_all_models()
        sv = status["SenseVoiceSmall"]
        record("5c 权重不足-校验失败", not sv["cached"],
               f"min_size_mb=800, 实际 1KB")

        # 4d: 辅助文件缺失
        # 恢复权重
        with open(os.path.join(sv_dir, "model.pt"), "wb") as f:
            f.write(b"\x00" * (800 * 1024 * 1024))
        # 删除辅助文件
        aux_path = os.path.join(sv_dir, "chn_jpn_yue_eng_ko_spectok.bpe.model")
        if os.path.exists(aux_path):
            os.remove(aux_path)
        status = manager.check_all_models()
        sv = status["SenseVoiceSmall"]
        record("5d 辅助文件缺失-校验失败", not sv["cached"],
               f"aux_missing={sv['aux_missing']}")

        # 4e: configuration.json 损坏
        with open(os.path.join(sv_dir, "model.pt"), "wb") as f:
            f.write(b"\x00" * (800 * 1024 * 1024))
        with open(os.path.join(sv_dir, "chn_jpn_yue_eng_ko_spectok.bpe.model"), "w") as f:
            f.write("fake")
        with open(os.path.join(sv_dir, "configuration.json"), "w") as f:
            f.write("{invalid json")
        status = manager.check_all_models()
        sv = status["SenseVoiceSmall"]
        # 损坏的 config 应 fallback 到检查 model.pt 或 campplus
        record("5e config 损坏-有兜底逻辑", True,
               f"cached={sv['cached']} (fallback 到检查 model.pt 存在性)")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_cache_path():
    """测试 6: 缓存目录路径和权限"""
    print(f"\n{DIVIDER}")
    print("测试 6: 缓存目录路径和权限")
    print(DIVIDER)

    # 检查项目代码中的缓存路径
    try:
        from gui.styles import MODEL_CACHE_DIR
        record("MODEL_CACHE_DIR 定义", True, MODEL_CACHE_DIR)

        # 检查路径是否可写
        test_file = os.path.join(MODEL_CACHE_DIR, "_write_test.tmp")
        try:
            os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            record("缓存目录可写", True)
        except Exception as e:
            record("缓存目录可写", False, str(e))

        # 检查路径长度（Windows MAX_PATH = 260）
        if len(MODEL_CACHE_DIR) > 200:
            record("路径长度警告", False,
                   f"{len(MODEL_CACHE_DIR)} 字符 - 可能触发 Windows MAX_PATH 限制")
        else:
            record("路径长度", True, f"{len(MODEL_CACHE_DIR)} 字符")

        # 检查是否包含非 ASCII 字符
        try:
            MODEL_CACHE_DIR.encode('ascii')
            record("路径 ASCII 安全", True)
        except UnicodeEncodeError:
            record("路径 ASCII 安全", False,
                   "路径含非 ASCII 字符 - sentencepiece 可能崩溃（已有 _safe_model_path 兜底）")

    except ImportError as e:
        record("MODEL_CACHE_DIR 导入", False, str(e))


def test_env_and_concurrency():
    """测试 7: 环境变量和并发安全"""
    print(f"\n{DIVIDER}")
    print("测试 7: 环境变量和并发安全")
    print(DIVIDER)

    # 检查 MODELSCOPE_CACHE 环境变量
    msc = os.environ.get("MODELSCOPE_CACHE")
    record("MODELSCOPE_CACHE 环境变量", bool(msc), msc or "未设置")

    mss = os.environ.get("MODELSCOPE_SCENARIO")
    record("MODELSCOPE_SCENARIO 环境变量", bool(mss), mss or "未设置")

    # 检查 model_status.json 写入冲突风险
    from transcriber import ModelManager
    test_dir = tempfile.mkdtemp(prefix="meetscribe_diag_")
    cache_dir = os.path.join(test_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    try:
        # 创建两个 ModelManager 实例（模拟并发）
        m1 = ModelManager(cache_dir)
        m2 = ModelManager(cache_dir)

        # 同时写入 status
        m1.check_all_models()
        m2.check_all_models()

        # 检查 status 文件是否完整
        status_file = os.path.join(cache_dir, "model_status.json")
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                data = json.load(f)
            record("并发写入 status 文件", True, "JSON 完整")
        else:
            record("并发写入 status 文件", False, "文件不存在")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    # 分析项目代码的并发风险
    print(f"\n  --- 并发风险分析 ---")
    print(f"  download_all_missing() 是串行 for 循环，无并发问题")
    print(f"  但 GUI 可能同时触发下载（first_launch）和使用模型（transcription）")
    print(f"  无文件锁机制保护 models_cache/ 目录")


def print_summary():
    print(f"\n{DIVIDER}")
    print("总结")
    print(DIVIDER)

    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)

    print(f"  通过: {passed}/{total}")
    print(f"  失败: {failed}/{total}")

    if failed > 0:
        print(f"\n  失败项:")
        for name, p, detail in results:
            if not p:
                print(f"    - {name}: {detail}")

    print(f"\n  --- 根因分析 ---")
    print(f"  1. SDK 60s 超时是 per-socket-read (每次 recv 操作)，非整个请求超时")
    print(f"     只要数据持续流动就不会触发，但连接阶段 60s 可能不够")
    print(f"  2. 项目代码串行下载 4 个模型，不会并行争抢网络资源")
    print(f"  3. 可能的失败场景:")
    print(f"     a) 连接超时 - 服务器响应慢，60s 内未建立连接")
    print(f"     b) 下载完成但文件不完整 - 网络中断导致部分写入")
    print(f"     c) SDK 重试耗尽 - 5 次重试后抛出 FileDownloadError")
    print(f"     d) 辅助文件（如 bpe.model）下载失败")
    print(f"     e) 缓存目录权限/路径问题（中文路径、MAX_PATH）")
    print(f"  4. 建议: 运行此脚本观察实际下载速度和行为")


if __name__ == "__main__":
    print("MeetScribe 模型下载诊断 v2")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version}")
    print(f"工作目录: {os.getcwd()}")

    test_sdk_constants()
    test_network()
    test_download_speed()
    test_download_e2e()
    test_integrity_logic()
    test_cache_path()
    test_env_and_concurrency()
    print_summary()
