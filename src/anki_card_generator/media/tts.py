"""Pronunciation audio from a local TTS engine.

Local synthesis rather than a cloud voice: no key, no rate limit, no per-character
cost, and every word in a list gets audio instead of only the ones some dictionary
happens to have a recording for.

``piper`` is preferred because its neural German voices are markedly better than
formant synthesis; ``espeak-ng`` is the fallback because it is packaged everywhere.
If neither is installed the caller is told once and the run continues without audio
-- a missing engine should not cost someone their deck.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess

from . import media_dir


class TTSUnavailable(RuntimeError):
    """No usable TTS engine is installed."""


# espeak-ng voice names differ from ISO codes for a few languages.
_ESPEAK_VOICES = {"de": "de", "en": "en-us", "fr": "fr", "es": "es", "it": "it", "ru": "ru"}


def _engine() -> tuple[str, str]:
    """Return ``(name, executable path)`` for the best available engine."""
    for name in ("piper", "espeak-ng", "espeak"):
        path = shutil.which(name)
        if path:
            return ("piper" if name == "piper" else "espeak", path)
    raise TTSUnavailable(
        "no TTS engine found — install piper (recommended) or espeak-ng, "
        "or pass --no-audio"
    )


def synthesize(word: str, lang: str, voice: str | None = None) -> str:
    """Produce an audio file for *word* and return its path.

    Output is cached by word and language, so regenerating a deck reuses the audio
    already on disk instead of re-synthesising every run.
    """
    engine, executable = _engine()
    key = hashlib.sha256(f"{engine}|{lang}|{voice or ''}|{word}".encode()).hexdigest()[:16]
    out = media_dir("audio") / f"{key}.wav"
    if out.is_file() and out.stat().st_size > 0:
        return str(out)

    if engine == "piper":
        if not voice:
            raise TTSUnavailable(
                "piper needs a voice model — pass one explicitly or install espeak-ng"
            )
        cmd = [executable, "--model", voice, "--output_file", str(out)]
        stdin = word.encode("utf-8")
    else:
        cmd = [executable, "-v", _ESPEAK_VOICES.get(lang, lang), "-w", str(out), word]
        stdin = None

    result = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60)
    if result.returncode != 0 or not out.is_file():
        out.unlink(missing_ok=True)
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"{engine} failed: {detail or result.returncode}")
    return str(out)


def available() -> bool:
    """Whether audio can be generated at all, for a pre-run check."""
    try:
        _engine()
    except TTSUnavailable:
        return False
    return True
