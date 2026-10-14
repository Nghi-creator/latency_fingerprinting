"""Read-only N5 release pins and independent synthetic experiment expectations."""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from latency_fingerprinting.cli import main as cli_main
from latency_fingerprinting.pipeline import canonical_json
from latency_fingerprinting.scenarios import inspect_experiment_bundle
from latency_fingerprinting.scenarios.bundle_io import read_members

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures/scenarios"
CASES = (
    "healthy",
    "host",
    "boundary",
    "failed-pressure",
    "cancelled",
    "unsupported",
    "missing-trace",
    "unknown-cleanup",
)
# Release 1.0.0. No update mode; changed expectations require explicit review.
EXPECTED_SHA256 = {
    "boundary/artifact-1.json": (
        "35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"
    ),
    "boundary/artifact-10.json": (
        "5e3758981784b47ddefd3973cc060083b6edf2a92eebcdaca25c98f8be469a66"
    ),
    "boundary/artifact-2.json": (
        "b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"
    ),
    "boundary/artifact-3.json": (
        "3859cd91f279111121c53ed55f4d110fe6114d3c538b52036cbbd77951516b6a"
    ),
    "boundary/artifact-4.json": (
        "51d4671b1ad032428ad91e5ba80fedc2c440cd114b4d9e56a1ccd7ceafd95f1e"
    ),
    "boundary/artifact-5.json": (
        "71f3e8378d2ca8115e78d7acbb776d37f4804cafd64fbb80c6e831a2145ecf88"
    ),
    "boundary/artifact-6.json": (
        "c679a2e3a246a3431d6abc62eb25ced11ede1b3736cd05151a8d8fcbf9758fee"
    ),
    "boundary/artifact-7.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "boundary/artifact-8.json": (
        "5e3758981784b47ddefd3973cc060083b6edf2a92eebcdaca25c98f8be469a66"
    ),
    "boundary/artifact-9.json": (
        "0cb8528d84225e78cd37015b1394083cb508916f3008c1d57826ab452e50be82"
    ),
    "boundary/expected.json": ("5d98c32e5a02f6969f83a9e7950b9f14e94970a034b991a34ab253c12214036b"),
    "boundary/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "boundary/experiment-result.json": (
        "8daa606b0b8a476beb51bad822acb269dd6d4ebbec533b5a71dbc3640ee84106"
    ),
    "cancelled/artifact-1.json": (
        "35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"
    ),
    "cancelled/artifact-2.json": (
        "b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"
    ),
    "cancelled/artifact-3.json": (
        "e99aa2771670b860d0fe983b239b0f74ccf0111eeb217c91edd6ded04f1df143"
    ),
    "cancelled/artifact-4.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "cancelled/artifact-5.json": (
        "332aeafb38d02b00bf9ce0fbdca38868007dfa5b9c27bad7afcd24fb7002f71a"
    ),
    "cancelled/expected.json": ("ecbc4f80e17a7d70ea8c58f37058618122c4ac5109c7768faa09207fea8fc880"),
    "cancelled/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "cancelled/experiment-result.json": (
        "d7216bca60f4e725fcd317b8a94a8a8730de32838365a74ab8fca8c262b07a4f"
    ),
    "failed-pressure/artifact-1.json": (
        "35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"
    ),
    "failed-pressure/artifact-10.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "failed-pressure/artifact-2.json": (
        "b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"
    ),
    "failed-pressure/artifact-3.json": (
        "9c877b2946d2c7c75f5fefe242117be11bda12f89093929d1e0ecdea1af8b1d6"
    ),
    "failed-pressure/artifact-4.json": (
        "f7deb226c9efa6a4401e4e814a8abef9244175887dd446a6aed7434332104f11"
    ),
    "failed-pressure/artifact-5.json": (
        "e94a346ff3b67ac20aa4d5909e3989a72037d1599881fdc0926067f57ac5b3fd"
    ),
    "failed-pressure/artifact-6.json": (
        "dc09f31939961dba34917d7a5deb6ca7f357794c5d5b6ca1d323374d73f03ab6"
    ),
    "failed-pressure/artifact-7.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "failed-pressure/artifact-8.json": (
        "0cb8528d84225e78cd37015b1394083cb508916f3008c1d57826ab452e50be82"
    ),
    "failed-pressure/artifact-9.json": (
        "0cb8528d84225e78cd37015b1394083cb508916f3008c1d57826ab452e50be82"
    ),
    "failed-pressure/expected.json": (
        "e10407dc28c33c84537e11e872f768dbe7a05ae05b5fc379a0e709631e86c687"
    ),
    "failed-pressure/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "failed-pressure/experiment-result.json": (
        "7870549c897840d8f7b2dea52379e3f2bceb36fba5e8f7d425df0a64486d310a"
    ),
    "healthy/artifact-1.json": ("78f7b95dbf34810e8c233084e119443cb876dfa1f08e95f2a524aa6dd13a98d2"),
    "healthy/artifact-10.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "healthy/artifact-2.json": ("63a7ac91438f355792500ca35ba47f008f148af1c796389278e8da285a91b466"),
    "healthy/artifact-3.json": ("68f985451a14e02b1f61adef9834951f062910697d9736539d12e698764f8a9e"),
    "healthy/artifact-4.json": ("6220a41f02c07c8db0d01f9e8b8b598ac848b6b52af448d1770e606faa879212"),
    "healthy/artifact-5.json": ("5c32259e5658e88f92e32c5b960fea4d88af461f013b4103cccb0e5fc6ae2a85"),
    "healthy/artifact-6.json": ("86268b78db4590aa5be46e381dca611d81af604d5169d1a1d9f8b25186fb451e"),
    "healthy/artifact-7.json": ("3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"),
    "healthy/artifact-8.json": ("3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"),
    "healthy/artifact-9.json": ("3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"),
    "healthy/expected.json": ("bd833f80da70d9819da965b6fd24b485b48c850179ddd4e8e20c951885dd826b"),
    "healthy/experiment-manifest.json": (
        "cfc87c8675245096e321e53ede9cf9d3d7ec8b073e09a52e9f2a064c25beac4c"
    ),
    "healthy/experiment-result.json": (
        "00b9b8ad544c88bfad8368d5205513264a9a0868ffda5d962e53391c0e9cc477"
    ),
    "host/artifact-1.json": ("35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"),
    "host/artifact-10.json": ("3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"),
    "host/artifact-2.json": ("b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"),
    "host/artifact-3.json": ("93d57a404c83a95ded3c75941b32838ff4698e3206ce77d6c04184d6443e8da3"),
    "host/artifact-4.json": ("d033474162b15cd7bdd199f3ea44201a2c97ff939c523fed5c515ac070ae7189"),
    "host/artifact-5.json": ("e94a346ff3b67ac20aa4d5909e3989a72037d1599881fdc0926067f57ac5b3fd"),
    "host/artifact-6.json": ("dc09f31939961dba34917d7a5deb6ca7f357794c5d5b6ca1d323374d73f03ab6"),
    "host/artifact-7.json": ("3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"),
    "host/artifact-8.json": ("0cb8528d84225e78cd37015b1394083cb508916f3008c1d57826ab452e50be82"),
    "host/artifact-9.json": ("0cb8528d84225e78cd37015b1394083cb508916f3008c1d57826ab452e50be82"),
    "host/expected.json": ("d3d3160f2f3d67117e832e30bac039f05224dbb78c106e631af5cc74c31ca858"),
    "host/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "host/experiment-result.json": (
        "78d3eb2437bcd8fb6eb249878109d455ce2f132456b58af4c093a26990369f0b"
    ),
    "missing-trace/artifact-1.json": (
        "35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"
    ),
    "missing-trace/artifact-2.json": (
        "b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"
    ),
    "missing-trace/artifact-3.json": (
        "93d57a404c83a95ded3c75941b32838ff4698e3206ce77d6c04184d6443e8da3"
    ),
    "missing-trace/artifact-4.json": (
        "d033474162b15cd7bdd199f3ea44201a2c97ff939c523fed5c515ac070ae7189"
    ),
    "missing-trace/artifact-5.json": (
        "e94a346ff3b67ac20aa4d5909e3989a72037d1599881fdc0926067f57ac5b3fd"
    ),
    "missing-trace/artifact-6.json": (
        "dc09f31939961dba34917d7a5deb6ca7f357794c5d5b6ca1d323374d73f03ab6"
    ),
    "missing-trace/expected.json": (
        "e954c44f1ed79425dd6944ac4ad93e978cc1bebd1a5badca5c3d2e628435fe91"
    ),
    "missing-trace/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "missing-trace/experiment-result.json": (
        "fc620bec95460507190163ef4d8f331431a41cf0c3b63f9eb05827cacc79bcc9"
    ),
    "unknown-cleanup/artifact-1.json": (
        "35dfd05c3a9b5884b75646ab0bc84bd267a5e97b6a4b7fe8657070aef1b43380"
    ),
    "unknown-cleanup/artifact-2.json": (
        "b154923a1009fbfb25784c8aff6bc81ea74728925e6035e74365b910c860c923"
    ),
    "unknown-cleanup/artifact-3.json": (
        "e99aa2771670b860d0fe983b239b0f74ccf0111eeb217c91edd6ded04f1df143"
    ),
    "unknown-cleanup/artifact-4.json": (
        "3be96af76e95d816ea7cec787f75d88fc59d0af30f3441bf292e743090af80a2"
    ),
    "unknown-cleanup/artifact-5.json": (
        "332aeafb38d02b00bf9ce0fbdca38868007dfa5b9c27bad7afcd24fb7002f71a"
    ),
    "unknown-cleanup/expected.json": (
        "9a946dd8677044e30e54bfae4f628f3066dcc08ece9e435244e46faaa536a8f7"
    ),
    "unknown-cleanup/experiment-manifest.json": (
        "f661ad6fc3f2e0f32d2916fb30e06c3b4d543b8b271aa48dd465783b8ccf8d20"
    ),
    "unknown-cleanup/experiment-result.json": (
        "9a7827b95cb082384ba6447dcec063368091ae25d5e08bfdd0f223386f82d194"
    ),
    "unsupported/expected.json": (
        "78881e178d6c646a3607daa16f847311d2a2d74f9e22f495217f4d83a56a5a70"
    ),
    "unsupported/experiment-manifest.json": (
        "fa25d2afec6da4f6a11e2068ddef7f53b53ce5ccd609e9d03052e8a387cd0912"
    ),
    "unsupported/experiment-result.json": (
        "8b27aec1ca84c58d0b9476db929f00216c7d26341fefb9facd6bd145eefce404"
    ),
}


