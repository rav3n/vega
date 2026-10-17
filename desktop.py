"""Платформозависимые части слушателя: выбор окна, набор текста, горячая клавиша.

  pick_target()             — запомнить окно/приложение с Claude Code
  deliver(target, text)     — набрать текст в нём и нажать Enter
  stop_hotkey_loop(on_stop) — глобальная горячая клавиша «замолчи» (блокирует поток)
"""

import sys
import time

STOP_HOTKEY = "Ctrl+Cmd+S" if sys.platform == "darwin" else "Ctrl+Alt+S"


def _countdown():
    for i in range(5, 0, -1):
        print(f"\rПереключись в окно с Claude Code... {i} ", end="", flush=True)
        time.sleep(1)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, VK_RETURN = 0x2, 0x4, 0x0D
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, VK_S, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x53, 0x312

    def _send(*events: KEYBDINPUT):
        arr = (INPUT * len(events))(*(INPUT(type=1, ki=e) for e in events))
        user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))

    def _type_text(text: str):
        # SendInput с юникодом — без буфера обмена
        data = text.encode("utf-16-le")
        for i in range(0, len(data), 2):
            code = int.from_bytes(data[i:i + 2], "little")
            _send(KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0),
                  KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
        time.sleep(0.05)
        _send(KEYBDINPUT(VK_RETURN, 0, 0, 0, 0), KEYBDINPUT(VK_RETURN, 0, KEYEVENTF_KEYUP, 0, 0))

    def pick_target():
        _countdown()
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        print(f"\rЦелевое окно: «{buf.value}»          ")
        return hwnd

    def deliver(hwnd, text: str) -> bool:
        if user32.GetForegroundWindow() != hwnd:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
        if user32.GetForegroundWindow() != hwnd:
            print("  [окно Claude Code не в фокусе — не отправлено]")
            return False
        _type_text(text)
        return True

    def stop_hotkey_loop(on_stop):
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_S):
            print(f"[не удалось занять {STOP_HOTKEY} — оно уже используется другой программой]")
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                on_stop()

elif sys.platform == "darwin":
    import os
    import re
    import shutil
    import subprocess
    from pathlib import Path

    def _osascript(script: str) -> str:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()

    def _frontmost_app() -> str:
        return _osascript('tell application "System Events" to get name of first application process '
                          "whose frontmost is true")

    def _tmux(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["tmux", *args], capture_output=True, text=True)

    def _claude_pane() -> str | None:
        """Панель tmux с Claude Code. VEGA_TMUX задаёт её явно, например «main:0.1»."""
        if os.environ.get("VEGA_TMUX"):
            return os.environ["VEGA_TMUX"]
        if not shutil.which("tmux"):
            return None
        panes = _tmux("list-panes", "-a", "-F", "#{pane_id} #{pane_current_command}").stdout
        for line in panes.splitlines():
            pane, _, command = line.partition(" ")
            # нативный claude может называться по версии: ~/.local/share/claude/versions/2.1.302
            if command == "claude" or re.fullmatch(r"\d+\.\d+\.\d+", command):
                return pane
        return None

    def _bind_tmux_stop():
        # Мониторинг ввода без админа не выдать, поэтому «замолчи» — на клавише tmux: префикс, затем S
        hook = Path(__file__).with_name("speak_hook.py")
        _tmux("bind-key", "S", "run-shell", "-b", f"'{sys.executable}' '{hook}' --stop < /dev/null")

    _use_tmux = False

    def pick_target():
        global STOP_HOTKEY, _use_tmux
        # tmux send-keys не требует «Универсального доступа»
        pane = _claude_pane()
        if pane:
            _bind_tmux_stop()
            _use_tmux = True
            STOP_HOTKEY = "Ctrl+B, затем S"
            print(f"Целевая панель tmux: {pane}")
            return ("tmux", pane)
        _countdown()
        app = _frontmost_app()
        print(f"\rЦелевое приложение: «{app}»          ")
        return ("app", app)

    def deliver(target: tuple[str, str], text: str) -> bool:
        kind, name = target
        if kind == "tmux":
            if _tmux("send-keys", "-t", name, "-l", text).returncode != 0:
                print(f"  [панель tmux {name} недоступна — не отправлено]")
                return False
            time.sleep(0.1)  # иначе Enter приходит вместе с текстом, как вставка, и не отправляет
            _tmux("send-keys", "-t", name, "Enter")
            return True
        return _deliver_app(name, text)

    def _deliver_app(app: str, text: str) -> bool:
        # Русский текст через keystroke печатается криво, поэтому вставка из буфера обмена.
        # Нужно разрешение: Настройки → Конфиденциальность → Универсальный доступ → терминал.
        previous = subprocess.run(["pbpaste"], capture_output=True).stdout
        subprocess.run(["pbcopy"], input=text.encode("utf-8"))
        _osascript(f'tell application "{app}" to activate')
        time.sleep(0.2)
        if _frontmost_app() != app:
            print(f"  [«{app}» не в фокусе — не отправлено]")
            subprocess.run(["pbcopy"], input=previous)
            return False
        _osascript('tell application "System Events"\n'
                   '  keystroke "v" using command down\n'
                   "  delay 0.1\n"
                   "  key code 36\n"
                   "end tell")
        time.sleep(0.2)
        subprocess.run(["pbcopy"], input=previous)
        return True

    def stop_hotkey_loop(on_stop):
        # Нужно разрешение: Настройки → Конфиденциальность → Мониторинг ввода → терминал.
        if _use_tmux:
            return  # «замолчи» висит на клавише tmux, разрешение не нужно
        try:
            from pynput import keyboard
        except ImportError:
            print("[pynput не установлен — горячая клавиша отключена]")
            return
        with keyboard.GlobalHotKeys({"<ctrl>+<cmd>+s": on_stop}) as listener:
            listener.join()

else:
    sys.exit("Поддерживаются только Windows и macOS.")
