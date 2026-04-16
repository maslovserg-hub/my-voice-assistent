"""
Тест GigaAM v3: запись 5 секунд с микрофона → распознавание → вывод текста.
Запуск: .venv/Scripts/python test_gigaam.py
"""
import sys
import os
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf

import gigaam

SAMPLE_RATE = 16000
DURATION = 5  # секунд
CACHE_DIR = "C:/gigaam_cache"  # ASCII-путь, обход Кириллики в имени пользователя

print("Загрузка модели GigaAM v3...")
model = gigaam.load_model("v3_e2e_ctc", device="cpu", download_root=CACHE_DIR)
print("Модель загружена.")

print(f"\nЗапись {DURATION} секунд... Говорите!")
audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32"
)
sd.wait()
print("Запись завершена. Распознаю...")

audio_mono = audio.squeeze()

with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="C:/gigaam_cache") as f:
    tmp_path = f.name

try:
    sf.write(tmp_path, audio_mono, SAMPLE_RATE, subtype="PCM_16")
    result = model.transcribe(tmp_path)
    print(f"\nРезультат: {result.text}")
finally:
    os.unlink(tmp_path)
