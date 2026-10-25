import os
import threading

import requests

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_PERSONALITY_FILE = "personality.txt"
MAX_PAIRS = 8
CHAT_TIMEOUT_SECONDS = 120
TAGS_TIMEOUT_SECONDS = 10

reply_callback = None
messages = []
_system_loaded = False


def _env_url():
    value = os.environ.get("OLLAMA_URL")
    if value is None or not str(value).strip():
        return DEFAULT_OLLAMA_URL
    return str(value).strip().rstrip("/")


def _model_name():
    value = os.environ.get("OLLAMA_MODEL")
    if value is None:
        return ""
    return str(value).strip()


def _personality_path():
    value = os.environ.get("PERSONALITY_FILE")
    if value is None or not str(value).strip():
        return DEFAULT_PERSONALITY_FILE
    return str(value).strip()


def _body_snippet(response, limit=200):
    compact = " ".join((response.text or "").split())
    if len(compact) > limit:
        return compact[:limit]
    return compact


def _load_system_prompt():
    path = _personality_path()
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeError) as exc:
        print(f"Could not read personality file {path}: {exc}", flush=True)
        return ""


def _ensure_system_prompt():
    global _system_loaded
    if _system_loaded:
        return
    prompt = _load_system_prompt()
    if messages and messages[0].get("role") == "system":
        messages[0] = {"role": "system", "content": prompt}
    else:
        messages.insert(0, {"role": "system", "content": prompt})
    _system_loaded = True


def _bounded(history):
    system = history[0]
    groups = []
    current = []
    for item in history[1:]:
        if item.get("role") == "user" and current:
            groups.append(current)
            current = [item]
        else:
            current.append(item)
    if current:
        groups.append(current)
    kept = []
    for group in groups[-MAX_PAIRS:]:
        kept.extend(group)
    return [system] + kept


def _tag_names(payload):
    names = []
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return names
    for item in models:
        if isinstance(item, str):
            if item not in names:
                names.append(item)
            continue
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            value = item.get(key)
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def _check_ollama():
    url = _env_url() + "/api/tags"
    model = _model_name()
    try:
        response = requests.get(url, timeout=TAGS_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        print(f"Ollama connection failed ({url}): {exc}", flush=True)
        return
    if response.status_code != 200:
        print(
            f"Ollama connection failed ({url}): HTTP {response.status_code}: {_body_snippet(response)}",
            flush=True,
        )
        return
    try:
        payload = response.json()
    except ValueError as exc:
        print(f"Ollama connection failed ({url}): {exc}", flush=True)
        return
    names = _tag_names(payload)
    if model not in names:
        shown = ", ".join(names) if names else "(none)"
        print(
            f"OLLAMA_MODEL {model!r} is not in the Ollama tag list at {url}. Installed: {shown}",
            flush=True,
        )


def run_async():
    thread = threading.Thread(target=_check_ollama, name="ollama-tags", daemon=True)
    thread.start()
    return thread


def send_message(text):
    _ensure_system_prompt()
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    messages.append({"role": "user", "content": text})
    outbound = _bounded(messages)
    messages[:] = outbound

    url = _env_url() + "/api/chat"
    payload = {
        "model": _model_name(),
        "messages": outbound,
        "stream": False,
        "think": False,
        "options": {
            "num_predict": 120,
            "num_ctx": 4096,
        },
    }
    try:
        response = requests.post(url, json=payload, timeout=CHAT_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        print(f"Ollama chat request failed ({url}): {exc}", flush=True)
        return

    if response.status_code != 200:
        print(
            f"Ollama chat HTTP {response.status_code}: {_body_snippet(response)}",
            flush=True,
        )
        return

    try:
        body = response.json()
    except ValueError:
        print(
            f"Ollama chat HTTP {response.status_code}: {_body_snippet(response)}",
            flush=True,
        )
        return

    message = body.get("message") if isinstance(body, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        print(
            f"Ollama chat HTTP {response.status_code}: {_body_snippet(response)}",
            flush=True,
        )
        return

    messages.append({"role": "assistant", "content": content})
    trimmed = _bounded(messages)
    messages[:] = trimmed
    if reply_callback is not None:
        reply_callback(content)


_ensure_system_prompt()
