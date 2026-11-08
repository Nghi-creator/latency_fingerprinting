"""Synthetic end-to-end processor checks; these are not native study evidence."""

import json
from copy import deepcopy
from itertools import permutations
from pathlib import Path

import pytest

from latency_fingerprinting.analytical.policy_release import payload_hash
from latency_fingerprinting.evaluation.fixture_conditions import CONDITIONS
from tests.evaluation.test_counter_specific_candidate import point_source
from tests.test_n11_experiment_tools import tool

processor = tool("qualify_resource_pipeline")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def config_at(tmp_path):
    context = dict(
        session_id="engineering-session", session_components=1, independent_support_groups=0
    )
    config = dict(
        pipelineQualification=processor.RELEASE,
        scope="engineering_only_no_study_admission",
        retryAllowed=False,
        maximumAcquisitions=36,
        directory=str(tmp_path),
        sessionId="engineering-session",
        sessionContext=context,
        contextHash=payload_hash(context),
        sourceManifestHash="sha256:" + "b" * 64,
        imageSha256="sha256:" + "a" * 64,
        excludedCaseIds=["n11-raw-eng-old"],
        cases=[],
    )
    orders = list(permutations(CONDITIONS))
    orders += orders[::-1]
    for index, order in enumerate(orders):
        for ordinal, condition in enumerate(order):
            number = index * 3 + ordinal + 1
            identifier = f"n11-raw-eng-processor-{number}"
            plan = tmp_path / "plans" / f"{identifier}.json"
            write(
                plan,
                dict(
                    acquisition_id=identifier,
                    condition={"name": condition},
                    image=config["imageSha256"],
                    source_manifest_hash=config["sourceManifestHash"],
                ),
            )
            config["cases"].append(
                dict(
                    id=identifier,
                    condition=condition,
                    block_id=f"block-{index}",
                    role="fitting" if index < 6 else "query",
                    plan=str(plan),
                    planSha256=processor.sha(plan),
                    output=str(tmp_path / "cases" / str(number)),
                )
            )
    path = tmp_path / "config.json"
    write(path, config)
    return config, path


def populate_training(config):
    for slot in config["cases"][:18]:
        directory = Path(slot["output"])
        directory.mkdir(parents=True)
        value = point_source(slot["id"], CONDITIONS.index(slot["condition"]))
        (directory / "acquisition.json").write_text(value["acquisition_json"])
        write(directory / "resource-observation.json", value["resource_artifact"])
        (directory / "plan.json").write_bytes(Path(slot["plan"]).read_bytes())
        write(
            directory / "control-receipt.json",
            dict(
                acquisition_id=slot["id"],
                condition=slot["condition"],
                condition_integrity="verified_declared_internal_evidence",
                resource_integrity="verified_declared_internal_evidence",
            ),
        )
        write(
            directory / "engineering-verification.stdout",
            dict(
                acquisition_id=slot["id"],
                source_manifest=config["sourceManifestHash"],
                native_sha256=processor.sha(directory / "acquisition.json"),
                sdk_cli_equal_phases=3,
                pipeline_projection=processor.project_case(directory),
            ),
        )


def test_fit_replays_exactly_without_reading_future_queries_and_score_needs_no_query_truth(
    tmp_path,
):
    config, path = config_at(tmp_path)
    populate_training(config)
    fitted = processor.fit_config(path)
    assert fitted["calibration"]["state"] == "candidate_calibration_available"
    assert fitted["study_admission"] is False
    for slot in config["cases"][18:]:
        directory = Path(slot["output"])
        directory.mkdir(parents=True)
        (directory / "control-receipt.json").write_text("poison future truth")
        (directory / "plan.json").write_text("poison future plan")
    assert processor.fit_config(path) == fitted
    value = point_source("fresh-engineering-query", 1)
    query = Path(config["cases"][18]["output"])
    (query / "acquisition.json").write_text(value["acquisition_json"])
    write(query / "resource-observation.json", value["resource_artifact"])
    result = processor.score_case(fitted, query, block="block-6", session="engineering-session")
    assert result["predicted_condition"] == CONDITIONS[1]
    changed = deepcopy(fitted)
    changed["calibration"]["thresholds"] = None
    with pytest.raises(ValueError, match="changed engineering calibration"):
        processor.score_case(changed, query, block="block-6", session="engineering-session")


@pytest.mark.parametrize(
    "kind", ["scope", "cap", "roles", "order", "duplicate", "excluded", "context", "escape"]
)
def test_invalid_qualification_declarations_rejected(tmp_path, kind):
    config, _ = config_at(tmp_path)
    if kind == "scope":
        config["scope"] = "study"
    elif kind == "cap":
        config["maximumAcquisitions"] = 37
    elif kind == "roles":
        config["cases"][18]["role"] = "fitting"
    elif kind == "order":
        config["cases"][0]["condition"] = config["cases"][1]["condition"]
    elif kind == "duplicate":
        config["cases"][1]["id"] = config["cases"][0]["id"]
    elif kind == "excluded":
        config["excludedCaseIds"] = [config["cases"][0]["id"]]
    elif kind == "context":
        config["sessionContext"]["session_components"] = 2
    else:
        config["cases"][0]["output"] = str(tmp_path / "foreign-case")
    with pytest.raises(ValueError):
        processor.inspect_config(config)


@pytest.mark.parametrize(
    "name",
    ["plan.json", "control-receipt.json", "engineering-verification.stdout", "acquisition.json"],
)
def test_changed_training_witness_cannot_fit(tmp_path, name):
    config, path = config_at(tmp_path)
    populate_training(config)
    item = Path(config["cases"][0]["output"]) / name
    if name == "acquisition.json":
        item.write_text(item.read_text() + " ")
    else:
        value = json.loads(item.read_text())
        if name == "plan.json":
            value["condition"]["name"] = CONDITIONS[1]
        elif name == "control-receipt.json":
            value["resource_integrity"] = "unverified"
        else:
            value["sdk_cli_equal_phases"] = 2
        write(item, value)
    with pytest.raises(ValueError):
        processor.fit_config(path)
