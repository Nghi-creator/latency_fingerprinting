"""Lossless offline custody of integrated game cohorts, without semantic promotion."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..analytical.policy_release import payload_hash
from ..calibration.contracts import Alias, Hash, check_identity, check_json_size, exact_string
from ..json_io import strict_json_loads
from .cadence import CadenceModel, CadenceOutcome

MAX_REPORT_BYTES = 1024 * 1024
MODES = (
    "engineering-game-disturbance",
    "engineering-game-cancel",
    "engineering-game-receiver-loss",
    "engineering-game-source-loss",
    "engineering-game-reconnect",
)


def decode_cohort(text):
    """Validate the acquisition wrapper only; nested observations remain declarations."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("integrated game report exceeds UTF-8 byte bound")
    runs = strict_json_loads(text)
    if not isinstance(runs, list) or not 1 <= len(runs) <= len(MODES):
        raise ValueError("bounded nonempty cohort required")
    for mode, run in zip(MODES, runs, strict=False):
        if (
            not isinstance(run, dict)
            or run.get("mode") != mode
            or run.get("status") not in ("passed", "failed")
            or run.get("live_authority") is not False
        ):
            raise ValueError("fixed ordered cohort prefix with no live authority required")
    return runs


class IntegratedGameRecordBody(CadenceModel):
    schema_version: Literal["integrated-game-cohort-record-v1"]
    method_release: Literal["n10-integrated-game-custody-v1"]
    assurance: Literal["operator_record_custody_only_not_independent_verification"]
    acquisition_id: Alias
    producer_revision: exact_string(r"[a-f0-9]{40}")
    raw_report: Annotated[str, Field(strict=True, max_length=MAX_REPORT_BYTES)]
    raw_report_hash: Hash
    evidence_role: Literal["engineering"]
    capability: Literal["unavailable_unqualified"]
    live_authority: Literal[False]

    @model_validator(mode="after")
    def raw_binding(self):
        decode_cohort(self.raw_report)
        digest = "sha256:" + hashlib.sha256(self.raw_report.encode("utf-8")).hexdigest()
        if self.raw_report_hash != digest:
            raise ValueError("integrated game original bytes hash mismatch")
        return self


class IntegratedGameRecord(IntegratedGameRecordBody):
    record_id: exact_string(r"integrated-game-record-[a-f0-9]{64}")
    content_hash: Hash

    @model_validator(mode="after")
    def identity(self):
        digest = check_identity(
            self, "record_id", "integrated-game-record-", ("record_id", "content_hash")
        )
        if self.content_hash != digest:
            raise ValueError("integrated game record identity mismatch")
        check_json_size(self)
        return self


def import_integrated_game_cohort(raw, *, acquisition_id, producer_revision):
    """Retain exact UTF-8 bytes, including whitespace; never run producer code."""
    if type(raw) is not bytes or len(raw) > MAX_REPORT_BYTES:
        raise ValueError("bounded UTF-8 bytes required")
    text = raw.decode("utf-8")
    body = IntegratedGameRecordBody(
        schema_version="integrated-game-cohort-record-v1",
        method_release="n10-integrated-game-custody-v1",
        assurance="operator_record_custody_only_not_independent_verification",
        acquisition_id=acquisition_id,
        producer_revision=producer_revision,
        raw_report=text,
        raw_report_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        evidence_role="engineering",
        capability="unavailable_unqualified",
        live_authority=False,
    ).model_dump(mode="json")
    digest = payload_hash(body)
    return IntegratedGameRecord(
        **body, record_id="integrated-game-record-" + digest[7:], content_hash=digest
    )


def _case_declarations(run):
    events = run.get("events")
    kind = "control_result" if run["mode"] == MODES[0] else "game_failure_result"
    matches = (
        [e for e in events if isinstance(e, dict) and e.get("kind") == kind]
        if isinstance(events, list)
        else []
    )
    outcome, ledger, state = None, None, "unavailable_missing_result"
    if len(matches) > 1:
        state = "unavailable_ambiguous_result"
    elif matches:
        event = matches[0]
        if event.get("ledger_state") in ("clean", "active", "dirty", "restored_pending_watchdog"):
            ledger = event["ledger_state"]
        if "result" not in event:
            state = "unavailable_missing_result"
        elif event["result"] is None:
            state = "unavailable_no_result"
        else:
            try:
                outcome = CadenceOutcome.model_validate(event["result"]).model_dump(mode="json")
                state = "declared_only"
            except (ValueError, TypeError):
                state = "unavailable_invalid_result"
    return {
        "mode": run["mode"],
        "acquisition_status_declared": run["status"],
        "result_state": state,
        "outcome_declared": outcome,
        "ledger_state_declared": ledger,
        "restoration_independently_verified": False,
    }


def inspect_integrated_game_record(record):
    """Expose declarations and omissions; neither success nor worker death proves restore."""
    record = IntegratedGameRecord.model_validate(record)
    runs = decode_cohort(record.raw_report)
    return {
        "record_hash": record.content_hash,
        "raw_report_hash": record.raw_report_hash,
        "cases": [_case_declarations(run) for run in runs],
        "missing_modes": list(MODES[len(runs) :]),
        "cohort_completeness": "complete" if len(runs) == len(MODES) else "partial",
        "engineering_screen": "unavailable_independent_reconstruction_required",
        "source_and_image_binding": "operator_declarations_not_authentication",
        "clock_alignment": "none",
        "issuer_restart_scope": "logical_local_owner_not_camera_process_reboot",
        "perceptual_quality": "not_evaluated",
        "audio_quality": "not_evaluated",
        "desktop_acceptance": "not_evaluated",
        "diagnostic_value": "unverified",
        "capability": "unavailable_unqualified",
        "live_authority": False,
    }
