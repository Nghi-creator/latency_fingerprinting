"""Pure separate v2 matching and repository-backed result verification."""

from ..models.analytical_response_v2 import AnalyticalResponseV2
from ..models.feature_policy import FeaturePolicyV1
from ..models.fingerprint_v2 import FingerprintV2
from ..models.match_v2 import MatchResultV2
from .compatibility import compatibility_rejections
from .decisions import decision_payload
from .policy_release import payload_hash
from .repository import MAX_FINGERPRINT_FILES_V2, FingerprintRepositoryV2
from .scoring import comparison_payload, shared_feature_rejections


def match_response_v2(
    response: AnalyticalResponseV2, policy: FeaturePolicyV1, repository: FingerprintRepositoryV2
) -> MatchResultV2:
    """Revalidate every input and return finite auditable similarity evidence."""
    response = AnalyticalResponseV2.model_validate(response)
    policy = FeaturePolicyV1.model_validate(policy)
    if policy != response.policy:
        raise ValueError("explicit policy must equal the query response policy")
    if len(repository.fingerprints) > MAX_FINGERPRINT_FILES_V2:
        raise ValueError("v2 repository exceeds the fingerprint limit")
    fingerprints = [FingerprintV2.model_validate(record) for record in repository.fingerprints]
    ids = [record.fingerprint_id for record in fingerprints]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate v2 fingerprint identity")
    references, rejections, comparisons = [], {}, {}
    for fingerprint in sorted(fingerprints, key=lambda record: record.fingerprint_id):
        identifier = fingerprint.fingerprint_id
        content_hash = payload_hash(fingerprint.model_dump(mode="json", by_alias=True))
        references.append({"fingerprintId": identifier, "contentHash": content_hash})
        codes = (
            ("query_invalid",)
            if not response.is_valid
            else compatibility_rejections(response, fingerprint)
        )
        if not codes:
            codes = shared_feature_rejections(response, fingerprint.feature_vector)
        if codes:
            rejections[identifier] = codes
        else:
            comparisons[identifier] = comparison_payload(
                response,
                identifier,
                content_hash,
                fingerprint.bottleneck_label,
                fingerprint.feature_vector,
            )
    digest = payload_hash(
        {
            "queryResponseId": response.response_id,
            "policyHash": policy.content_hash,
            "repositoryReferences": references,
        }
    )
    return MatchResultV2.model_validate(
        {
            "schemaVersion": "match-result-v2",
            "contractVersion": "2.0.0",
            "matchId": "match-v2-" + digest[7:],
            "queryResponse": response,
            "repositoryReferences": references,
            "candidateRejections": rejections,
            "comparisons": comparisons,
            **decision_payload(response, references, rejections, comparisons),
            "noticeCode": "software_similarity_not_causal_confidence",
        }
    )


def verify_match_repository_v2(result: MatchResultV2, repository: FingerprintRepositoryV2) -> None:
    """Check hashes, vectors, labels and rejections against full reference records."""
    result = MatchResultV2.model_validate(result)
    reproduced = match_response_v2(result.query_response, result.query_response.policy, repository)
    if result.model_dump(mode="json", by_alias=True) != reproduced.model_dump(
        mode="json", by_alias=True
    ):
        raise ValueError("match result disagrees with its full fingerprint repository")
