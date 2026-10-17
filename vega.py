"""Вега — голосовой собеседник на Claude.

Enter — начать запись, Enter — закончить. Скажи «выход», чтобы завершить.
"""

import queue
import re
import sys
import threading
from pathlib import Path

import anthropic
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from piper import PiperVoice

ROOT = Path(__file__).parent
MODEL = "claude-opus-5-5"
WHISPER_SIZE = "small"  # tiny / base / small / medium — точнее, но медленнее
VOICE_PATH = ROOT / "voices" / "ru_RU-irina-medium.onnx"
MIC_RATE = 16000  # whisper ждёт 16 кГц моно
EXIT_WORDS = {"выход", "стоп", "пока"}

SYSTEM = """Тебя зовут Вега. Ты голосовой ассистент: всё, что ты пишешь, синтезируется в речь.
Отвечай по-русски, коротко и живо, как в разговоре — обычно 1–3 предложения.
Никакого markdown, списков, эмодзи, кода и ссылок. Числа и сокращения пиши так, как их произносят.
Текст пользователя получен распознаванием речи и может содержать ошибки — угадывай смысл."""

SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
MARKDOWN = re.compile(r"[*_#`>\[\]|~]")


class Speaker:
    """Озвучивает предложения по мере их поступления, в отдельном потоке."""

    def __init__(self, voice_path: Path):
        self.voice = PiperVoice.load(str(voice_path))
        self.queue: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str):
        text = MARKDOWN.sub("", text).strip()
        if text:
            self.queue.put(text)

    def wait(self):
        self.queue.join()

    def _run(self):
        while True:
            text = self.queue.get()
            try:
                chunks = list(self.voice.synthesize(text))
                if chunks:
                    audio = np.concatenate([c.audio_int16_array for c in chunks])
                    sd.play(audio, chunks[0].sample_rate)
                    sd.wait()
            except Exception as e:
                print(f"\n[TTS ошибка: {e}]", file=sys.stderr)
            finally:
                self.queue.task_done()


def record() -> np.ndarray:
    frames: list[np.ndarray] = []
    with sd.InputStream(samplerate=MIC_RATE, channels=1, dtype="float32",
                        callback=lambda data, *_: frames.append(data.copy())):
        input("🎙  Говори... (Enter — стоп)")
    return np.concatenate(frames).flatten() if frames else np.zeros(0, np.float32)


def transcribe(stt: WhisperModel, audio: np.ndarray) -> str:
    if len(audio) < MIC_RATE * 0.3:
        return ""
    segments, _ = stt.transcribe(audio, language="ru", vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


def reply(client: anthropic.Anthropic, history: list, speaker: Speaker):
    buffer = ""
    print("Вега: ", end="", flush=True)
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        messages=history,
        output_config={"effort": "low"},  # для разговора важнее скорость ответа
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            buffer += text
            *done, buffer = SENTENCE_END.split(buffer)
            for sentence in done:
                speaker.say(sentence)
        final = stream.get_final_message()
    speaker.say(buffer)
    print()

    if final.stop_reason == "refusal":
        speaker.say("Извини, на это я ответить не могу.")
    history.append({"role": "assistant", "content": final.content})


def main():
    print("Загрузка моделей...")
    stt = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    speaker = Speaker(VOICE_PATH)
    client = anthropic.Anthropic()
    history: list = []

    print("Готово. Enter — начать говорить, Ctrl+C — выход.\n")
    speaker.say("Привет, я Вега. Слушаю.")
    speaker.wait()

    while True:
        input("⏎  Enter, чтобы говорить")
        text = transcribe(stt, record())
        if not text:
            print("(ничего не расслышала)\n")
            continue
        print(f"Ты: {text}")
        if text.lower().strip(" .!?") in EXIT_WORDS:
            speaker.say("До связи.")
            speaker.wait()
            break

        history.append({"role": "user", "content": text})
        try:
            reply(client, history, speaker)
        except anthropic.AuthenticationError:
            sys.exit("Нет доступа к API: задай переменную окружения ANTHROPIC_API_KEY.")
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError) as e:
            history.pop()
            print(f"[Ошибка API: {e}]")
            speaker.say("Что-то со связью, повтори, пожалуйста.")
        speaker.wait()
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПока!")
