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

## macOS

Скопировать папку `vega` без `.venv/` и `voices/`, затем:

```bash
cd vega && bash setup_mac.sh
```

Скрипт поставит зависимости, скачает голос и напечатает блок `hooks` для `~/.claude/settings.json`.
Терминалу нужны разрешения (Настройки → Конфиденциальность и безопасность):
**Микрофон**, **Универсальный доступ** (вставка текста в окно), **Мониторинг ввода** (горячая клавиша).
Остановить речь — **Ctrl+Cmd+S**. Текст вставляется через буфер обмена (прежнее содержимое восстанавливается).

## Дальше

1. Wake word «Вега» + автоопределение конца фразы (VAD) — без нажатия Enter.
2. Перебивание: замолкает, когда начинаешь говорить.
3. Голос получше (ElevenLabs и т.п.).
4. Инструменты: управление компьютером.
5. HUD-интерфейс.
