"""Pronunciation audio from a local TTS engine.

Local synthesis rather than a cloud voice: no key, no rate limit, no per-character
cost, and every word in a list gets audio instead of only the ones some dictionary
happens to have a recording for.

``piper`` gives markedly better voices than formant synthesis, but it is useless
without a voice model, so it is preferred only when one is actually configured --
otherwise a piper install would shadow a working espeak-ng and silently cost the
deck its audio.  ``espeak-ng`` is the fallback because it is packaged everywhere and
needs no model.  If neither can run, the caller is told once and the run continues
without audio: a missing engine should not cost someone their deck.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from . import media_dir

# Where to find a piper voice model when one is not passed explicitly.
VOICE_ENV_VAR = "ANKIGEN_PIPER_VOICE"


class TTSUnavailable(RuntimeError):
    """No usable TTS engine is installed."""


# espeak-ng voice names differ from ISO codes for a few languages.
_ESPEAK_VOICES = {"de": "de", "en": "en-us", "fr": "fr", "es": "es", "it": "it", "ru": "ru"}


def _resolve_voice(voice: str | None) -> str:
    return voice or os.environ.get(VOICE_ENV_VAR, "")


def _engine(voice: str | None = None) -> tuple[str, str, str]:
    """Return ``(engine, executable, voice model)`` for the best usable engine.

    Piper only wins when its model is on disk; that check is what keeps an
    unconfigured piper from shadowing a perfectly good espeak-ng.
    """
    resolved = _resolve_voice(voice)
    piper = shutil.which("piper")
    if piper and resolved and Path(resolved).is_file():
        return ("piper", piper, resolved)

    for name in ("espeak-ng", "espeak"):
        path = shutil.which(name)
        if path:
            return ("espeak", path, "")

    if piper and resolved:
        raise TTSUnavailable(f"piper voice model not found: {resolved}")
    if piper:
        raise TTSUnavailable(
            f"piper is installed but no voice model is configured — set {VOICE_ENV_VAR} "
            "or pass --voice, or install espeak-ng"
        )
    raise TTSUnavailable(
        "no TTS engine found — install espeak-ng, or piper plus a voice model, "
        "or pass --no-audio"
    )


def synthesize(word: str, lang: str, voice: str | None = None) -> str:
    """Produce an audio file for *word* and return its path.

    Output is cached by word and language, so regenerating a deck reuses the audio
    already on disk instead of re-synthesising every run.
    """
    engine, executable, model = _engine(voice)
    key = hashlib.sha256(f"{engine}|{lang}|{model}|{word}".encode()).hexdigest()[:16]
    out = media_dir("audio") / f"{key}.wav"
    if out.is_file() and out.stat().st_size > 0:
        return str(out)

    if engine == "piper":
        cmd = [executable, "--model", model, "--output_file", str(out)]
        stdin = word.encode("utf-8")
    else:
        cmd = [executable, "-v", _ESPEAK_VOICES.get(lang, lang), "-w", str(out), word]
        stdin = None

    result = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60)
    if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"{engine} failed: {detail or result.returncode}")
    return str(out)


def available(voice: str | None = None) -> bool:
    """Whether audio can be generated at all, for a pre-run check."""
    try:
        _engine(voice)
    except TTSUnavailable:
        return False
    return True
