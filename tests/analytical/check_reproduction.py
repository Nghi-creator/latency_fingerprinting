"""Read-only independent expectations, exact bytes and pinned N3 release reproduction."""

import hashlib
import json
import sys

from .fixture_cases import DEFAULT_FIXTURE_DIRECTORY, fixture_drift, fixture_records
from .fixture_expectations import check_expectations

# Release 1.0.0 pins, retained independently after reviewing numerical expectations.
EXPECTED_SHA256 = {
    "inputs/observation.json": ("d6b96c18e0104fcd62ea2525b5637c6aadf7a033ac30d3b4e918be3ff8088954"),
    "matches/ambiguous_margin.json": (
        "a2a354f96b53edbe9129cf06ee65dddec911eb34b57457cff5acbb08cdcd9cd2"
    ),
    "matches/conflicting_evidence.json": (
        "951e4ee9ae41c08e6d8c68d2bb813f204c9454fc6894dec2514f254113599163"
    ),
    "matches/insufficient_features.json": (
        "51d92782bbee84b5e12b7e0976c4eca8d494630a482f03f9d709213836c8a4f8"
    ),
    "matches/invalid_response.json": (
        "9d0a1ed8d71cfacc1101c6a99c5adf5ade3617b8593a6f29bff2d3fb647b9752"
    ),
    "matches/matched.json": ("df0475871d1f8c7b38613b3e2e7d42e82967d1f16ea91c3704fe82db4ba501bf"),
    "matches/no_compatible_fingerprints.json": (
        "9d28b25d2d8e9ccaf7e6d1dab06f08bc8c35813afc97f0bc6a298fb95fa9c2a8"
    ),
    "matches/no_fingerprints.json": (
        "cf09d9322387ef747c55fb1faf32b7292a867f93c1ffe363e15a0ad52e93ecda"
    ),
    "matches/weak_match.json": ("72df923fb7ffb1ae089d17ce79ab07d5a42a7e70ce10e26b1fefdf3ae96fcd8b"),
    "policy.json": ("e3f54c5eb4b8fd4d406a9b201584a28db97c15b04478ae9226f854bb580bad7e"),
    "references/ambiguous/fingerprint-1.json": (
        "8bdffc0395a859501bcb7df5b9210754a69b93b5cfa18f43db46be97fe690029"
    ),
    "references/ambiguous/fingerprint-2.json": (
        "842a0fe80ca5971c9922a06b245754c1fa85a066795bc46a8ed9f11e3a7361d8"
    ),
    "references/conflicting/fingerprint.json": (
        "12b8ee3344e559118c3b0a7e2994a0aef46f3cc6c3a3cc07461005c10a97e9be"
    ),
    "references/matched/fingerprint.json": (
        "c1bfbd794731177e7f3abd972a9d7856de2f86ca8a2a7ab7db4d77b37f4c572a"
    ),
    "references/unreviewed/fingerprint.json": (
        "1ca0fe53b37d7d4afc1f0ffc09f27ba11da0e94657b14e7e6774dcb10921c66a"
    ),
    "references/weak/fingerprint.json": (
        "23394bd3f6c7b29a434d9c352f6ac9a8066a51e3a92db188a87c73bc2fe49542"
    ),
    "responses/complete.json": ("4a3a636bc7a7c5ee0ac729be40035460fbdd477e41e22cd3965b91a19bc39427"),
    "responses/confounded.json": (
        "801a6199289e6ae739107b05befb8752abad222c823056fafa966a2cdd8c3c67"
    ),
    "responses/insufficient.json": (
        "07b8f7532fcddb251330a7a667b08e7dc13ba89a8cf2bb9b7c5ec03a289af208"
    ),
}


def check_reproduction():
    check_expectations(fixture_records())
    if fixture_drift(DEFAULT_FIXTURE_DIRECTORY):
        raise ValueError("N3 analytical fixture drift")
    hashes = {
        path.relative_to(DEFAULT_FIXTURE_DIRECTORY).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(DEFAULT_FIXTURE_DIRECTORY.rglob("*.json"))
    }
    if hashes != EXPECTED_SHA256:
        raise ValueError("N3 analytical release pin mismatch")
    return {"status": "current", "fixtureRelease": "1.0.0", "fixtureSha256": hashes}


def main():
    try:
        result = check_reproduction()
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
