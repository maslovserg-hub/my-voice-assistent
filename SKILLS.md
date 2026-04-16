# Скилы, хуки и агенты проекта

## О системе

Мы развернули **Continuous Claude v3** — надстройку над Claude Code, которая превращает стандартный AI-ассистент в полноценную систему с памятью, специализированными агентами и автоматизацией рабочего процесса.

### Что это такое

По умолчанию Claude Code — это умный, но «одноразовый» инструмент: каждая сессия начинается с чистого листа, Claude не помнит что делал вчера, не знает какие файлы сейчас редактирует другой терминал, не сохраняет принятые решения.

Continuous Claude v3 устраняет эти ограничения. Система добавляет:
- **Долгосрочную память** через базу данных PostgreSQL с векторными эмбеддингами
- **114 специализированных команд** для типичных задач разработки
- **48 агентов** — каждый эксперт в своей области
- **50 автоматических хуков** — система реагирует на события без ручных команд

### Что появилось после установки

**Память между сессиями.**
Claude помнит что делалось в прошлых сессиях. При старте новой сессии загружается контекст проекта — что работало, что нет, какие решения были приняты. Команда `/recall` позволяет семантически искать по истории работы.

**Автоматические handoff-документы.**
Когда сессия завершается (Stop), система автоматически сохраняет итоговый документ: цель сессии, что сработало, что не сработало, ключевые решения. При следующем старте Claude читает этот документ и продолжает с того места.

**Специализированные агенты по задачам.**
Вместо одного Claude на всё — команда агентов. Нужно исправить баг → `sleuth` расследует причину, `spark` пишет фикс, `arbiter` прогоняет тесты. Каждый агент получает только нужный контекст, не засоряя общий.

**114 готовых команд.**
`/discovery-interview`, `/build`, `/fix`, `/review`, `/commit`, `/plan`, `/recall` и другие — готовые рабочие процессы, которые не нужно объяснять заново каждый раз.

**Умные хуки-автоматы.**
- Перед редактированием файла — автоматически проверяет не редактирует ли его другой терминал
- После каждого изменения TypeScript — запускает проверку типов
- При каждом запросе — проверяет есть ли релевантные воспоминания из прошлых сессий
- При поиске через Grep — перенаправляет на более точный AST-поиск

**Статусная строка.**
В интерфейсе Claude Code отображается текущий расход контекста (например `45K 22%`) — видно когда контекст заполняется и нужно начать новую сессию.

**Координация между терминалами.**
Если открыто два терминала с Claude — они видят друг друга. При попытке редактировать один файл из двух мест — предупреждение о конфликте.

### Ключевые преимущества

| До | После |
|----|-------|
| Каждая сессия с нуля | Контекст проекта загружается автоматически |
| Нужно объяснять задачу каждый раз | `/fix`, `/build`, `/review` — одна команда запускает весь процесс |
| Claude один на все задачи | 48 агентов, каждый специализирован |
| Ошибки TypeScript обнаруживаются поздно | Проверка запускается автоматически после каждого изменения |
| Не знаешь сколько осталось контекста | Статусная строка показывает % использования |
| Прошлые решения теряются | База данных хранит историю с семантическим поиском |

### Состав установленной системы

| Компонент | Количество | Где хранится |
|-----------|-----------|--------------|
| Скилы (команды) | 114 | `~/.claude/skills/` |
| Агенты | 48 | `~/.claude/agents/` |
| Хуки | 50 | `~/.claude/hooks/` |
| Правила поведения | 12 | `~/.claude/rules/` |
| Python-утилиты | 12 | `~/.claude/scripts/` |
| База данных | PostgreSQL 16 + pgvector | `localhost:5432/continuous_claude` |

---

## Структура системы

В проекте используются два уровня расширений Claude Code:

1. **Проектные скилы** — описаны в `CLAUDE.md`, специфичны для этого проекта
2. **Глобальная система Continuous-Claude-v3** — установлена в `~/.claude/`, работает во всех проектах

---

## Проектные скилы

Активируются командой `/имя-скила` в чате с Claude.

### `/discovery-interview`
Глубокое исследовательское интервью. Трансформирует размытую идею в детальную спецификацию.
- Задаёт 10–15 структурированных вопросов по 8 категориям (проблема, UX, данные, технологии, масштаб и др.)
- Предлагает исследование альтернатив при неопределённости
- На выходе создаёт файл спецификации `thoughts/shared/specs/ДАТА-название.md`
- **Когда использовать:** перед стартом новой фичи, продукта или при проверке гипотезы

