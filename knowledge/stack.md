# Стек и архитектура

## Текущий стек

- **Frontend:** Чистый HTML5 + CSS3 + Vanilla JS
- **Файловая структура:** Всё в одном `index.html`
- **Никаких:** Bootstrap, jQuery, React, Vue и других внешних библиотек
- **Голосовой ввод:** Python (voice_input.py) + Web Speech API (браузер)

## Дизайн-система

- Фон: тёмный (`#1a1a2e` или похожий)
- Текст: светлый (`#eee` / белый)
- Акцент: оранжевый
- Адаптивность: от 320px, flexbox/grid, clamp() для шрифтов

## Голосовой ввод (voice_input.py)

Запускается через `run_voice_input.bat`.
Использует Python speech_recognition библиотеку.
Передаёт текст в браузер через WebSocket или HTTP.

## Планируемый бекенд

- Speech Recognition API (Google/Amazon)
- Text-to-Speech API
- БД: пользователи + история команд + интеграции
