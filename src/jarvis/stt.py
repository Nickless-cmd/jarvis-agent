import os

STT_ENABLED = os.getenv("STT", "false").lower() == "true"
_MODEL = None


def _load_dependencies():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    import whisper

    model_name = os.getenv("WHISPER_MODEL", "base")
    _MODEL = whisper.load_model(model_name)
    return _MODEL


def record_audio(duration=5, fs=16000):
    if not STT_ENABLED:
        raise RuntimeError("STT er deaktiveret")
    import numpy as np
    import sounddevice as sd

    print("🎙️ Optager...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    return np.squeeze(recording)


def transcribe(audio):
    if not STT_ENABLED:
        raise RuntimeError("STT er deaktiveret")
    import scipy.io.wavfile as wav

    model = _load_dependencies()
    wav.write("speech.wav", 16000, audio)
    result = model.transcribe("speech.wav")
    return result["text"]
