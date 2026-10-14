"""Bounded N5 vocabulary; reuse strict N4 primitives without changing N4."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator

from ..observability.contracts import TraceModel, alias

SECOND = 1_000_000_000
PHASES = ("warmup", "healthy", "degraded", "probe", "recovery", "cooldown")
MEASURED = PHASES[1:5]
Phase = Literal[*PHASES]
Release = Literal["n5-single-cause-v1"]
AdapterReason = Literal[
    "adapter_not_implemented",
    "runtime_unavailable",
    "permission_denied",
    "clock_unavailable",
    "source_unavailable",
]
ExperimentID, NodeID, WorkloadID = alias("experiment"), alias("node"), alias("workload")
ActionID, ArtifactID = alias("action"), alias("artifact")
Workers = Annotated[int, Field(strict=True, ge=0, le=8)]
Duration = Annotated[int, Field(strict=True, ge=SECOND, le=300 * SECOND)]
Version = Annotated[
    str,
    Field(strict=True, pattern=r"^(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})$"),
]


def strict_integer(value):
    if type(value) is not int:
        raise ValueError("configuration requires a strict integer")
    return value


Width = Annotated[Literal[1280], BeforeValidator(strict_integer)]
Height = Annotated[Literal[720], BeforeValidator(strict_integer)]
FPS = Annotated[Literal[30], BeforeValidator(strict_integer)]


class ExperimentModel(TraceModel):
    @field_validator("*", mode="before")
    @classmethod
    def bound_experiment_containers(cls, value, info):
        caps = {"phases": 6, "actions": 6, "artifacts": 18, "intervals": 1200}
        if info.field_name in caps and (
            not isinstance(value, (list, tuple)) or len(value) > caps[info.field_name]
        ):
            raise ValueError("experiment collection must be a bounded list or tuple")
        return value


def ordered_times(start, end):
    if end is not None and (start is None or end < start):
        raise ValueError("timestamps must be ordered and retain their start")


def phase_prefix(phases):
    if tuple(p.phase for p in phases) != PHASES[: len(phases)]:
        raise ValueError("phases must follow the fixed prefix order")
