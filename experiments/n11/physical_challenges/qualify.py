"""Read-only original-file qualification and descriptive projection; never collect or fit."""

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from latency_fingerprinting.evaluation.projections.physical_challenge_projection import (
    project_physical_challenge,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_delivery import (
    inspect_challenge_delivery,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_links import (
    inspect_challenge_links,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_measurements import (
    inspect_challenge_measurements,
)
from latency_fingerprinting.evaluation.protocols.physical_challenge_raw import (
    inspect_challenge_raw_export,
)
from latency_fingerprinting.json_io import strict_json_loads

OPERANDS = {
    "acquisition.json": 4 * 1024 * 1024,
    "plan.json": 1024 * 1024,
    "raw-export.json": 4 * 1024 * 1024,
    "exclusions.json": 1024 * 1024,
}
REPLAY = "scripts/research/n11/qualification/replayPhysicalChallenge.mjs"
REQUIRED = (
    REPLAY,
    "scripts/research/n10/shared/researchSources.mjs",
    "scripts/research/n11/acquisition/rawObservation.mjs",
    "scripts/research/n11/receipts/physicalChallengeMedia.mjs",
    "scripts/research/n11/receipts/pairedObservationReceipt.mjs",
    "scripts/research/n11/receipts/observedPhase.mjs",
    "scripts/research/n11/browser/challengePhaseCustody.mjs",
)


def read_regular(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("regular qualification file required")
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("qualification file exceeds bound")
        return raw


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def source_path(root, name):
    if root.is_symlink():
        raise ValueError("symlink source root is not replayable")
    parts = PurePosixPath(name)
    if parts.is_absolute() or str(parts) != name or ".." in parts.parts or "\\" in name:
        raise ValueError("noncanonical source path")
    target = root.joinpath(*parts.parts)
    for parent in (target, *target.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("symlink source is not replayable")
    return target


def verify_sources(case, producer, sources):
    if not all(name in sources for name in REQUIRED) or len(sources) > 10000:
        raise ValueError("complete producer replay source pins required")
    total = 0
    for name, expected in sources.items():
        if not isinstance(name, str) or not name:
            raise ValueError("invalid source path")
        frozen = read_regular(source_path(case / "sources", name), 16 * 1024 * 1024)
        if name.startswith("web/src/"):
            current = source_path(producer / "apps/web/src", name[8:])
        else:
            current = source_path(producer / "engine/runtime", name)
        actual = read_regular(current, 16 * 1024 * 1024)
        total += len(frozen) + len(actual)
        if (
            total > 256 * 1024 * 1024
            or hashlib.sha256(frozen).hexdigest() != expected
            or hashlib.sha256(actual).hexdigest() != expected
        ):
            raise ValueError("changed frozen/current producer source")


def qualify_case(case_directory, producer):
    """Re-run each component from cached original operands; reject failed overall cases."""
    case, producer = Path(case_directory).resolve(), Path(producer).resolve()
    if os.path.lexists(case / "failure.json"):
        raise ValueError("failed overall case cannot be qualified")
    operands = {name: read_regular(case / name, limit) for name, limit in OPERANDS.items()}
    a, p, e, x = (operands[n] for n in OPERANDS)
    custody = inspect_challenge_raw_export(a, p, e, x)
    plan = strict_json_loads(p.decode())
    verify_sources(case, producer, plan["source_sha256"])
    links = inspect_challenge_links(a)
    delivery = inspect_challenge_delivery(a)
    measurements = inspect_challenge_measurements(a)
    projection = project_physical_challenge(a)
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js required for producer media replay")
    # Node reads exactly the same originals as Python, not changing live case files.
    with tempfile.TemporaryDirectory(prefix="n11-challenge-replay-") as directory:
        directory = Path(directory)
        for name in ("acquisition.json", "plan.json"):
            (directory / name).write_bytes(operands[name])
        result = subprocess.run(  # noqa: S603
            [
                node,
                str(producer / "engine/runtime" / REPLAY),
                str(directory / "acquisition.json"),
                str(directory / "plan.json"),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        if len(result.stdout) > 4 * 1024 * 1024:
            raise ValueError("oversized producer replay report")
        replay = strict_json_loads(result.stdout.decode())
    if (
        replay.get("method") != "n11-physical-challenge-producer-replay-v1"
        or replay.get("source_manifest_replayed") is not True
        or replay.get("native_software_identity_replayed") is not True
        or replay["media"]["method"] != "n11-physical-challenge-media-inspection-v2"
        or replay["media"]["acquisition_sha256"] != sha(a)
    ):
        raise ValueError("producer replay is not bound to original acquisition")
    verify_sources(case, producer, plan["source_sha256"])
    if os.path.lexists(case / "failure.json") or any(
        read_regular(case / name, limit) != operands[name] for name, limit in OPERANDS.items()
    ):
        raise ValueError("case changed during qualification")
    return dict(
        method="n11-physical-challenge-joint-qualification-v1",
        state="source_components_consistent",
        original_sha256={n: sha(b) for n, b in operands.items()},
        source_components_replayed=True,
        custody=custody,
        links=links,
        delivery=delivery,
        measurements=measurements,
        producer_replay=replay,
        projection=projection,
        native_qualification=False,
        resource_dose_verified=False,
        n2_pair_admitted=False,
        scoring_authority=False,
        empirical_acceptance=False,
        acquisition_authority=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-directory", type=Path, required=True)
    parser.add_argument("--producer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    status = 0
    try:
        report = qualify_case(args.case_directory, args.producer)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report = dict(
            method="n11-physical-challenge-joint-qualification-v1",
            state="qualification_failed",
            reason=type(error).__name__,
            detail=str(error).split("\n")[0][:512],
            native_qualification=False,
            empirical_acceptance=False,
        )
        status = 1
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
