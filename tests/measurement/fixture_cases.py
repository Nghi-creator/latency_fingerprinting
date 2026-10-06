"""Hand-reviewed N1 arithmetic cases; never derive expectations from aggregation code."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_FIXTURE_DIRECTORY = Path(__file__).resolve().parents[2] / "fixtures/measurement"
REGISTRY_VERSION = "latency-metrics-v2.0.0"
RATE = "client.frames_decoded_rate_fps"
TOTAL = "client.frames_decoded_window_total"
GAUGE = "transport.jitter_ms"


def _samples(values, times, *, state="missing") -> list[dict]:
    records = []
    for index, (value, elapsed) in enumerate(zip(values, times, strict=True)):
        records.append(
            {
                "elapsedMs": elapsed,
                "capturedAt": (
                    datetime(2026, 10, 6, tzinfo=UTC) + timedelta(milliseconds=elapsed)
                ).isoformat(),
                "value": value,
                "available": value is not None or state != "unavailable",
                "sourceRow": index + 2,
                "missingReason": "synthetic missing cell"
                if value is None and state != "rejected"
                else None,
                "rejectionReason": "synthetic malformed numeric cell"
                if value is None and state == "rejected"
                else None,
            }
        )
    return records


def _interval(first, last, start, end, duration, delta, rate) -> dict:
    # All quantities, including duration and rate, are independently supplied literals.
    return {
        "startSourceRow": first,
        "endSourceRow": last,
        "startElapsedMs": start,
        "endElapsedMs": end,
        "durationMs": duration,
        "delta": delta,
        "rate": rate,
        "wrapped": False,
    }


def _expected(
    *,
    value,
    aggregates,
    source_count,
    usable_rows,
    interval_count,
    observed,
    coverage,
    cadence,
    status,
    intervals=(),
    rate_unit=None,
    resets=(),
    gaps=(),
    missing=(),
    rejected=(),
    warnings=(),
) -> dict:
    return {
        "value": value,
        "aggregates": aggregates,
        "sourceSampleCount": source_count,
        "usableSampleCount": len(usable_rows),
        "usableSourceRows": list(usable_rows),
        "acceptedIntervalCount": interval_count,
        "observedDurationMs": observed,
        "coverage": coverage,
        "cadenceMinimumMs": cadence[0],
        "cadenceMedianMs": cadence[1],
        "cadenceMaximumMs": cadence[2],
        "status": status,
        "counterIntervals": list(intervals),
        "intervalRateUnit": rate_unit,
        "resetSourceRows": list(resets),
        "gapSourceRows": list(gaps),
        "missingReasons": list(missing),
        "rejectedReasonPrefixes": list(rejected),
        "warnings": list(warnings),
    }


def _counter_expected(*, rate, total, **evidence) -> dict:
    return {
        RATE: _expected(
            value=rate,
            aggregates={} if rate is None else {"time_weighted_rate": rate},
            rate_unit="frames/s",
            **evidence,
        ),
        TOTAL: _expected(
            value=total,
            aggregates={} if total is None else {"window_total": total},
            rate_unit="frames/s",
            **evidence,
        ),
    }


def _case(name, explanation, times, values, end, expected, *, state="missing", missing_reason=None):
    return {
        "schemaVersion": "measurement-arithmetic-fixture-v1",
        "caseId": name,
        "provenance": {
            "kind": "synthetic",
            "controlledReal": False,
            "purpose": "offline arithmetic regression; not experimental evidence",
        },
        "registryVersion": REGISTRY_VERSION,
        "explanation": explanation,
        "window": {"startMs": 0, "endMs": end},
        "sourceMissingReason": missing_reason,
        "samples": _samples(values, times, state=state),
        "expectedSummaries": expected,
    }


def fixture_cases() -> dict[str, dict]:
    """Return fresh authored inputs and expected arithmetic/audit summary projections."""
    cases = {}
    regular = _expected(
        value=20,
        aggregates={"minimum": 10, "median": 20, "nearest_rank_p95": 30, "maximum": 30},
        source_count=3,
        usable_rows=(2, 3, 4),
        interval_count=2,
        observed=2000,
        coverage=1,
        cadence=(1000, 1000, 1000),
        status="complete",
    )
    cases["gauge-regular"] = _case(
        "gauge-regular",
        (
            "Sorted 10,20,30: median 20; nearest rank ceil(.95*3)=3 gives P95 30. "
            "Two supported one-second pairs cover 2s."
        ),
        [0, 1000, 2000],
        [10, 20, 30],
        2000,
        {GAUGE: regular},
    )
    for name, state in (("gauge-missing", "missing"), ("gauge-rejected", "rejected")):
        expectation = _expected(
            value=30,
            aggregates={"minimum": 10, "median": 30, "nearest_rank_p95": 50, "maximum": 50},
            source_count=5,
            usable_rows=(2, 3, 5, 6),
            interval_count=2,
            observed=2000,
            coverage=0.5,
            cadence=(1000, 1000, 1000),
            status="incomplete",
            missing=("synthetic missing cell",) if state == "missing" else (),
            rejected=("synthetic malformed numeric cell",) if state == "rejected" else (),
            warnings=("Gauge interval coverage is incomplete; values are not extrapolated.",),
        )
        cases[name] = _case(
            name,
            (
                "Usable 10,20,40,50: median (20+40)/2=30, P95 50. Only pairs 2->3 and "
                "5->6 support 2s of a 4s window; no gap bridge."
            ),
            [0, 1000, 2000, 3000, 4000],
            [10, 20, None, 40, 50],
            4000,
            {GAUGE: expectation},
            state=state,
        )
    times = list(range(0, 10001, 1000))
    intervals = [
        _interval(index + 2, index + 3, index * 1000, (index + 1) * 1000, 1000, 60, 60)
        for index in range(10)
    ]
    cases["counter-1s-cadence"] = _case(
        "counter-1s-cadence",
        (
            "Ten accepted one-second deltas of 60: total 600; 600/10s = 60 "
            "frames/s. Same window and activity as the five-second case."
        ),
        times,
        list(range(0, 601, 60)),
        10000,
        _counter_expected(
            rate=60,
            total=600,
            source_count=11,
            usable_rows=tuple(range(2, 13)),
            interval_count=10,
            observed=10000,
            coverage=1,
            cadence=(1000, 1000, 1000),
            status="complete",
            intervals=intervals,
        ),
    )
    cases["counter-5s-equivalent-cadence"] = _case(
        "counter-5s-equivalent-cadence",
        (
            "Two five-second deltas of 300: total 600; 600/10s = 60 frames/s. "
            "Same window and activity as the one-second case."
        ),
        [0, 5000, 10000],
        [0, 300, 600],
        10000,
        _counter_expected(
            rate=60,
            total=600,
            source_count=3,
            usable_rows=(2, 3, 4),
            interval_count=2,
            observed=10000,
            coverage=1,
            cadence=(5000, 5000, 5000),
            status="complete",
            intervals=(
                _interval(2, 3, 0, 5000, 5000, 300, 60),
                _interval(3, 4, 5000, 10000, 5000, 300, 60),
            ),
        ),
    )
    cases["counter-irregular-cadence"] = _case(
        "counter-irregular-cadence",
        (
            "Deltas 100 and 100 over 1s and 4s give interval rates 100 and 25. "
            "Total 200/5s = 40 frames/s; unweighted 62.5 is wrong."
        ),
        [0, 1000, 5000],
        [0, 100, 200],
        5000,
        _counter_expected(
            rate=40,
            total=200,
            source_count=3,
            usable_rows=(2, 3, 4),
            interval_count=2,
            observed=5000,
            coverage=1,
            cadence=(1000, 2500, 4000),
            status="complete",
            intervals=(
                _interval(2, 3, 0, 1000, 1000, 100, 100),
                _interval(3, 4, 1000, 5000, 4000, 100, 25),
            ),
        ),
    )
    for name, state in (
        ("counter-gap", "missing"),
        ("counter-unavailable", "unavailable"),
        ("counter-malformed", "rejected"),
    ):
        cases[name] = _case(
            name,
            (
                "Two separate deltas of 60 support 2s of a 4s window: total 120, rate "
                "60, coverage .5. The 60-to-1000 jump is never counted."
            ),
            [0, 1000, 2000, 3000, 4000],
            [0, 60, None, 1000, 1060],
            4000,
            _counter_expected(
                rate=60,
                total=120,
                source_count=5,
                usable_rows=(2, 3, 5, 6),
                interval_count=2,
                observed=2000,
                coverage=0.5,
                cadence=(1000, 1000, 1000),
                status="incomplete",
                gaps=(4,),
                intervals=(
                    _interval(2, 3, 0, 1000, 1000, 60, 60),
                    _interval(5, 6, 3000, 4000, 1000, 60, 60),
                ),
                missing=("synthetic missing cell",) if state != "rejected" else (),
                rejected=("synthetic malformed numeric cell",) if state == "rejected" else (),
                warnings=(
                    (
                        "Counter interval coverage is incomplete; totals and rates are not "
                        "extrapolated."
                    ),
                ),
            ),
            state=state,
        )
    cases["counter-reset"] = _case(
        "counter-reset",
        (
            "Registered reject_segment excludes 60-to-5. Accepted 0-to-60 and "
            "5-to-65 give total 120 over 2s, rate 60, coverage 2/3; current row "
            "becomes a baseline."
        ),
        [0, 1000, 2000, 3000],
        [0, 60, 5, 65],
        3000,
        _counter_expected(
            rate=60,
            total=120,
            source_count=4,
            usable_rows=(2, 3, 4, 5),
            interval_count=2,
            observed=2000,
            coverage=2 / 3,
            cadence=(1000, 1000, 1000),
            status="incomplete",
            resets=(4,),
            intervals=(
                _interval(2, 3, 0, 1000, 1000, 60, 60),
                _interval(4, 5, 2000, 3000, 1000, 60, 60),
            ),
            rejected=("browser_webrtc row 4: counter decreased; reset transition rejected",),
            warnings=(
                "Counter interval coverage is incomplete; totals and rates are not extrapolated.",
            ),
        ),
    )
    cases["counter-overflow"] = _case(
        "counter-overflow",
        (
            "Each 1e308 delta/rate is finite, but two deltas total 2e308 exceeds "
            "float maximum. Reject all partial results; retain the reset row and "
            "rejection evidence."
        ),
        [0, 1000, 2000, 3000],
        [0, 1e308, 0, 1e308],
        3000,
        _counter_expected(
            rate=None,
            total=None,
            source_count=4,
            usable_rows=(2, 3, 4, 5),
            interval_count=0,
            observed=0,
            coverage=0,
            cadence=(1000, 1000, 1000),
            status="rejected",
            resets=(4,),
            rejected=(
                "browser_webrtc row 4: counter decreased; reset transition rejected",
                "counter aggregate arithmetic rejected:",
            ),
        ),
    )
    cases["counter-single"] = _case(
        "counter-single",
        (
            "One usable baseline supports no interval. Rate and total are absent, "
            "not zero; coverage is zero and status incomplete."
        ),
        [0],
        [60],
        1000,
        _counter_expected(
            rate=None,
            total=None,
            source_count=1,
            usable_rows=(2,),
            interval_count=0,
            observed=0,
            coverage=0,
            cadence=(None, None, None),
            status="incomplete",
            warnings=("No adjacent usable counter pair; interval aggregates are unavailable.",),
        ),
    )
    cases["empty-optional-source"] = _case(
        "empty-optional-source",
        (
            "An absent optional encoder source has no samples or numeric summary. "
            "Its absence reason stays explicit; nothing becomes zero."
        ),
        [],
        [],
        10000,
        {
            "encoder.queue_level_buffers": _expected(
                value=None,
                aggregates={},
                source_count=0,
                usable_rows=(),
                interval_count=0,
                observed=0,
                coverage=0,
                cadence=(None, None, None),
                status="missing",
                missing=("source has no supplied rows",),
            )
        },
        missing_reason="source has no supplied rows",
    )
    return dict(sorted(cases.items()))


def rendered_fixture_files() -> dict[Path, bytes]:
    return {
        Path(f"{name}.json"): (
            json.dumps(case, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        for name, case in fixture_cases().items()
    }


def fixture_drift(directory: Path = DEFAULT_FIXTURE_DIRECTORY) -> dict[Path, str]:
    """Read-only exact-byte checking; never creates directories or rewrites files."""
    result = {}
    for relative, expected in rendered_fixture_files().items():
        path = directory / relative
        if not path.is_file():
            result[path] = "missing"
        elif path.read_bytes() != expected:
            result[path] = "changed"
    if directory.is_dir():
        expected_names = set(rendered_fixture_files())
        for path in directory.glob("*.json"):
            if path.relative_to(directory) not in expected_names:
                result[path] = "unexpected"
    return result
