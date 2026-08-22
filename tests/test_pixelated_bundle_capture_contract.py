"""Regression tests for real-capture Pixelated bundle boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from latency_fingerprinting.adapters.pixelated_bundle import PixelatedBundleError
from latency_fingerprinting.models import ContextKey

from .pixelated_bundle_support import copy_v2_bundle as copy_bundle
from .pixelated_bundle_support import ingest


def test_v2_event_details_reject_private_peer_identity(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    events_path = bundle / "stream-events.csv"
    events_path.write_text(
        events_path.read_text(encoding="utf-8").replace(
            "first_non_black_frame,\n",
            'first_non_black_frame,"{""signaling"":{""peerId"":""private-peer""}}"\n',
        ),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="private peer identity"):
        ingest(bundle, context_v2)


def test_preliminary_session_events_may_roll_into_final_session(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    events_path = bundle / "stream-events.csv"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    lines.insert(
        1,
        "2026-08-10T02:03:03.000Z,0,pixelated-sanitized-run-v2-001,"
        "preliminary-session,backend_session_requested,",
    )
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert ingest(bundle, context_v2).validity.is_valid


def test_event_session_cannot_switch_after_final_session_is_observed(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    events_path = bundle / "stream-events.csv"
    with events_path.open("a", encoding="utf-8") as events_file:
        events_file.write(
            "2026-08-10T02:03:05.000Z,1000,pixelated-sanitized-run-v2-001,"
            "other-session,retry_started,\n"
        )

    with pytest.raises(PixelatedBundleError, match="switches away"):
        ingest(bundle, context_v2)


def test_formal_capture_events_must_use_final_session(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    events_path = bundle / "stream-events.csv"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    lines.insert(
        1,
        "2026-08-10T02:03:03.000Z,0,pixelated-sanitized-run-v2-001,"
        "preliminary-session,research_recording_started,",
    )
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(PixelatedBundleError, match="formal capture event"):
        ingest(bundle, context_v2)


def test_packet_loss_first_sample_is_a_zero_delta_baseline(
    tmp_path: Path,
    context_v2: ContextKey,
) -> None:
    bundle = copy_bundle(tmp_path)
    telemetry_path = bundle / "stream-telemetry.csv"
    telemetry_path.write_text(
        telemetry_path.read_text(encoding="utf-8").replace(
            ",0,0,8,connected",
            ",5,5,8,connected",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(PixelatedBundleError, match="packets_lost_delta disagrees"):
        ingest(bundle, context_v2)
