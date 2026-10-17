#!/bin/bash
# Установка Веги на macOS без прав администратора. Запуск: bash setup_mac.sh
# Всё ставится в папку проекта (.venv, .tools, voices) и в домашнюю папку — sudo не нужен.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
TOOLS="$DIR/.tools/bin"
mkdir -p "$TOOLS"
export PATH="$TOOLS:$PATH"

# --- Python 3.10+ ---
# /usr/bin/python3 без Command Line Tools — заглушка, которая просит установку с правами админа.
find_python() {
  for py in python3.13 python3.12 python3.11 python3.10 python3; do
    local path
    path="$(command -v "$py" 2>/dev/null)" || continue
    if [ "$path" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
      continue
    fi
    if "$path" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      echo "$path"
      return
    fi
  done
}

if [ ! -x .venv/bin/python ]; then
  PYTHON="$(find_python)"
  if [ -n "$PYTHON" ]; then
    "$PYTHON" -m venv .venv
  else
    echo "Python 3.10+ не найден — ставлю uv и Python 3.12 в домашнюю папку."
    command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh |
      env UV_INSTALL_DIR="$TOOLS" INSTALLER_NO_MODIFY_PATH=1 sh
    uv venv --python 3.12 --seed .venv
  fi
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
mkdir -p voices
[ -f voices/ru_RU-irina-medium.onnx ] ||
  .venv/bin/python -m piper.download_voices --download-dir voices ru_RU-irina-medium

# --- tmux: текст уходит в Claude Code через него, без «Универсального доступа» ---
if ! command -v tmux >/dev/null; then
  if command -v brew >/dev/null && [ -w "$(brew --prefix)" ]; then
    brew install tmux
  else
    echo "Ставлю tmux через micromamba (conda-forge) в .tools."
    case "$(uname -m)" in arm64) ARCH=osx-arm64 ;; *) ARCH=osx-64 ;; esac
    curl -Ls "https://micro.mamba.pm/api/micromamba/$ARCH/latest" | tar -xj -C "$DIR/.tools" bin/micromamba
    "$TOOLS/micromamba" create -y -q -r "$DIR/.tools/mamba" -p "$DIR/.tools/env" -c conda-forge tmux
    ln -sf "$DIR/.tools/env/bin/tmux" "$TOOLS/tmux"
  fi
fi

# --- хуки озвучки в ~/.claude/settings.json (старая версия файла сохраняется в .bak) ---
.venv/bin/python - "$DIR" <<'EOF'
import json, os, shutil, sys
from pathlib import Path

root = Path(sys.argv[1])
settings = Path(os.environ.get("CLAUDE_SETTINGS", Path.home() / ".claude" / "settings.json"))
data = json.loads(settings.read_text()) if settings.exists() else {}
if settings.exists():
    shutil.copy(settings, settings.with_suffix(".json.bak"))
base = f'"{root}/.venv/bin/python" "{root}/speak_hook.py"'
hooks = data.setdefault("hooks", {})
for event, command in (("Stop", base), ("UserPromptSubmit", base + " --stop")):
    entries = hooks.setdefault(event, [])
    if not any(h.get("command") == command for e in entries for h in e.get("hooks", [])):
        entries.append({"hooks": [{"type": "command", "timeout": 15, "command": command}]})
settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"Хуки озвучки добавлены в {settings}")
EOF

cat <<EOF

Готово. Запуск: bash $DIR/start_mac.sh
(из папки проекта, где нужен Claude Code; аргументы передаются в vega_listen.py, например --always)

macOS один раз спросит доступ к микрофону для терминала — это разрешение даётся без пароля админа.
EOF
