"""Openverse image lookup, with the network stubbed."""

import pytest

from anki_card_generator.media import images
from anki_card_generator.media.images import fetch_image

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 200


class FakeRaw:
    def __init__(self, data):
        self.data = data

    def read(self, size, decode_content=True):
        return self.data[:size]


class FakeResponse:
    def __init__(self, status_code=200, payload=None, data=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.raw = FakeRaw(data)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(images, "media_dir", lambda kind: tmp_path)
    return tmp_path


def wire(monkeypatch, session):
    monkeypatch.setattr(images, "_session", session)
    return session


def test_downloads_and_stores_a_result(image_dir, monkeypatch):
    session = wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": [{"url": "https://example.test/a.jpg"}]}),
        FakeResponse(200, data=JPEG),
    ))
    path = fetch_image("Haus", "house")
    assert path.endswith(".jpg")
    assert open(path, "rb").read() == JPEG
    assert session.calls[0][1]["params"]["q"] == "house"


def test_the_short_sense_is_what_gets_searched(image_dir, monkeypatch):
    # Searching the full gloss finds nothing, which is why the caller passes
    # WordEntry.primary_sense() rather than translations[0].
    session = wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": [{"url": "https://example.test/a.jpg"}]}),
        FakeResponse(200, data=JPEG),
    ))
    fetch_image("Woche", "week")
    assert session.calls[0][1]["params"]["q"] == "week"


def test_falls_back_to_the_word_without_a_query(image_dir, monkeypatch):
    session = wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": []}),
    ))
    fetch_image("Haus")
    assert session.calls[0][1]["params"]["q"] == "Haus"


def test_no_results_yields_no_image(image_dir, monkeypatch):
    wire(monkeypatch, FakeSession(FakeResponse(200, {"results": []})))
    assert fetch_image("Ratschlag", "piece of advice") == ""


def test_a_failed_search_is_not_fatal(image_dir, monkeypatch):
    wire(monkeypatch, FakeSession(FakeResponse(503)))
    assert fetch_image("Haus", "house") == ""


def test_a_failed_download_is_not_fatal(image_dir, monkeypatch):
    wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": [{"url": "https://example.test/a.jpg"}]}),
        FakeResponse(404),
    ))
    assert fetch_image("Haus", "house") == ""


def test_oversized_images_are_rejected(image_dir, monkeypatch):
    # A huge file would bloat the .apkg for no benefit on a flashcard.
    wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": [{"url": "https://example.test/a.jpg"}]}),
        FakeResponse(200, data=b"x" * (images.MAX_BYTES + 1)),
    ))
    assert fetch_image("Haus", "house") == ""
    assert list(image_dir.glob("*.jpg")) == []


def test_a_cached_image_skips_the_network(image_dir, monkeypatch):
    session = wire(monkeypatch, FakeSession(
        FakeResponse(200, {"results": [{"url": "https://example.test/a.jpg"}]}),
        FakeResponse(200, data=JPEG),
    ))
    first = fetch_image("Haus", "house")
    second = fetch_image("Haus", "house")
    assert first == second
    assert len(session.calls) == 2  # only the first lookup hit the network
