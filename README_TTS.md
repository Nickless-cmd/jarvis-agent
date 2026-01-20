# Lokal TTS (Piper)

Valgfri lokal TTS kan aktiveres via Piper. Hvis Piper ikke er tilgængelig, bruges gTTS som fallback.

## Miljøvariabler
- `TTS_ENGINE`: `piper` eller `gtts` (default: `gtts`)
- `PIPER_VOICE`: sti til `.onnx`-modellen (påkrævet for Piper)
- `TTS_LANG`: sprog til gTTS (default: `da`)

## Installation (Ubuntu 24.04)
1) Installer Piper (én af følgende afhængigt af hvad der virker hos dig):
   - `pip install piper-tts`
   - eller brug en .whl fra Piper-projektet hvis pip fejler

2) Hent en dansk stemme (eksempel):
   - Download en dansk `.onnx`-model fra Piper voice repos
   - Sæt `PIPER_VOICE=/path/to/da_DK-voice.onnx`

## Eksempel
```bash
export TTS_ENGINE=piper
export PIPER_VOICE=/home/bs/voices/da_DK-voice.onnx
```
