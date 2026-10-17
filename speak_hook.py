"""Хуки Claude Code: озвучивают ответы Claude голосом Piper.

  speak_hook.py          — Stop-хук: читает JSON со stdin и озвучивает last_assistant_message
  speak_hook.py --stop   — UserPromptSubmit-хук: обрывает текущую речь
  speak_hook.py --play F — внутренний режим: проигрывает текст из файла F

Чтобы временно выключить звук, создай файл .mute рядом со скриптом.
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
VOICE_PATH = ROOT / "voices" / "ru_RU-irina-medium.onnx"
MUTE_FILE = ROOT / ".mute"
STATE_DIR = Path(tempfile.gettempdir()) / "vega-speak"
PID_FILE = STATE_DIR / "player.pid"
MAX_CHARS = 350  # озвучивается только начало ответа, остальное читается с экрана

CLEANUP = [
    (re.compile(r"```.*?```", re.S), " Пример кода — на экране. "),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # [текст](ссылка) → текст
    (re.compile(r"https?://\S+"), " ссылка "),
    (re.compile(r"^\s*\|.*\|\s*$", re.M), ""),  # строки таблиц
    (re.compile(r"^\s*[-*]\s+", re.M), ""),  # маркеры списков
    (re.compile(r"[*_#`>|~]"), ""),
    (re.compile(r"\s+"), " "),
]


def clean(text: str) -> str:
    for pattern, repl in CLEANUP:
        text = pattern.sub(repl, text)
    text = text.strip()
    if len(text) > MAX_CHARS:
        cut = text.rfind(".", 0, MAX_CHARS)
        text = text[: cut + 1 if cut > 0 else MAX_CHARS] + " Подробности на экране."
    return text


def stop_playing():
    try:
        pid = int(PID_FILE.read_text())
    except (OSError, ValueError):
        return
    if sys.platform == "win32":
        # pythonw из venv — лаунчер, сам плеер живёт в дочернем процессе, поэтому /T
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass
    PID_FILE.unlink(missing_ok=True)


def start_playing(text: str):
    STATE_DIR.mkdir(exist_ok=True)
    text_file = STATE_DIR / "text.txt"
    text_file.write_text(text, encoding="utf-8")
    if sys.platform == "win32":
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        python = str(pythonw if pythonw.exists() else sys.executable)
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        python = sys.executable
        detach = {"start_new_session": True}  # своя группа процессов — для killpg
    proc = subprocess.Popen(
        [python, __file__, "--play", str(text_file)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, **detach,
    )
    PID_FILE.write_text(str(proc.pid))


def play(text_file: str):
    import numpy as np
    import sounddevice as sd
    from piper import PiperVoice

    voice = PiperVoice.load(str(VOICE_PATH))
    text = Path(text_file).read_text(encoding="utf-8")
    try:
        # синтезируем и играем по предложениям, чтобы речь начиналась сразу
        for sentence in re.split(r"(?<=[.!?…])\s+", text):
            chunks = list(voice.synthesize(sentence))
            if chunks:
                sd.play(np.concatenate([c.audio_int16_array for c in chunks]), chunks[0].sample_rate)
                sd.wait()
    finally:
        # по наличию этого файла vega_listen.py понимает, что Вега сейчас говорит
        PID_FILE.unlink(missing_ok=True)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--play":
        play(sys.argv[2])
        return

    sys.stdin.reconfigure(encoding="utf-8")
    event = json.loads(sys.stdin.read() or "{}")
    stop_playing()
    if sys.argv[1:] == ["--stop"] or MUTE_FILE.exists():
        return
    text = clean(event.get("last_assistant_message") or "")
    if text:
        start_playing(text)


if __name__ == "__main__":
    main()