def check_reproduction(directory=FIXTURES, producer_bundles=None):
    hashes = {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }
    if hashes != EXPECTED_SHA256:
        raise ValueError("N5 fixture release pin mismatch")
    for case in CASES:
        source = directory / case
        expected_files = {
            p.name: p.read_bytes() for p in source.iterdir() if p.name != "expected.json"
        }
        expected = json.loads((source / "expected.json").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary).resolve() / "bundle"
            bundle.mkdir()
            for name in expected_files:
                shutil.copyfile(source / name, bundle / name)
            inspected = inspect_experiment_bundle(bundle)
            observed = inspected.result.model_dump(mode="json")
            if {key: observed[key] for key in expected} != expected:
                raise ValueError("N5 independent effect/cleanup expectation mismatch")
            if (
                canonical_json(inspected.manifest).encode()
                != expected_files["experiment-manifest.json"]
                or canonical_json(inspected.result).encode()
                != expected_files["experiment-result.json"]
            ):
                raise ValueError("N5 canonical root drift")
            for ref, artifact in zip(inspected.result.artifacts, inspected.artifacts, strict=True):
                if canonical_json(artifact).encode() != expected_files[ref.file_name]:
                    raise ValueError("N5 canonical artifact drift")
            output = bundle.parent / "result.json"
            if (
                cli_main(["inspect-experiment", "--bundle", str(bundle), "--output", str(output)])
                != 0
                or output.read_bytes() != expected_files["experiment-result.json"]
            ):
                raise ValueError("N5 directory CLI drift")
            if producer_bundles is not None:
                produced = producer_bundles / f"{case}.tar.gz"
                if read_members(produced) != expected_files:
                    raise ValueError("N5 producer artifact bytes drift")
                if inspect_experiment_bundle(produced) != inspected:
                    raise ValueError("N5 producer inspection drift")
                if (
                    cli_main(
                        ["inspect-experiment", "--bundle", str(produced), "--output", str(output)]
                    )
                    != 0
                    or output.read_bytes() != expected_files["experiment-result.json"]
                ):
                    raise ValueError("N5 producer CLI drift")
    return dict(
        status="current",
        fixtureRelease="1.0.0",
        fixtureSha256=hashes,
        producerIntegration="passed" if producer_bundles is not None else "not_run",
        provenance="synthetic",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-bundles", type=Path)
    args = parser.parse_args()
    try:
        result = check_reproduction(producer_bundles=args.producer_bundles)
    except (OSError, ValueError):
        print("error: N5 reproduction failed", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
