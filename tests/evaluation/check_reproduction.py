"""Read-only N11 corpus reconstruction; never regenerate or bless expectations."""

import hashlib
import json
from pathlib import Path

from latency_fingerprinting.evaluation import (
    EvaluationManifest,
    EvaluationReport,
    run_evaluation,
    verify_evaluation_report,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/evaluation-v1"
RELEASE_SHA256 = "526732b389241f98d51b485acabc0f1ee1103025ef0b7fa859ea4dc4de941890"
MAX_BYTES = 4 * 1024 * 1024


def load_release(directory=FIXTURES):
    directory = Path(directory).resolve()
    files = {}
    total = 0
    for path in directory.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("invalid N11 fixture inventory")
        if path.is_file():
            total += path.stat().st_size
            if total > MAX_BYTES or len(files) >= 128:
                raise ValueError("N11 fixture budget exceeded")
            files[path.relative_to(directory).as_posix()] = path.read_bytes()
    raw = files.pop("release.json")
    if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError("N11 release pin mismatch")
    release = json.loads(raw)
    if {k: hashlib.sha256(v).hexdigest() for k, v in files.items()} != release["sha256"]:
        raise ValueError("N11 fixture inventory/hash mismatch")
    return release


def operands(case):
    """Resolve only explicit pinned files inside the fixture case."""
    paths = json.loads((case / "paths.json").read_bytes())
    result = {}
    for key, name in paths.items():
        path = case / name
        if path.resolve() != path or not path.is_relative_to(case):
            raise ValueError("invalid N11 fixture operand")
        result[key] = path
    return result


def check_case(case, expected):
    manifest = EvaluationManifest.model_validate_json((case / "manifest.json").read_bytes())
    paths = operands(case)
    execution = run_evaluation(manifest, paths)
    report = execution.report
    frozen = EvaluationReport.model_validate_json((case / "report.json").read_bytes())
    if (
        report != frozen
        or verify_evaluation_report(frozen, dict(reversed(list(paths.items())))) != frozen
    ):
        raise ValueError("N11 full-root reconstruction drift")
    actual = dict(
        planned=report.counts.planned_slots,
        held_out=report.counts.held_out_slots,
        failed=report.counts.failed_slots,
        not_started=report.counts.not_started_slots,
        profile_unknown=report.counts.profile_unknown.numerator,
        point_unknown=report.counts.point_unknown.numerator,
        rows=[
            [r.slot_id, r.diagnosis_state, r.passive_state, r.proposals, list(r.reason_codes)]
            for r in report.rows
        ],
    )
    if actual != expected:
        raise ValueError("N11 independent outcome mismatch")
    if report.empirical_acceptance != "unavailable_not_a_frozen_real_study":
        raise ValueError("N11 software corpus gained empirical acceptance")
    return execution


def check_reproduction(directory=FIXTURES):
    directory = Path(directory).resolve()
    release = load_release(directory)
    for name, expected in release["expectations"].items():
        check_case(directory / name, expected)
    return dict(status="current", cases=len(release["expectations"]), provenance="software_only")


if __name__ == "__main__":
    print(json.dumps(check_reproduction(), sort_keys=True))
