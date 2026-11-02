"""Independent N11 wheel/CLI checks outside the checkout; no real study data."""

import json
import shutil

from tests.evaluation.support import base, canonical, slot
from tests.evaluation.test_windows import context
from tests.pixelated.support import VALID_V2_BUNDLE, write_tar


def check_evaluation(directory, invoke_installed):
    from latency_fingerprinting.evaluation import seal_manifest
    from tests.evaluation.check_reproduction import FIXTURES, load_release, operands

    release = load_release()
    corpus = directory / "n11-frozen"
    shutil.copytree(FIXTURES, corpus)
    for name in release["expectations"]:
        case = corpus / name
        pathmap = directory / (name + "-operands.json")
        pathmap.write_bytes(canonical(dict(paths={k: str(v) for k, v in operands(case).items()})))
        result_path = directory / (name + "-report.json")
        code, stdout, stderr = invoke_installed(
            [
                "evaluate-study",
                "--manifest",
                case / "manifest.json",
                "--operands",
                pathmap,
                "--verify-report",
                case / "report.json",
                "--output",
                result_path,
            ]
        )
        if (
            code
            or stdout
            or stderr
            or result_path.read_bytes() != (case / "report.json").read_bytes()
        ):
            raise ValueError("installed frozen N11 corpus drift")

    payload, paths = base(directory)
    payload["slots"] = [slot("failed", state="failed"), slot("unstarted", state="not_started")]
    manifest = directory / "study-manifest.json"
    manifest.write_bytes(canonical(seal_manifest(payload).model_dump(mode="json")))
    operands = directory / "study-paths.json"
    operands.write_bytes(canonical(dict(paths={k: str(v) for k, v in paths.items()})))
    output = directory / "study-report.json"
    args = ["evaluate-study", "--manifest", manifest, "--operands", operands, "--output", output]
    code, stdout, stderr = invoke_installed(args)
    if code or stdout or stderr:
        raise ValueError("installed N11 evaluation failed")
    result = json.loads(output.read_bytes())
    if result["counts"]["held_out_slots"] != 2 or result["counts"]["profile_unknown"]["value"] != 1:
        raise ValueError("installed N11 missing planned denominator")
    code, stdout, stderr = invoke_installed(["validate", output])
    if code or stderr or json.loads(stdout) != result:
        raise ValueError("installed N11 report validation failed")
    verified = directory / "verified-study.json"
    code, stdout, stderr = invoke_installed([*args[:-1], verified, "--verify-report", output])
    if code or stdout or stderr or verified.read_bytes() != output.read_bytes():
        raise ValueError("installed N11 report reconstruction failed")
    archive = directory / "window-source.tar"
    write_tar(VALID_V2_BUNDLE, archive)
    ctx = directory / "window-context.json"
    ctx.write_bytes(canonical(context().model_dump(mode="json", by_alias=True)))
    window = directory / "windowed.json"
    args = [
        "ingest-pixelated-window",
        "--bundle",
        archive,
        "--context",
        ctx,
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
        "--start-ms",
        "0",
        "--end-ms",
        "5000",
        "--output",
        window,
    ]
    code, stdout, stderr = invoke_installed(args)
    if code or stdout or stderr:
        raise ValueError("installed N11 window extraction failed")
    body = json.loads(window.read_bytes())
    if (
        body["captureMethod"]["methodVersion"] != "1.1.0"
        or body["measurements"]["client.frames_decoded_rate_fps"]["summary"]["aggregates"][
            "time_weighted_rate"
        ]
        != 60
    ):
        raise ValueError("installed N11 raw window arithmetic changed")
    retained = archive.read_bytes()
    code, stdout, stderr = invoke_installed([*args[:-1], archive])
    if (
        code != 1
        or stdout
        or stderr != b"error: ingest-pixelated-window: invalid_input_or_output\n"
        or archive.read_bytes() != retained
    ):
        raise ValueError("installed N11 raw input overwrite protection failed")
