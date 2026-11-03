"""Installed source-local SDK/CLI, independent arithmetic and fixed output failures."""

import json

from tests.evaluation.support import canonical
from tests.evaluation.test_source_local import local_context, source
from tests.pixelated.support import write_tar


def check_source_local(directory, invoke_installed):
    case = directory / "source-local"
    case.mkdir()
    bundle = source(case)
    archive = case / "raw.tar"
    write_tar(bundle, archive)
    context = case / "context.json"
    context.write_bytes(canonical(local_context().model_dump(mode="json")))
    output = case / "window.json"
    arguments = [
        "ingest-pixelated-source-local",
        "--bundle",
        archive,
        "--context",
        context,
        "--phase",
        "degraded",
        "--comparison-case-id",
        "controlled-case-001",
        "--output",
    ]
    code, stdout, stderr = invoke_installed([*arguments, output])
    if code or stdout or stderr:
        raise ValueError("installed source-local adoption failed")
    body = json.loads(output.read_bytes())
    metric = body["measurements"]["host.camera_cpu_percent"]["summary"]
    if (
        body["captureMethod"]["methodVersion"] != "1.2.0"
        or [metric["windowStartMs"], metric["windowEndMs"]] != [500, 5500]
        or metric["coverage"] != 1
        or metric["aggregates"]["median"] != 32.5
    ):
        raise ValueError("installed source-local arithmetic/bounds drift")
    code, stdout, stderr = invoke_installed(["validate", output])
    if code or stderr or json.loads(stdout) != body:
        raise ValueError("installed source-local root validation failed")
    original = archive.read_bytes()
    code, stdout, stderr = invoke_installed([*arguments, archive])
    if (
        code != 1
        or stdout
        or stderr != b"error: ingest-pixelated-source-local: invalid_input_or_output\n"
        or archive.read_bytes() != original
    ):
        raise ValueError("installed source-local input protection failed")