### `/fullstack-developer`
Архитектура и разработка полного стека.
- Помогает проектировать структуру файлов, API, схемы данных
- Ориентирован на `index.html`, бэкенд-план и интеграционное тестирование
- **Когда использовать:** при планировании технической реализации

### `/frontend-design`
Визуальный дизайн и адаптивная вёрстка.
- Тёмный современный интерфейс, плавные анимации, мобильная адаптивность
- Создание и улучшение лендинга, интерактивных блоков
- **Когда использовать:** при работе над UI/UX

---

## Глобальная система Continuous-Claude-v3

Установлена в `~/.claude/`. Работает автоматически во всех проектах.

### Скилы (114 штук)
Вызываются командой `/имя-скила`. Примеры наиболее полезных:

| Команда | Назначение |
|---------|-----------|
| `/discovery-interview` | Исследовательское интервью → спецификация |
| `/commit` | Создать git-коммит с правильным сообщением |
| `/review` | Ревью pull request |
| `/build` | Реализация фичи по плану |
| `/fix` | Исправление бага |
| `/explore` | Изучение кодовой базы |
| `/plan` | Создание плана реализации |
| `/recall` | Поиск в памяти прошлых сессий |

Полный список: `ls ~/.claude/skills/`

### Агенты (48 штук)
Специализированные Claude-агенты для конкретных задач. Запускаются автоматически или через Agent tool.

| Агент | Назначение |
|-------|-----------|
| `kraken` | Реализация кода по TDD |
| `spark` | Быстрые правки и мелкие задачи |
| `architect` | Проектирование архитектуры |
| `scout` | Исследование кодовой базы |
| `sleuth` | Поиск причин багов |
| `oracle` | Внешние исследования (веб) |
| `arbiter` | Запуск и валидация тестов |
| `critic` | Ревью кода |

### Хуки (50 штук)
Запускаются автоматически при событиях Claude Code. Конфигурация в `~/.claude/settings.local.json`.

| Событие | Что происходит |
|---------|---------------|
| `SessionStart` | Регистрация сессии, загрузка контекста проекта |
| `UserPromptSubmit` | Активация скилов, проверка памяти, анализ влияния изменений |
| `PreToolUse:Edit` | Проверка блокировок файлов, инъекция контекста |
| `PreToolUse:Read` | Перенаправление на TLDR-анализ (экономия токенов) |
| `PreToolUse:Grep` | Умный роутинг поиска |
| `PostToolUse:Edit` | TypeScript preflight, компилятор в цикле, диагностика |
| `Stop` | Автосохранение handoff-документа сессии |
| `SessionEnd` | Очистка, сохранение итогов сессии |

---

## Установка на другом компьютере

### 1. Требования

Установить все инструменты:

```bash
# Windows (через winget)
winget install Python.Python.3.11
winget install astral-sh.uv
winget install OpenJS.NodeJS.LTS
winget install Docker.DockerDesktop
winget install Git.Git

# macOS (через brew)
brew install python@3.11 uv node git
brew install --cask docker
```

Установить Claude Code:
```bash
npm install -g @anthropic-ai/claude-code
```

### 2. Установить скилы Continuous-Claude-v3

**Способ А — через npx (если Node.js установлен):**
```bash
npx skills add parcadei/Continuous-Claude-v3
```

**Способ Б — вручную через git:**
```bash
# Клонировать репозиторий
git clone --depth=1 https://github.com/parcadei/Continuous-Claude-v3.git /tmp/cc3

# Создать директории
mkdir -p ~/.claude/skills ~/.claude/agents ~/.claude/hooks ~/.claude/rules

# Скопировать компоненты
cp -r /tmp/cc3/.claude/skills/. ~/.claude/skills/
cp -r /tmp/cc3/.claude/agents ~/.claude/agents
cp -r /tmp/cc3/.claude/hooks ~/.claude/hooks
cp -r /tmp/cc3/.claude/rules ~/.claude/rules
cp -r /tmp/cc3/.claude/scripts ~/.claude/scripts
cp -r /tmp/cc3/.claude/plugins ~/.claude/plugins
```

### 3. Добавить хуки в settings.local.json

Открыть (или создать) файл `~/.claude/settings.local.json` и добавить блок `"hooks"`:

