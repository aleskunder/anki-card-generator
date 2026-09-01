"""Engine selection and synthesis, with the real binaries stubbed out.

The selection logic carries the interesting bug risk: piper produces better audio
but cannot run without a voice model, so preferring it unconditionally would let a
piper install silently disable audio on a machine where espeak-ng works fine.
"""

import pytest

from anki_card_generator.media import tts
from anki_card_generator.media.tts import TTSUnavailable, _engine, available, synthesize


@pytest.fixture
def no_binaries(monkeypatch):
    """Start from a machine with no TTS installed; tests add what they need."""
    installed: dict[str, str] = {}
    monkeypatch.setattr(tts.shutil, "which", lambda name: installed.get(name))
    monkeypatch.delenv(tts.VOICE_ENV_VAR, raising=False)
    return installed


@pytest.fixture
def audio_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "media_dir", lambda kind: tmp_path)
    return tmp_path


def test_no_engine_is_reported_not_raised_as_a_crash(no_binaries):
    assert available() is False
    with pytest.raises(TTSUnavailable, match="no TTS engine found"):
        _engine()


def test_espeak_ng_is_used_when_present(no_binaries):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    engine, executable, model = _engine()
    assert (engine, executable, model) == ("espeak", "/usr/bin/espeak-ng", "")


def test_plain_espeak_is_accepted_as_a_fallback(no_binaries):
    no_binaries["espeak"] = "/usr/bin/espeak"
    assert _engine()[0] == "espeak"


def test_piper_wins_when_a_voice_model_exists(no_binaries, tmp_path):
    model = tmp_path / "de.onnx"
    model.write_bytes(b"x")
    no_binaries["piper"] = "/usr/bin/piper"
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    engine, _, resolved = _engine(str(model))
    assert engine == "piper"
    assert resolved == str(model)


def test_unconfigured_piper_does_not_shadow_espeak(no_binaries):
    # The regression this guards: preferring piper on the strength of the binary
    # alone left every card silent on a machine where espeak-ng was installed.
    no_binaries["piper"] = "/usr/bin/piper"
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    assert _engine()[0] == "espeak"


def test_piper_alone_and_unconfigured_says_what_is_missing(no_binaries):
    no_binaries["piper"] = "/usr/bin/piper"
    with pytest.raises(TTSUnavailable, match="no voice model is configured"):
        _engine()


def test_a_missing_voice_model_is_named(no_binaries, tmp_path):
    no_binaries["piper"] = "/usr/bin/piper"
    with pytest.raises(TTSUnavailable, match="voice model not found"):
        _engine(str(tmp_path / "absent.onnx"))


def test_voice_can_come_from_the_environment(no_binaries, tmp_path, monkeypatch):
    model = tmp_path / "de.onnx"
    model.write_bytes(b"x")
    no_binaries["piper"] = "/usr/bin/piper"
    monkeypatch.setenv(tts.VOICE_ENV_VAR, str(model))
    assert _engine()[0] == "piper"


# --- synthesis --------------------------------------------------------------

class FakeRun:
    """Stands in for subprocess.run, optionally writing the output file."""

    def __init__(self, returncode=0, write=True, stderr=b""):
        self.returncode = returncode
        self.write = write
        self.stderr = stderr
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.write:
            # -w / --output_file names the destination.
            for flag in ("-w", "--output_file"):
                if flag in cmd:
                    from pathlib import Path

                    Path(cmd[cmd.index(flag) + 1]).write_bytes(b"RIFFfake")
        return self


def test_espeak_is_invoked_with_the_language_voice(no_binaries, audio_dir, monkeypatch):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    run = FakeRun()
    monkeypatch.setattr(tts.subprocess, "run", run)

    path = synthesize("Haus", "de")

    cmd = run.calls[0][0]
    assert cmd[0] == "/usr/bin/espeak-ng"
    assert cmd[1:3] == ["-v", "de"]
    assert cmd[-1] == "Haus"
    assert path.endswith(".wav")


def test_english_maps_to_the_espeak_voice_name(no_binaries, audio_dir, monkeypatch):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    run = FakeRun()
    monkeypatch.setattr(tts.subprocess, "run", run)
    synthesize("house", "en")
    assert run.calls[0][0][1:3] == ["-v", "en-us"]


def test_piper_receives_the_word_on_stdin(no_binaries, audio_dir, monkeypatch, tmp_path):
    model = tmp_path / "de.onnx"
    model.write_bytes(b"x")
    no_binaries["piper"] = "/usr/bin/piper"
    run = FakeRun()
    monkeypatch.setattr(tts.subprocess, "run", run)

    synthesize("Haus", "de", str(model))

    cmd, kwargs = run.calls[0]
    assert "--model" in cmd and str(model) in cmd
    assert kwargs["input"] == b"Haus"


def test_second_call_reuses_the_cached_file(no_binaries, audio_dir, monkeypatch):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    run = FakeRun()
    monkeypatch.setattr(tts.subprocess, "run", run)

    first = synthesize("Haus", "de")
    second = synthesize("Haus", "de")

    assert first == second
    assert len(run.calls) == 1  # no re-synthesis


def test_a_failing_engine_leaves_no_empty_file(no_binaries, audio_dir, monkeypatch):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"
    monkeypatch.setattr(tts.subprocess, "run", FakeRun(returncode=1, write=False, stderr=b"boom"))

    with pytest.raises(RuntimeError, match="boom"):
        synthesize("Haus", "de")
    # A zero-byte wav would package into the deck and play as silence.
    assert list(audio_dir.glob("*.wav")) == []


def test_an_empty_output_file_counts_as_failure(no_binaries, audio_dir, monkeypatch):
    no_binaries["espeak-ng"] = "/usr/bin/espeak-ng"

    class EmptyRun(FakeRun):
        def __call__(self, cmd, **kwargs):
            super().__call__(cmd, **kwargs)
            from pathlib import Path

            Path(cmd[cmd.index("-w") + 1]).write_bytes(b"")
            return self

    monkeypatch.setattr(tts.subprocess, "run", EmptyRun())
    with pytest.raises(RuntimeError):
        synthesize("Haus", "de")
