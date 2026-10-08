"""Additive bounded, read-only N3 commands with privacy-limited failures."""

import os
import stat
import sys
from pathlib import Path

from .analytical.fingerprints import create_fingerprint_v2
from .analytical.matching import match_response_v2
from .analytical.repository import load_fingerprint_repository_v2
from .analytical.responses import derive_analytical_response
from .json_io import MAX_CONTRACT_JSON_BYTES, strict_json_loads
from .models import AnalyticalResponseV2, FeaturePolicyV1, ObservationRecordV2
from .pipeline import canonical_json


def _load_local_model(path: Path, model):
    """Read bounded regular JSON through no-follow directory/file descriptors."""
    path = path.absolute()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fd = os.open(path.anchor, directory_flags)
    try:
        for component in path.parts[1:-1]:
            child_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        file_fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
        )
    finally:
        os.close(directory_fd)
    with os.fdopen(file_fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("input must be a regular file")
        if metadata.st_size > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("input exceeds the JSON byte limit")
        payload = source.read(MAX_CONTRACT_JSON_BYTES + 1)
        if len(payload) > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("input exceeds the JSON byte limit")
    return model.model_validate(strict_json_loads(payload.decode("utf-8-sig")))


def _build_response(args, policy):
    return derive_analytical_response(
        _load_local_model(args.observation, ObservationRecordV2), policy
    )


def _load_response(args, policy):
    response = _load_local_model(args.response, AnalyticalResponseV2)
    if response.policy != policy:
        raise ValueError("explicit policy must equal the embedded policy")
    return response


def _build_fingerprint(args, policy):
    return create_fingerprint_v2(
        _load_response(args, policy),
        bottleneck_label=args.bottleneck_label,
        validation_status=args.validation_status,
    )


def _match(args, policy):
    response = _load_response(args, policy)
    repository = load_fingerprint_repository_v2(args.fingerprints)
    return match_response_v2(response, policy, repository)


def _run_v2(args):
    try:
        policy = _load_local_model(args.policy, FeaturePolicyV1)
        result = args.v2_builder(args, policy)
        output = canonical_json(result)
        if len(output.encode("utf-8")) > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("output exceeds the JSON byte limit")
    except (OSError, ValueError):
        # Keep paths, source values and Pydantic input echoes out of public errors.
        raise ValueError(f"{args.command}: invalid_input_or_result") from None
    sys.stdout.write(output)


def register_v2_commands(subparsers):
    """Register explicit v2 arguments without affecting existing command handlers."""
    response = subparsers.add_parser(
        "build-response-v2", help="derive an auditable analytical response from a v2 observation"
    )
    response.add_argument("--observation", type=Path, required=True)
    response.add_argument("--policy", type=Path, required=True)
    response.set_defaults(handler=_run_v2, v2_builder=_build_response)

    fingerprint = subparsers.add_parser(
        "build-fingerprint-v2", help="create a declared v2 reference from an analytical response"
    )
    fingerprint.add_argument("--response", type=Path, required=True)
    fingerprint.add_argument("--policy", type=Path, required=True)
    fingerprint.add_argument("--bottleneck-label", required=True)
    fingerprint.add_argument(
        "--validation-status",
        choices=["unreviewed", "software_checked", "rejected"],
        default="software_checked",
    )
    fingerprint.set_defaults(handler=_run_v2, v2_builder=_build_fingerprint)

    match = subparsers.add_parser("match-v2", help="match an analytical response to v2 references")
    match.add_argument("--response", type=Path, required=True)
    match.add_argument("--policy", type=Path, required=True)
    match.add_argument("--fingerprints", type=Path, required=True)
    match.set_defaults(handler=_run_v2, v2_builder=_match)
