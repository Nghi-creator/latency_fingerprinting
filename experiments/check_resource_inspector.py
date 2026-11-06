"""Synthetic producer resource artifact replay and tamper rejection; no acquisition."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from verify_native_exports import replay_inspector


def check_resource_inspector(tmp_path, producer):
    runtime = producer / "engine/runtime"
    script = """
import fs from 'node:fs';import {createHash} from 'node:crypto';
const {fixture}=await import(process.argv[1]);
const {inspectResourceConditionAcquisition,resourceObservationArtifact}=
 await import(process.argv[2]);
const {resourceDeclaration,resourceMode}=
 await import(new URL('./resourceProtocol.mjs',process.argv[2]));
const d=process.argv[3],raw=fixture(),condition='no_injected_fault';
const bytes=JSON.stringify(raw,null,2)+'\\n';
const receipt=inspectResourceConditionAcquisition(raw,{condition});
fs.writeFileSync(d+'/plan.json',JSON.stringify({schema_version:'n11-contained-resource-condition-plan-v1',mode:resourceMode(condition),resources:resourceDeclaration(),condition:{name:condition}}));
fs.writeFileSync(d+'/acquisition.json',bytes);
fs.writeFileSync(d+'/control-receipt.json',JSON.stringify(receipt));
fs.writeFileSync(d+'/resource-observation.json',JSON.stringify(resourceObservationArtifact(receipt,'sha256:'+createHash('sha256').update(bytes).digest('hex'))));
"""
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node.js executable required")
    subprocess.run(  # noqa: S603
        [
            node,
            "--input-type=module",
            "-e",
            script,
            (runtime / "scripts/research/n10/resourceReceiptFixture.mjs").as_uri(),
            (runtime / "scripts/research/n11/resourceReceipt.mjs").as_uri(),
            str(tmp_path),
        ],
        check=True,
        timeout=30,
    )
    replay_inspector(tmp_path, producer=producer, resource=True)
    artifact = tmp_path / "resource-observation.json"
    original = artifact.read_text()
    data = json.loads(original)
    data["clock_id"] = "changed"
    artifact.write_text(json.dumps(data))
    try:
        replay_inspector(tmp_path, producer=producer, resource=True)
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("tampered resource/source bytes were accepted")
    artifact.write_text(original)
    plan_file = tmp_path / "plan.json"
    original_plan = plan_file.read_text()
    plan = json.loads(original_plan)
    plan["resources"]["maximum_samples"] += 1
    plan_file.write_text(json.dumps(plan))
    try:
        replay_inspector(tmp_path, producer=producer, resource=True)
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("changed resource plan declaration was accepted")
    plan_file.write_text(original_plan)
    raw = tmp_path / "acquisition.json"
    raw.write_text(raw.read_text() + " ")
    try:
        replay_inspector(tmp_path, producer=producer, resource=True)
    except subprocess.CalledProcessError:
        pass
    else:
        raise ValueError("tampered resource/source bytes were accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="resource-inspector-replay-") as directory:
        check_resource_inspector(Path(directory).resolve(), args.producer.resolve())
    print(
        json.dumps(
            dict(
                scope="synthetic_cross_repo_resource_replay",
                valid_replay=True,
                auxiliary_tamper_rejected=True,
                plan_declaration_tamper_rejected=True,
                raw_byte_tamper_rejected=True,
                acquisitions=0,
            )
        )
    )


if __name__ == "__main__":
    main()
