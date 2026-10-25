import io
import os
from urllib.parse import urlencode

import requests

VOICEVOX_LOCAL_FILE = "test.wav"

WHISPER_DEFAULT_URL = "http://127.0.0.1:8178"
VOICEVOX_DEFAULT_URL = "http://127.0.0.1:50021"


def _env_url(name, default):
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().rstrip("/")


def _body_snippet(response, limit=200):
    compact = " ".join((response.text or "").split())
    if len(compact) > limit:
        return compact[:limit]
    return compact


def transcribe(filename):
    with open(filename, "rb") as audio:
        wav_bytes = audio.read()

    response = requests.post(
        _env_url("WHISPER_URL", WHISPER_DEFAULT_URL) + "/inference",
        data=wav_bytes,
        headers={"Content-Type": "application/octet-stream"},
        timeout=120,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"whisper inference failed ({response.status_code}): {_body_snippet(response)}"
        )

    payload = response.json()
    message = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(message, str) or len(message.strip()) == 0:
        return None
    return message


def speak_jp(text, speaker=None):
    import utils.audio
    import utils.vtube_studio

    if speaker is None:
        speaker = int(os.environ.get("VOICEVOX_SPEAKER") or 46)
    else:
        speaker = int(speaker)

    base = _env_url("VOICEVOX_URL", VOICEVOX_DEFAULT_URL)
    query = requests.post(
        f"{base}/audio_query?{urlencode({'text': text, 'speaker': speaker})}"
    )
    if query.status_code != 200:
        raise RuntimeError(
            f"voicevox audio_query failed ({query.status_code}): {_body_snippet(query)}"
        )

    synthesis = requests.post(
        f"{base}/synthesis?{urlencode({'speaker': speaker, 'enable_interrogative_upspeak': True})}",
        json=query.json(),
    )
    if synthesis.status_code != 200:
        raise RuntimeError(
            f"voicevox synthesis failed ({synthesis.status_code}): {_body_snippet(synthesis)}"
        )

    with io.BytesIO(synthesis.content) as memfile:
        utils.audio.play(memfile, utils.vtube_studio.set_audio_level)
