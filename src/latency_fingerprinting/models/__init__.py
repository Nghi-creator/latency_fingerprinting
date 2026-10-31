"""Public model facade for supported P0 and current contracts.

Imports remain available from :mod:`latency_fingerprinting.models` even though
P0 implementations live in :mod:`latency_fingerprinting.p0.models`; shared and
current model implementations remain in this package.
"""

from ..calibration import CalibrationDataset, CalibrationReport
from ..observability import (
    StageTraceRecord,
    StageTraceRecordV2,
    StageTraceSummary,
    StageTraceSummaryV2,
)
from ..p0.models.common import (
    CONTRACT_VERSION,
    FINGERPRINT_SCHEMA_VERSION,
    MATCH_RESULT_SCHEMA_VERSION,
    OBSERVATION_SCHEMA_VERSION,
    MatchDecision,
    OutcomeResult,
    ProbeApplicationMethod,
    ProbeExecutionStatus,
    UnknownReason,
    ValidationStatus,
)
from ..profile_matching import ProfileEvaluationResult, ProfileMatchPolicy, ProfileMatchResult
from ..profiles import ProfilePolicy, ProfileSnapshot
from ..scenarios import ExperimentManifest, ExperimentPhaseEvidence, ExperimentResult
from .common import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    NonNegativeFiniteFloat,
    NonNegativeInt,
    PositiveFiniteFloat,
    PositiveInt,
    ProvenanceKind,
    RestorationStatus,
    UnitInterval,
    WindowPhase,
)

__all__ = [
    "CONTRACT_VERSION",
    "OBSERVATION_SCHEMA_VERSION",
    "FINGERPRINT_SCHEMA_VERSION",
    "MATCH_RESULT_SCHEMA_VERSION",
    "NonEmptyStr",
    "FiniteFloat",
    "NonNegativeFiniteFloat",
    "PositiveFiniteFloat",
    "NonNegativeInt",
    "PositiveInt",
    "UnitInterval",
    "ContractModel",
    "WindowPhase",
    "ProvenanceKind",
    "ProbeApplicationMethod",
    "ProbeExecutionStatus",
    "RestorationStatus",
    "ValidationStatus",
    "MatchDecision",
    "UnknownReason",
    "OutcomeResult",
    "ContextKey",
    "TimeBounds",
    "MetricAggregate",
    "ValidityState",
    "SourceArtifact",
    "ObservationWindow",
    "Probe",
    "FeatureDelta",
    "ResponseDelta",
    "NormalizedFeature",
    "NormalizedResponse",
    "ObservationRecord",
    "CompatibilityKey",
    "Fingerprint",
    "RankedCandidate",
    "FeatureEvidence",
    "CompatibilityResult",
    "MatchThresholds",
    "MatchResult",
    "ValidatedOutcome",
    "METRIC_REGISTRY_SCHEMA_VERSION",
    "AggregationKind",
    "ClockBasis",
    "CounterResetPolicy",
    "MetricDefinition",
    "MetricKind",
    "MetricRegistry",
    "MetricSource",
    "MetricUnit",
    "MissingDataPolicy",
    "MeasurementSample",
    "MetricSeriesStatus",
    "MetricSeriesSummary",
    "CounterInterval",
]
from ..p0.models.fingerprint import CompatibilityKey, Fingerprint
from ..p0.models.match import (
    CompatibilityResult,
    FeatureEvidence,
    MatchResult,
    MatchThresholds,
    RankedCandidate,
    ValidatedOutcome,
)
from ..p0.models.observation import (
    MetricAggregate,
    ObservationWindow,
    SourceArtifact,
    TimeBounds,
    ValidityState,
)
from ..p0.models.response import (
    FeatureDelta,
    NormalizedFeature,
    NormalizedResponse,
    ObservationRecord,
    Probe,
    ResponseDelta,
)
from .analytical_response_v2 import (
    ANALYTICAL_RESPONSE_V2_SCHEMA_VERSION,
    AnalyticalResponseV2,
    FeatureResponseV2,
    WindowFeatureEvidenceV2,
)
from .context import ContextKey
from .feature_policy import (
    FEATURE_POLICY_SCHEMA_VERSION,
    AnalyticalDecisionPolicyV1,
    FeaturePolicyParameterV1,
    FeaturePolicyV1,
)
from .fingerprint_v2 import FINGERPRINT_V2_SCHEMA_VERSION, FingerprintV2
from .match_v2 import (
    MATCH_RESULT_V2_SCHEMA_VERSION,
    AnalyticalFeatureEvidenceV2,
    CandidateComparisonV2,
    MatchResultV2,
    RankedCandidateV2,
    RepositoryReferenceV2,
)
from .measurement import (
    METRIC_REGISTRY_SCHEMA_VERSION,
    AggregationKind,
    ClockBasis,
    CounterInterval,
    CounterResetPolicy,
    MeasurementSample,
    MetricDefinition,
    MetricKind,
    MetricRegistry,
    MetricSeriesStatus,
    MetricSeriesSummary,
    MetricSource,
    MetricUnit,
    MissingDataPolicy,
)
from .observation_pair_v2 import InterventionV2, ObservationRecordV2
from .observation_v2 import MetricMeasurement, ObservationWindowV2
from .v2_common import (
    OBSERVATION_V2_SCHEMA_VERSION,
    OBSERVATION_WINDOW_V2_SCHEMA_VERSION,
    V2_CONTRACT_VERSION,
    CaptureMethodReference,
    RegistryReference,
    SourceArtifactV2,
    V2ContextSnapshot,
)
from .v2_support import (
    MetricSupport,
    SourceSupport,
    StageTiming,
    WindowClock,
    WindowValidityV2,
)

