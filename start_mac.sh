#!/bin/bash
# Запуск без прав администратора: tmux-сессия «vega» — слева Claude Code, справа слушатель.
# Claude Code стартует в текущей папке. Аргументы уходят в vega_listen.py (например, --always).
set -euo pipefail
WORKDIR="$(pwd)"
DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$DIR/.tools/bin:$HOME/.local/bin:$PATH"
SESSION=vega

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  PANE="$(tmux new-session -d -P -F '#{pane_id}' -s "$SESSION" -c "$WORKDIR" claude)"
  tmux split-window -h -l 35% -t "$PANE" -c "$DIR" -e "VEGA_TMUX=$PANE" \
    "'$DIR/.venv/bin/python' vega_listen.py $*; read -rp 'Enter — закрыть панель'"
  tmux select-pane -t "$PANE"
fi
exec tmux attach -t "$SESSION"
