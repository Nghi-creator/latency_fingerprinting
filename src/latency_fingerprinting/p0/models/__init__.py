"""P0 contract models with shared vocabulary re-exported for P0 processing."""

from ...models.common import ProvenanceKind, RestorationStatus, WindowPhase
from ...models.context import ContextKey
from .common import (
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
from .fingerprint import CompatibilityKey, Fingerprint
from .match import (
    CompatibilityResult,
    FeatureEvidence,
    MatchResult,
    MatchThresholds,
    RankedCandidate,
    ValidatedOutcome,
)
from .observation import (
    MetricAggregate,
    ObservationWindow,
    SourceArtifact,
    TimeBounds,
    ValidityState,
)
from .response import (
    FeatureDelta,
    NormalizedFeature,
    NormalizedResponse,
    ObservationRecord,
    Probe,
    ResponseDelta,
)

__all__ = [
    "ProvenanceKind",
    "RestorationStatus",
    "WindowPhase",
    "ContextKey",
    "CONTRACT_VERSION",
    "FINGERPRINT_SCHEMA_VERSION",
    "MATCH_RESULT_SCHEMA_VERSION",
    "OBSERVATION_SCHEMA_VERSION",
    "MatchDecision",
    "OutcomeResult",
    "ProbeApplicationMethod",
    "ProbeExecutionStatus",
    "UnknownReason",
    "ValidationStatus",
    "CompatibilityKey",
    "Fingerprint",
    "CompatibilityResult",
    "FeatureEvidence",
    "MatchResult",
    "MatchThresholds",
    "RankedCandidate",
    "ValidatedOutcome",
    "MetricAggregate",
    "ObservationWindow",
    "SourceArtifact",
    "TimeBounds",
    "ValidityState",
    "FeatureDelta",
    "NormalizedFeature",
    "NormalizedResponse",
    "ObservationRecord",
    "Probe",
    "ResponseDelta",
]