__all__ += [
    "FINGERPRINT_V2_SCHEMA_VERSION",
    "FingerprintV2",
    "MATCH_RESULT_V2_SCHEMA_VERSION",
    "MatchResultV2",
    "CandidateComparisonV2",
    "AnalyticalFeatureEvidenceV2",
    "RankedCandidateV2",
    "RepositoryReferenceV2",
    "FEATURE_POLICY_SCHEMA_VERSION",
    "ANALYTICAL_RESPONSE_V2_SCHEMA_VERSION",
    "FeaturePolicyV1",
    "FeaturePolicyParameterV1",
    "AnalyticalDecisionPolicyV1",
    "AnalyticalResponseV2",
    "FeatureResponseV2",
    "WindowFeatureEvidenceV2",
    "V2_CONTRACT_VERSION",
    "OBSERVATION_V2_SCHEMA_VERSION",
    "OBSERVATION_WINDOW_V2_SCHEMA_VERSION",
    "ObservationWindowV2",
    "ObservationRecordV2",
    "InterventionV2",
    "MetricMeasurement",
    "V2ContextSnapshot",
    "RegistryReference",
    "CaptureMethodReference",
    "SourceArtifactV2",
    "SourceSupport",
    "MetricSupport",
    "StageTiming",
    "WindowClock",
    "WindowValidityV2",
]


__all__ += ["StageTraceRecord", "StageTraceSummary", "StageTraceRecordV2", "StageTraceSummaryV2"]


__all__ += ["ExperimentManifest", "ExperimentPhaseEvidence", "ExperimentResult"]


__all__ += ["CalibrationDataset", "CalibrationReport"]


__all__ += ["ProfilePolicy", "ProfileSnapshot"]


__all__ += ["ProfileMatchPolicy", "ProfileMatchResult", "ProfileEvaluationResult"]

_PASSIVE_ROOTS = ("PassiveGatePolicy", "PassiveBaseline", "PassiveReplay", "PassiveGateResult")
__all__ += list(_PASSIVE_ROOTS)


def __getattr__(name):
    # N9 retains N2 windows; resolve its additive exports after model bootstrap.
    if name in _PASSIVE_ROOTS:
        from .. import passive_gating

        return getattr(passive_gating, name)
    raise AttributeError(name)
