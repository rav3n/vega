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
    import subprocess

    def _osascript(script: str) -> str:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()

    def _frontmost_app() -> str:
        return _osascript('tell application "System Events" to get name of first application process '
                          "whose frontmost is true")

    def pick_target():
        _countdown()
        app = _frontmost_app()
        print(f"\rЦелевое приложение: «{app}»          ")
        return app

    def deliver(app: str, text: str) -> bool:
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
        try:
            from pynput import keyboard
        except ImportError:
            print("[pynput не установлен — горячая клавиша отключена]")
            return
        with keyboard.GlobalHotKeys({"<ctrl>+<cmd>+s": on_stop}) as listener:
            listener.join()

else:
    sys.exit("Поддерживаются только Windows и macOS.")
