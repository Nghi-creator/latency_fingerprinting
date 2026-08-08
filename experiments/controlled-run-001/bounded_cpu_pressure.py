"""Bounded experiment-only CPU pressure for controlled run 001."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import time
from collections.abc import Sequence

MIN_DURATION_S = 30
MAX_DURATION_S = 300
MAX_WORKERS = 8


def _burn_cpu(deadline: float) -> None:
    payload = b"latency-fingerprinting-controlled-run-001"
    while time.monotonic() < deadline:
        payload = hashlib.sha256(payload).digest()


def _default_workers() -> int:
    available = os.cpu_count() or 1
    return min(MAX_WORKERS, max(1, available // 2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded local CPU pressure for controlled experiment 001."
    )
    parser.add_argument("--duration-s", type=int, default=180)
    parser.add_argument("--workers", type=int, default=_default_workers())
    parser.add_argument(
        "--confirm-experiment-only",
        action="store_true",
        help="required acknowledgement that the workload is for a monitored experiment",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.confirm_experiment_only:
        raise SystemExit("error: --confirm-experiment-only is required")
    if not MIN_DURATION_S <= args.duration_s <= MAX_DURATION_S:
        raise SystemExit(
            f"error: --duration-s must be between {MIN_DURATION_S} and {MAX_DURATION_S}"
        )
    if not 1 <= args.workers <= MAX_WORKERS:
        raise SystemExit(f"error: --workers must be between 1 and {MAX_WORKERS}")

    deadline = time.monotonic() + args.duration_s
    workers = [
        multiprocessing.Process(target=_burn_cpu, args=(deadline,), daemon=True)
        for _ in range(args.workers)
    ]
    print(
        json.dumps(
            {
                "durationS": args.duration_s,
                "event": "pressure_started",
                "workers": args.workers,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    except KeyboardInterrupt:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
        for worker in workers:
            worker.join()
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()
    print(json.dumps({"event": "pressure_stopped", "restored": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
