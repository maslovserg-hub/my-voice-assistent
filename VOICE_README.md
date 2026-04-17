# VoiceType — утилита голосового ввода для Windows

Нажал Right Ctrl → говоришь → текст вставляется порциями в любое активное поле → нажал снова → стоп.

## Возможности

- Глобальный хоткей Right Ctrl — начать/остановить запись
- Esc — отменить запись (текст не вставляется)
- Распознавание через GigaAM v3 — локально, без интернета, с пунктуацией
- Вставка текста напрямую через pynput (без буфера обмена)
- Постепенная вставка текста по мере речи (после 1.5с паузы)
- Оверлей: 5 анимированных полосок, всегда поверх окон
- Трей-иконка: автозагрузка с Windows, закрыть приложение
- Один экземпляр (Windows mutex)
- Мастер первого запуска: выбрать папку с моделью или скачать автоматически

## Требования

- Windows 10+
- ~650 МБ места для модели GigaAM v3 (хранится в `C:/gigaam_cache`)
- ~1.5 ГБ RAM в работе
- Микрофон

## Быстрый старт (для разработки)

```bash
voicetype.bat
```

Или напрямую:

```bash
.venv/Scripts/python main.py
```

## Тест микрофона и модели

```bash
test_mic.bat
```

## Сборка .exe

```bash
.venv/Scripts/pyinstaller \
  --onefile --noconsole --name VoiceType \
  --additional-hooks-dir=. \
  --hidden-import=pystray._win32 \
  --collect-all=gigaam \
  --collect-all=torch \
  --collect-all=torchaudio \
  --collect-all=onnxruntime \
  --collect-all=hydra \
  --collect-all=omegaconf \
  --hidden-import=sounddevice \
  --hidden-import=soundfile \
  --hidden-import=sentencepiece \
  --hidden-import=hydra._internal.utils \
  --hidden-import=hydra._internal.instantiate._internal.utils \
  --exclude-module=torch.testing \
  --exclude-module=torch.distributed \
  --exclude-module=torch.ao \
  --exclude-module=torch.onnx \
  --exclude-module=torch.fx \
  main.py
```

Результат: `dist/VoiceType.exe` (~170 МБ).  
`hook-torch.py` исключает C++ заголовки torch для уменьшения размера.

## Распространение

Скопировать на целевую машину:
- `dist/VoiceType.exe`
- Папку `C:/gigaam_cache` (модель, ~650 МБ) — **или** скачается автоматически при первом запуске

## Стек

| Компонент | Назначение |
|-----------|-----------|
| GigaAM v3 `v3_e2e_ctc` | Распознавание речи с пунктуацией |
| sounddevice | Захват микрофона (постоянный поток) |
| pynput | Глобальный хоткей + симуляция клавиатуры |
| tkinter | Оверлей always-on-top |
| pystray | Трей-иконка |
| PyInstaller | Сборка в .exe |
| winreg | Автозагрузка через HKCU реестр |
