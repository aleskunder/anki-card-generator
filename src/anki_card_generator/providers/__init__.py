"""Provider registry.

Backends are imported lazily so that a missing optional dependency or an unset API
key only ever breaks the provider that actually needs it -- ``--provider stub`` must
keep working on a bare checkout.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import Provider, ProviderError

# name -> zero-arg factory, resolved on first use
_REGISTRY: dict[str, Callable[..., Provider]] = {}


def _register(name: str, loader: Callable[..., Provider]) -> None:
    _REGISTRY[name] = loader


def _load_stub(**kwargs: Any) -> Provider:
    from .stub import StubProvider

    return StubProvider()


def _load_llm(**kwargs: Any) -> Provider:
    from .llm import LLMProvider

    return LLMProvider(**kwargs)


def _load_wiktionary(**kwargs: Any) -> Provider:
    from .wiktionary import WiktionaryProvider

    return WiktionaryProvider()


def _load_deepl(**kwargs: Any) -> Provider:
    from .deepl import DeepLProvider

    return DeepLProvider()


def _load_libre(**kwargs: Any) -> Provider:
    from .libre import LibreTranslateProvider

    return LibreTranslateProvider()


_register("stub", _load_stub)
_register("llm", _load_llm)
_register("wiktionary", _load_wiktionary)
_register("deepl", _load_deepl)
_register("libre", _load_libre)

PROVIDER_NAMES = tuple(_REGISTRY)
DEFAULT_PROVIDER = "llm"


def get_provider(name: str, **kwargs: Any) -> Provider:
    """Instantiate the provider registered under *name*.

    Extra keyword arguments are passed to the backend, which ignores the ones it
    does not care about (only the LLM provider takes ``model`` and ``effort``).
    """
    try:
        loader = _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown provider {name!r}. Available: {known}") from None
    return loader(**kwargs)


__all__ = [
    "DEFAULT_PROVIDER",
    "PROVIDER_NAMES",
    "Provider",
    "ProviderError",
    "get_provider",
]
