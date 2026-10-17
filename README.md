# Вега — голосовой собеседник на Claude

Говоришь голосом, Вега отвечает голосом. Пока только разговор, без управления компьютером.

```
Enter → запись с микрофона → Enter → faster-whisper (речь→текст)
      → Claude (потоковый ответ) → Piper (текст→речь по предложениям) → динамики
```

## Запуск

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\python vega.py
```

Скажи «выход», «стоп» или «пока», чтобы завершить (или Ctrl+C).

## Установка с нуля

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m piper.download_voices --download-dir voices ru_RU-irina-medium
```

Другие русские голоса Piper: `ru_RU-denis-medium`, `ru_RU-dmitri-medium`, `ru_RU-ruslan-medium`
(путь меняется в `VOICE_PATH` в `vega.py`).

## Настройки (`vega.py`)

- `MODEL` — модель Claude.
- `WHISPER_SIZE` — `small` по умолчанию; `medium` точнее, но медленнее на CPU.
- `effort` в `reply()` — `low` для быстрых ответов.

## Голос для Claude Code без API-ключа

- **Ввод:** встроенная диктовка Claude Code — `/voice` (нужен вход через claude.ai, язык — `/config` → Russian).
- **Вывод:** `speak_hook.py` озвучивает каждый ответ Claude голосом Piper (локально, бесплатно).
  Новое сообщение обрывает речь. Файл `.mute` рядом со скриптом — выключить звук.

В `~/.claude/settings.json` добавить:

```json
"hooks": {
  "Stop": [{ "hooks": [{ "type": "command", "timeout": 15,
    "command": "\"C:/Users/raven/Documents/studio_projects/vega/.venv/Scripts/python.exe\" \"C:/Users/raven/Documents/studio_projects/vega/speak_hook.py\"" }] }],
  "UserPromptSubmit": [{ "hooks": [{ "type": "command", "timeout": 15,
    "command": "\"C:/Users/raven/Documents/studio_projects/vega/.venv/Scripts/python.exe\" \"C:/Users/raven/Documents/studio_projects/vega/speak_hook.py\" --stop" }] }]
}
```

### Без кнопок: `vega_listen.py`

Постоянно слушает микрофон; фразу «Вега, ...» распознаёт локально и набирает в окно Claude Code
с Enter. Пока Вега говорит, микрофон игнорируется.

```powershell
.venv\Scripts\python vega_listen.py           # только фразы со словом «Вега»
.venv\Scripts\python vega_listen.py --always  # отправлять всё сказанное
```

После запуска есть 5 секунд, чтобы переключиться в окно Claude Code — оно запоминается как цель.

## macOS (без прав администратора)

Скопировать папку `vega` без `.venv/` и `voices/`, затем:

```bash
bash vega/setup_mac.sh
```

Скрипт ничего не ставит в систему и не просит sudo:

- **Python 3.10+** — берёт найденный; если его нет, ставит [uv](https://docs.astral.sh/uv/) и Python 3.12 в домашнюю папку.
- **Зависимости и голос** — в `.venv/` и `voices/`.
- **tmux** — через Homebrew, если он доступен на запись; иначе через micromamba в `.tools/`.
- **Хуки озвучки** — сам дописывает в `~/.claude/settings.json` (прежняя версия — в `settings.json.bak`).

Запуск — из папки проекта, где нужен Claude Code:

```bash
bash ~/path/to/vega/start_mac.sh           # только фразы со словом «Вега»
bash ~/path/to/vega/start_mac.sh --always  # отправлять всё сказанное
```

Откроется tmux-сессия `vega`: слева Claude Code, справа `vega_listen.py`. Текст уходит в Claude Code
через `tmux send-keys`, поэтому «Универсальный доступ» и «Мониторинг ввода» не нужны — их без админа не выдать.
macOS спросит только доступ к **Микрофону**, он даётся без пароля админа.
Остановить речь — **Ctrl+B, затем S**. Отключиться от сессии — Ctrl+B, затем D; вернуться — снова `start_mac.sh`.

Если Claude Code уже запущен в своём tmux, `vega_listen.py` найдёт его панель сам; задать явно — `VEGA_TMUX=main:0.1`.
Без tmux слушатель работает как раньше: вставка через буфер обмена и Ctrl+Cmd+S, но тогда нужны
«Универсальный доступ» и «Мониторинг ввода».

## Дальше

1. Wake word «Вега» + автоопределение конца фразы (VAD) — без нажатия Enter.
2. Перебивание: замолкает, когда начинаешь говорить.
3. Голос получше (ElevenLabs и т.п.).
4. Инструменты: управление компьютером.
5. HUD-интерфейс.
