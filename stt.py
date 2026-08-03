"""音声認識(faster-whisper)。ノイズ対策としてVADで無音・雑音区間を除去する。

GPUはLLMが使うためCPUで動かす。large-v3-turbo は large級の精度で数倍速い。
モデルは初回呼び出し時に自動ダウンロードされる(約1.5GB)。
"""
import os
import tempfile

MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3-turbo")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"[stt] Whisperを読み込み中: {MODEL_NAME} ({DEVICE}/{COMPUTE})")
        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE)
        print("[stt] 読み込み完了")
    return _model


def transcribe(data: bytes, filename: str = "audio.webm") -> str:
    """音声データを文字起こしする。"""
    suffix = os.path.splitext(filename)[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        segments, info = _get_model().transcribe(
            path,
            language="ja",
            beam_size=5,                 # 精度重視
            vad_filter=True,             # 無音・雑音区間を除去(ノイズ対策)
            vad_parameters={"min_silence_duration_ms": 400},
            condition_on_previous_text=False,  # 直前の誤認識に引きずられないように
        )
        text = "".join(s.text for s in segments).strip()
        print(f"[stt] 認識({info.duration:.1f}秒): {text[:60]}")
        return text
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
