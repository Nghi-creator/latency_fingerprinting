"""Deterministic JSON Schemas for frozen P0/N1 roots and additive N2–N11 roots."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel

from .calibration import CalibrationDataset, CalibrationReport
from .evaluation import EvaluationManifest, EvaluationReport
from .live_probes import (
    CadenceProbeEvidence,
    GameBrowserProbeEvidence,
    IntegratedGameRecord,
    LiveProbeEvidence,
)
from .models import (
    AnalyticalResponseV2,
    ExperimentManifest,
    ExperimentPhaseEvidence,
    ExperimentResult,
    FeaturePolicyV1,
    Fingerprint,
    FingerprintV2,
    MatchResult,
    MatchResultV2,
    MetricRegistry,
    ObservationRecord,
    ObservationRecordV2,
    ObservationWindowV2,
    StageTraceRecord,
    StageTraceSummary,
)
from .observability.browser_v2 import StageTraceRecordV2, StageTraceSummaryV2
from .passive_gating import PassiveBaseline, PassiveGatePolicy, PassiveGateResult, PassiveReplay
from .profile_matching import ProfileEvaluationResult, ProfileMatchPolicy, ProfileMatchResult
from .profiles import ProfilePolicy, ProfileSnapshot
from .scenarios.campaign_models import CampaignIndex, CampaignPlan, CampaignReport
from .scenarios.overhead_models import OverheadEvidence, OverheadReport
from .scenarios.pacing import ExperimentManifestV2, ExperimentPhaseEvidenceV2, ExperimentResultV2

SchemaModel: TypeAlias = type[BaseModel]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIRECTORY = PROJECT_ROOT / "schemas"

SCHEMA_MODELS: Mapping[str, SchemaModel] = {
    "evaluation/n11-evaluation-manifest-v1.schema.json": EvaluationManifest,
    "evaluation/n11-evaluation-report-v1.schema.json": EvaluationReport,
    "live_probes/integrated-game-cohort-record-v1.schema.json": IntegratedGameRecord,
    "live_probes/game-browser-probe-evidence-v1.schema.json": GameBrowserProbeEvidence,
    "live_probes/cadence-probe-evidence-v1.schema.json": CadenceProbeEvidence,
    "live_probes/live-probe-evidence-v1.schema.json": LiveProbeEvidence,
    "passive_gating/passive-gate-policy-v1.schema.json": PassiveGatePolicy,
    "passive_gating/passive-baseline-v1.schema.json": PassiveBaseline,
    "passive_gating/passive-replay-v1.schema.json": PassiveReplay,
    "passive_gating/passive-gate-result-v1.schema.json": PassiveGateResult,
    "profile_matching/profile-match-policy-v1.schema.json": ProfileMatchPolicy,
    "profile_matching/profile-match-result-v1.schema.json": ProfileMatchResult,
    "profile_matching/profile-evaluation-result-v1.schema.json": ProfileEvaluationResult,
    "profiles/profile-policy-v1.schema.json": ProfilePolicy,
    "profiles/profile-snapshot-v1.schema.json": ProfileSnapshot,
    "calibration/calibration-dataset-v1.schema.json": CalibrationDataset,
    "calibration/calibration-report-v1.schema.json": CalibrationReport,
    "observability/stage-trace-record-v2.schema.json": StageTraceRecordV2,
    "observability/stage-trace-summary-v2.schema.json": StageTraceSummaryV2,
    "scenarios/n5-campaign-report-v1.schema.json": CampaignReport,
    "scenarios/n4-overhead-report-v1.schema.json": OverheadReport,
    "scenarios/n5-campaign-plan-v1.schema.json": CampaignPlan,
    "scenarios/n5-campaign-index-v1.schema.json": CampaignIndex,
    "scenarios/n4-overhead-evidence-v1.schema.json": OverheadEvidence,
    "scenarios/experiment-manifest-v2.schema.json": ExperimentManifestV2,
    "scenarios/experiment-phase-evidence-v2.schema.json": ExperimentPhaseEvidenceV2,
    "scenarios/experiment-result-v2.schema.json": ExperimentResultV2,
    "scenarios/experiment-manifest-v1.schema.json": ExperimentManifest,
    "scenarios/experiment-phase-evidence-v1.schema.json": ExperimentPhaseEvidence,
    "scenarios/experiment-result-v1.schema.json": ExperimentResult,
    "observability/stage-trace-record-v1.schema.json": StageTraceRecord,
    "observability/stage-trace-summary-v1.schema.json": StageTraceSummary,
    "p0/observation-v1.schema.json": ObservationRecord,
    "p0/fingerprint-v1.schema.json": Fingerprint,
    "p0/match-result-v1.schema.json": MatchResult,
    "measurement/metric-registry-v1.schema.json": MetricRegistry,
    "measurement/observation-window-v2.schema.json": ObservationWindowV2,
    "measurement/observation-v2.schema.json": ObservationRecordV2,
    "analytical/match-result-v2.schema.json": MatchResultV2,
    "analytical/fingerprint-v2.schema.json": FingerprintV2,
    "analytical/feature-policy-v1.schema.json": FeaturePolicyV1,
    "analytical/analytical-response-v2.schema.json": AnalyticalResponseV2,
}


def render_schema(model: SchemaModel) -> str:
    """Return one canonical, newline-terminated JSON Schema document."""

    schema = model.model_json_schema(by_alias=True)
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def rendered_schemas() -> dict[str, str]:
    """Return every public schema keyed by its path relative to the schema directory."""

    return {filename: render_schema(model) for filename, model in SCHEMA_MODELS.items()}


def _atomic_write_text(path: Path, text: str) -> None:
    """Durably write text to a sibling temporary file before atomic replacement."""

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        destination_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as temporary_file:
            temporary_file.write(text)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_path, destination_mode)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def export_schemas(output_directory: Path = DEFAULT_SCHEMA_DIRECTORY) -> tuple[Path, ...]:
    """Write all generated schemas and return their paths in stable order."""

    output_directory.mkdir(parents=True, exist_ok=True)
    schemas = rendered_schemas()
    paths = tuple(output_directory / filename for filename in sorted(schemas))
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(path, schemas[path.relative_to(output_directory).as_posix()])
    return paths


def schema_drift(output_directory: Path = DEFAULT_SCHEMA_DIRECTORY) -> dict[Path, str]:
    """Return files whose contents differ from the current Pydantic models."""

    drift: dict[Path, str] = {}
    for filename, expected in rendered_schemas().items():
        path = output_directory / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drift[path] = expected
    return drift
