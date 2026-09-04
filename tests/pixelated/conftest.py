"""Fixtures scoped to the Pixelated adapter test package."""

from __future__ import annotations

import pytest

from latency_fingerprinting.models import ContextKey

from .support import FIXTURE_ROOT


@pytest.fixture
def context() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def context_v2() -> ContextKey:
    return ContextKey.model_validate_json(
        (FIXTURE_ROOT / "context-v2.json").read_text(encoding="utf-8")
    )