```json
{
  "hooks": {
    "PreToolUse": [
      { "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/pre-tool-use-broadcast.mjs" }] },
      { "matcher": "Read|Edit|Write", "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/path-rules.mjs", "timeout": 5 }] },
      { "matcher": "Read",  "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/tldr-read-enforcer.mjs", "timeout": 20 }] },
      { "matcher": "Grep",  "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/smart-search-router.mjs", "timeout": 10 }] },
      { "matcher": "Task",  "hooks": [
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/tldr-context-inject.mjs", "timeout": 30 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/arch-context-inject.mjs",  "timeout": 30 }
      ]},
      { "matcher": "Edit",  "hooks": [
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/file-claims.mjs",        "timeout": 5 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/edit-context-inject.mjs","timeout": 5 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/signature-helper.mjs",   "timeout": 5 }
      ]}
    ],
    "PreCompact": [
      { "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/pre-compact-continuity.mjs" }] }
    ],
    "SessionStart": [
      { "hooks": [
          { "type": "command", "command": "bash $HOME/.claude/hooks/persist-project-dir.sh" },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/session-register.mjs", "timeout": 10 },
          { "type": "command", "command": "uv run $HOME/.claude/hooks/hook_launcher.py session-symbol-index", "timeout": 5 }
      ]},
      { "matcher": "resume|compact|clear",  "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/session-start-continuity.mjs" }] },
      { "matcher": "startup|resume", "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/session-start-tldr-cache.mjs", "timeout": 2 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/skill-activation-prompt.mjs" },
          { "type": "command", "command": "uv run $HOME/.claude/hooks/hook_launcher.py premortem-suggest", "timeout": 5 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/memory-awareness.mjs",  "timeout": 10 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/impact-refactor.mjs",   "timeout": 10 }
      ]}
    ],
    "PostToolUse": [
      { "matcher": "Edit|Write", "hooks": [
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/typescript-preflight.mjs", "timeout": 40 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/compiler-in-the-loop.mjs", "timeout": 30 },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/post-edit-notify.mjs",     "timeout": 5  },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/post-edit-diagnostics.mjs","timeout": 10 }
      ]},
      { "matcher": "Write", "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/handoff-index.mjs" }] },
      { "matcher": "Edit|MultiEdit|Write|Bash", "hooks": [{ "type": "command", "command": "uv run $HOME/.claude/hooks/hook_launcher.py post-tool-use-tracker", "timeout": 120 }] },
      { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/import-validator.mjs",    "timeout": 5 }] },
      { "matcher": "Bash",       "hooks": [{ "type": "command", "command": "node $HOME/.claude/hooks/dist/import-error-detector.mjs","timeout": 5 }] }
    ],
    "Stop": [
      { "hooks": [
          { "type": "command", "command": "uv run $HOME/.claude/hooks/hook_launcher.py auto-handoff-stop" },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/compiler-in-the-loop-stop.mjs" }
      ]}
    ],
    "SessionEnd": [
      { "hooks": [
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/session-end-cleanup.mjs" },
          { "type": "command", "command": "node $HOME/.claude/hooks/dist/session-outcome.mjs" }
      ]}
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "uv run $HOME/.claude/scripts/status.py"
  }
}
```

> Если в файле уже есть `"permissions"` — не перезаписывай весь файл,
> а добавь блоки `"hooks"` и `"statusLine"` рядом с существующими ключами.

### 4. PostgreSQL для полной функциональности

Нужна для: сессионной памяти, ledger'ов, семантического поиска по истории.

#### Вариант A: через Docker (Linux/macOS или Windows с WSL2)

```bash
# Скопировать docker-compose из репозитория
cp -r /tmp/cc3/docker ~/.claude/docker

# Запустить контейнер
cd ~/.claude/docker
docker compose up -d

# Проверить
docker exec continuous-claude-postgres pg_isready -U claude
```

#### Вариант Б: прямая установка PostgreSQL (Windows без виртуализации)

Docker Desktop требует виртуализации (WSL2/Hyper-V). Если виртуализация недоступна —
устанавливай PostgreSQL напрямую.

**Шаг 1 — Установить PostgreSQL 16:**
```bash
winget install PostgreSQL.PostgreSQL.16 --accept-package-agreements --accept-source-agreements
```
В окне установщика: Password = `postgres`, Port = `5432`, StackBuilder — пропустить.

