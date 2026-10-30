"""Explicit bounded local N7 CLI with protected inputs and pinned atomic output."""

import os
from pathlib import Path

from ..adapters.pixelated_bundle_io import _open_bundle
from ..analytical.policy_release import canonical_payload_bytes
from ..json_io import MAX_CONTRACT_JSON_BYTES
from ..observability.bundle import _read_file
from ..observability.output import write_trace_output
from .lifecycle import LifecycleReview
from .operations import (
    _build_profile_snapshot,
    create_profile_snapshot,
    transition_profile_snapshot,
)
from .policy import ProfilePolicy
from .snapshot import ProfileSnapshot


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino


class _Operands:
    def __init__(self):
        self.names, self.files, self.directories = set(), set(), set()

    def read(self, path, model):
        path = Path(path).absolute()
        parent = _open_bundle(path.parent)
        try:
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            try:
                self.names.add((_identity(os.fstat(parent)), path.name))
                self.files.add(_identity(os.fstat(descriptor)))
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    raw = _read_file(source, MAX_CONTRACT_JSON_BYTES)
            finally:
                os.close(descriptor)
        finally:
            os.close(parent)
        return model.model_validate_json(raw)

    def protect_target(self, parent, name, metadata):
        origin = _identity(os.fstat(parent))
        if (
            origin in self.directories
            or (origin, name) in self.names
            or (metadata is not None and _identity(metadata) in self.files)
        ):
            raise ValueError("profile output overlaps an input")


def register_profile_commands(subparsers):
    create = subparsers.add_parser(
        "create-profile-snapshot", help="create an approved-policy draft"
    )
    create.add_argument("--policy", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.set_defaults(profile_operation="create", handler=_run)

    build = subparsers.add_parser(
        "build-profiles", help="inspect N6 evidence and fit training-only profiles"
    )
    build.add_argument("--directory", type=Path, required=True)
    build.add_argument("--policy", type=Path, required=True)
    build.add_argument("--parent", type=Path)
    build.add_argument("--expected-split-id")
    build.add_argument("--expected-dataset-content-hash")
    build.add_argument("--output", type=Path, required=True)
    build.set_defaults(profile_operation="build", handler=_run)

    transition = subparsers.add_parser(
        "transition-profile-snapshot", help="withdraw or supersede a profile revision"
    )
    transition.add_argument("--snapshot", type=Path, required=True)
    transition.add_argument(
        "--operation", choices=("mark_stale", "reject", "supersede"), required=True
    )
    transition.add_argument("--reason", required=True)
    transition.add_argument("--review", type=Path, required=True)
    transition.add_argument("--replacement", type=Path)
    transition.add_argument("--output", type=Path, required=True)
    transition.set_defaults(profile_operation="transition", profile_parser=transition, handler=_run)


def _run(args):
    name = dict(
        create="create-profile-snapshot",
        build="build-profiles",
        transition="transition-profile-snapshot",
    )[args.profile_operation]
    if args.profile_operation == "transition" and (
        (args.operation == "supersede") != (args.replacement is not None)
    ):
        args.profile_parser.error("--replacement is required only for supersede")
    operands = _Operands()
    try:
        if args.profile_operation == "create":
            result = create_profile_snapshot(operands.read(args.policy, ProfilePolicy))
        elif args.profile_operation == "build":
            result, origin = _build_profile_snapshot(
                args.directory,
                operands.read(args.policy, ProfilePolicy),
                parent=operands.read(args.parent, ProfileSnapshot)
                if args.parent is not None
                else None,
                expected_split_id=args.expected_split_id,
                expected_dataset_content_hash=args.expected_dataset_content_hash,
            )
            operands.directories.add(origin)
        else:
            result = transition_profile_snapshot(
                operands.read(args.snapshot, ProfileSnapshot),
                operation=args.operation,
                reason_code=args.reason,
                review=operands.read(args.review, LifecycleReview),
                replacement=operands.read(args.replacement, ProfileSnapshot)
                if args.replacement is not None
                else None,
            )
        write_trace_output(
            args.output,
            canonical_payload_bytes(result.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError(name + ": invalid_input_or_output") from None
