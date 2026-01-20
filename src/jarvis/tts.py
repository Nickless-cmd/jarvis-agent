import hashlib
import os
import subprocess
import uuid
from gtts import gTTS

CACHE = "tts_cache"
os.makedirs(CACHE, exist_ok=True)

def speak(text, lang=None):
    if not text or not text.strip():
        return None
    engine = os.getenv("TTS_ENGINE", "gtts").lower()
    if not lang:
        lang = os.getenv("TTS_LANG", "da")
    if engine == "piper":
        voice = os.getenv("PIPER_VOICE")
        if voice:
            digest = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()[:12]
            fname = f"{CACHE}/{digest}.wav"
            try:
                subprocess.run(
                    ["piper", "-m", voice, "-f", fname],
                    input=text,
                    text=True,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return fname
            except Exception:
                pass
    fname = f"{CACHE}/{uuid.uuid4()}.mp3"
    tts = gTTS(text=text, lang=lang)
    tts.save(fname)
    return fname