**Шаг 2 — Создать пользователя и базу данных:**
```bash
# В bash (после установки)
PGPASSWORD=postgres "/c/Program Files/PostgreSQL/16/bin/psql" -U postgres -c \
  "CREATE USER claude WITH PASSWORD 'claude_dev';"

PGPASSWORD=postgres "/c/Program Files/PostgreSQL/16/bin/psql" -U postgres -c \
  "CREATE DATABASE continuous_claude OWNER claude;"

PGPASSWORD=postgres "/c/Program Files/PostgreSQL/16/bin/psql" -U postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE continuous_claude TO claude;"
```

**Шаг 3 — Установить расширение pgvector:**

PostgreSQL не включает pgvector. Нужно скачать бинарник для Windows:

```powershell
# Скачать pgvector для pg16
Invoke-WebRequest `
  -Uri "https://github.com/andreiramani/pgvector_pgsql_windows/releases/download/0.8.2_16.1/vector.v0.8.2-pg16.zip" `
  -OutFile "C:\Temp\vector-pg16.zip"

# Распаковать
Expand-Archive -Path "C:\Temp\vector-pg16.zip" -DestinationPath "C:\Temp\pgvector-pg16" -Force
```

Затем запустить **PowerShell от имени администратора** и выполнить:
```powershell
$pg = "C:\Program Files\PostgreSQL\16"
Copy-Item "C:\Temp\pgvector-pg16\lib\vector.dll"         "$pg\lib\vector.dll" -Force
Copy-Item "C:\Temp\pgvector-pg16\share\extension\*"      "$pg\share\extension\" -Force
$inc = "$pg\include\server\extension\vector"
New-Item -ItemType Directory -Path $inc -Force | Out-Null
Copy-Item "C:\Temp\pgvector-pg16\include\server\extension\vector\*" $inc -Force
```

**Шаг 4 — Получить файл схемы:**
```bash
# Схема уже есть если клонировал репо на Шаге 2:
mkdir -p ~/.claude/docker
cp /tmp/cc3/docker/init-schema.sql ~/.claude/docker/

# Если репо не клонировал — скачать напрямую:
curl -L https://raw.githubusercontent.com/parcadei/Continuous-Claude-v3/main/docker/init-schema.sql \
  -o ~/.claude/docker/init-schema.sql
```

**Шаг 5 — Включить расширения и применить схему:**
```bash
export PGPASSWORD=postgres
PSQL="/c/Program Files/PostgreSQL/16/bin/psql"

"$PSQL" -U postgres -d continuous_claude -c "CREATE EXTENSION IF NOT EXISTS vector;"
"$PSQL" -U postgres -d continuous_claude -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
"$PSQL" -U postgres -d continuous_claude -f ~/.claude/docker/init-schema.sql
"$PSQL" -U postgres -d continuous_claude -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO claude;"
"$PSQL" -U postgres -d continuous_claude -c "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO claude;"
```

**Шаг 6 — Создать `.env` файл:**
```bash
cat > ~/.claude/scripts/.env << 'EOF'
DATABASE_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude
CONTINUOUS_CLAUDE_DB_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=continuous_claude
POSTGRES_USER=claude
POSTGRES_PASSWORD=claude_dev
EOF
```

**Шаг 7 — Проверить:**
```bash
PGPASSWORD=claude_dev "/c/Program Files/PostgreSQL/16/bin/psql" \
  -U claude -d continuous_claude -c "\dt"
# Должны появиться: sessions, file_claims, archival_memory, handoffs
```

#### Итоговые параметры подключения

| Параметр | Значение |
|----------|---------|
| Host | `localhost:5432` |
| Database | `continuous_claude` |
| User | `claude` |
| Password | `claude_dev` |
| `DATABASE_URL` | `postgresql://claude:claude_dev@localhost:5432/continuous_claude` |

### 5. Проверить установку

Перезапустить Claude Code. При старте сессии в чате должно появиться сообщение о регистрации сессии. Команда `/discovery-interview` должна быть доступна.

---

## Структура файлов `~/.claude/`

```
~/.claude/
├── skills/          # 114 скилов (SKILL.md файлы)
├── agents/          # 48 агентов (markdown-инструкции)
├── hooks/           # 50 хуков (dist/*.mjs скомпилированные)
├── rules/           # 12 глобальных правил поведения Claude
├── scripts/         # Python-утилиты (status.py, recall и др.)
├── plugins/         # Плагины (braintrust-tracing и др.)
└── settings.local.json  # Конфигурация хуков и разрешений
```
