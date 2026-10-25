"""Protected offline game/browser import; no native runtime or network access."""

from pathlib import Path

from ..analytical.policy_release import canonical_payload_bytes
from ..observability.output import write_trace_output
from ..profiles.commands import _Operands
from .game_browser import _RawGameBrowserAcquisition, import_game_browser_acquisition


def register_game_browser_command(subparsers):
    parser = subparsers.add_parser(
        "import-game-browser-report", help="seal contained game/browser engineering observations"
    )
    for name in ("report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("acquisition-id", "producer-revision"):
        parser.add_argument("--" + name, required=True)
    parser.set_defaults(handler=_run)


def _run(args):
    operands = _Operands()
    try:
        acquisition = operands.read(args.report, _RawGameBrowserAcquisition)
        evidence = import_game_browser_acquisition(
            acquisition,
            acquisition_id=args.acquisition_id,
            producer_revision=args.producer_revision,
        )
        write_trace_output(
            args.output,
            canonical_payload_bytes(evidence.model_dump(mode="json")),
            target_guard=operands.protect_target,
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise ValueError("import-game-browser-report: invalid_input_or_output") from None
