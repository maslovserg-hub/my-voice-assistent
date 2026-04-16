# VoiceType — утилита голосового ввода для Windows

Нажал хоткей → говоришь → текст вставляется в любое поле → нажал снова → стоп.

## Возможности

- Глобальный хоткей (Right Ctrl по умолчанию, настраивается)
- Распознавание через GigaAM v3 — локально, без интернета
- Вставка текста напрямую, без буфера обмена
- Оверлей на экране: показывает статус и распознанный текст
- Автозагрузка с Windows (опционально)
- Сборка в .exe — Python не нужен

## Требования

- Windows 10+
- ~2 ГБ места (модель GigaAM v3)
- Микрофон

## Быстрый старт (для разработки)

```bash
pip install -r requirements.txt
python main.py
```

## Сборка .exe

```bash
pyinstaller --onefile main.py
```

## Конфиг

`config.json` в папке с программой:

```json
{
  "hotkey": "right_ctrl",
  "chunk_duration_sec": 3,
  "autostart": false,
  "overlay_position": "bottom-right"
}
```

## Стек

- GigaAM v3 (`salute-developers/GigaAM`) — распознавание речи
- sounddevice — захват микрофона
- pynput — глобальный хоткей + симуляция клавиатуры
- customtkinter — оверлей
- PyInstaller — сборка
