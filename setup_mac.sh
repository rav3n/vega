#!/bin/bash
# Установка Веги на macOS. Запуск: bash setup_mac.sh (из папки vega)
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"

python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
mkdir -p voices
.venv/bin/python -m piper.download_voices --download-dir voices ru_RU-irina-medium

PY="$DIR/.venv/bin/python"
HOOK="$DIR/speak_hook.py"
cat <<EOF

Готово. Добавь в ~/.claude/settings.json (внутрь верхних { }):

"hooks": {
  "Stop": [{ "hooks": [{ "type": "command", "timeout": 15,
    "command": "\"$PY\" \"$HOOK\"" }] }],
  "UserPromptSubmit": [{ "hooks": [{ "type": "command", "timeout": 15,
    "command": "\"$PY\" \"$HOOK\" --stop" }] }]
}

Затем: .venv/bin/python vega_listen.py
macOS спросит разрешения для терминала: Микрофон, Универсальный доступ, Мониторинг ввода.
EOF
