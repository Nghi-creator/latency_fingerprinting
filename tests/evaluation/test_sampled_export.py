"""Full producer CSV/export path; artificial telemetry and no runtime claim."""

import hashlib

from tests.pixelated.support import FIXTURE_ROOT

from .producer_boundary import check_producer_bundle


def test_full_producer_sample_export_preserves_arithmetic_and_actual_declarations():
    archive = FIXTURE_ROOT / "producer-sampled-v2.tar"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == (
        "8e74ee4b0f289f6b302de52006c2b3f6c6dbe5051561e8f3346a6333bac20618"
    )
    first, second = check_producer_bundle(archive, full_sample_export=True)
    assert first.measurements["client.received_fps"].support.declared_state == "supported"
    assert first.measurements["encoder.pipeline_delay_proxy_ms"].support.state == "unsupported"
    # Current export declares packet-loss deltas, while N1 aggregates the total.
    # That total's support is inherited from the source, not an invented declaration.
    lost = first.measurements["transport.packets_lost_rate_per_s"]
    assert lost.support.basis == "source_support"
    assert lost.support.declared_state is None
    assert second.measurements["client.frames_decoded_rate_fps"].summary.value == 60
