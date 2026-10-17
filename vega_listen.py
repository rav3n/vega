"""Голосовой ввод для Claude Code без нажатия клавиш.

Постоянно слушает микрофон. Фраза, начинающаяся с «Вега», распознаётся локально
(faster-whisper) и набирается в окно Claude Code с нажатием Enter.
Пока Вега говорит (speak_hook.py), микрофон игнорируется.

  vega_listen.py           — реагирует только на фразы с «Вега ...»
  vega_listen.py --always  — отправляет всё сказанное
"""

import queue
import re
import sys
import threading
import time
from difflib import SequenceMatcher

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from desktop import STOP_HOTKEY, deliver, pick_target, stop_hotkey_loop
from speak_hook import PID_FILE, stop_playing

RATE = 16000
BLOCK = 480  # 30 мс
SILENCE_END = 0.9  # секунд тишины = конец фразы
MIN_PHRASE = 0.4
MAX_PHRASE = 30
WAKE_WORD = "вега"
WAKE_SIMILARITY = 0.6  # насколько первое слово должно походить на «вега»
WHISPER_SIZE = "small"
NO_SPEECH_MAX = 0.6  # сегменты, где Whisper не уверен, что это речь, отбрасываются

# --- запись фраз ---

def speaking() -> bool:
    return PID_FILE.exists()


def phrases(threshold: float):
    """Генератор фраз: накапливает звук между паузами."""
    blocks: queue.Queue[np.ndarray] = queue.Queue()
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK,
                        callback=lambda d, *_: blocks.put(d[:, 0].copy())):
        phrase, silent, pre = [], 0.0, []
        while True:
            block = blocks.get()
            if speaking():
                phrase, silent, pre = [], 0.0, []
                continue
            loud = np.sqrt(np.mean(block ** 2)) > threshold
            if not phrase:
                pre = (pre + [block])[-10:]  # 300 мс до начала речи, чтобы не съесть первый слог
                if loud:
                    phrase = pre[:]
                continue
            phrase.append(block)
            silent = 0.0 if loud else silent + BLOCK / RATE
            duration = len(phrase) * BLOCK / RATE
            if silent >= SILENCE_END or duration >= MAX_PHRASE:
                if duration - silent >= MIN_PHRASE:
                    yield np.concatenate(phrase)
                phrase, silent, pre = [], 0.0, []


def is_hallucination(text: str) -> bool:
    """Whisper на шуме выдаёт одну и ту же фразу по кругу или «субтитры» из обучающих данных."""
    sentences = [s.strip(" ,.!?…").lower() for s in re.split(r"[.!?…]+", text) if s.strip(" ,.!?…")]
    if len(sentences) >= 2 and len(set(sentences)) <= len(sentences) / 2:
        return True
    return bool(re.search(r"субтитр|продолжение следует|спасибо за просмотр", text, re.I))


def strip_wake_word(text: str) -> str | None:
    """Убирает «Вега» из начала фразы; None, если фраза не к Веге."""
    match = re.match(r"\s*([\w-]+)[\s,.!?:…-]*", text)
    if not match:
        return None
    first = match.group(1).lower().replace("э", "е")
    if SequenceMatcher(None, first, WAKE_WORD).ratio() < WAKE_SIMILARITY:
        return None
    return text[match.end():].strip()


def calibrate() -> float:
    print("Калибровка шума, помолчи секунду...")
    noise = sd.rec(RATE, samplerate=RATE, channels=1, dtype="float32")
    sd.wait()
    floor = float(np.sqrt(np.mean(noise ** 2)))
    return max(floor * 3.5, 0.008)


def main():
    always = "--always" in sys.argv
    print("Загрузка распознавания речи...")
    stt = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    threshold = calibrate()
    target = pick_target()
    threading.Thread(target=stop_hotkey_loop, args=(stop_playing,), daemon=True).start()
    hint = "говори" if always else "начинай фразу со слова «Вега»"
    print(f"Слушаю — {hint}. {STOP_HOTKEY} — замолчать, Ctrl+C — выход.\n")

    for audio in phrases(threshold):
        # без initial_prompt: на тишине Whisper начинает повторять текст подсказки
        segments, _ = stt.transcribe(audio, language="ru", vad_filter=True,
                                     condition_on_previous_text=False,
                                     hotwords=None if always else "Вега")
        text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < NO_SPEECH_MAX).strip()
        if is_hallucination(text):
            print(f"  (похоже на галлюцинацию, пропущено: {text})")
            continue
        if not text:
            continue
        if not always:
            command = strip_wake_word(text)
            if command is None:
                print(f"  (мимо: {text})")
                continue
            if not command:
                continue
            text = command
        stop_playing()
        print(f"→ {text}")
        deliver(target, text)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПока!")
