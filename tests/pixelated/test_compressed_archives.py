"""Expanded bytes and physical extension headers are bounded before TAR interpretation."""

import bz2
import gzip
import io
import lzma
import tarfile

import pytest

from latency_fingerprinting.adapters import pixelated_bundle_io
from latency_fingerprinting.adapters.pixelated_bundle_common import PixelatedBundleError
from tests.pixelated.support import copy_bundle, ingest, write_tar

COMPRESSORS = [
    pytest.param(lambda data: data, id="plain"),
    gzip.compress,
    bz2.compress,
    lzma.compress,
    pytest.param(lambda data: lzma.compress(data, format=lzma.FORMAT_ALONE), id="lzma-alone"),
]


@pytest.mark.parametrize("compress", COMPRESSORS)
def test_supported_compression_preserves_adoption(tmp_path, context, compress):
    bundle = copy_bundle(tmp_path)
    path = tmp_path / "bundle.tar"
    write_tar(bundle, path)
    path.write_bytes(compress(path.read_bytes()))
    assert ingest(path, context) == ingest(bundle, context)


@pytest.mark.parametrize("compress", COMPRESSORS)
def test_expansion_is_rejected_before_tar_interpretation(tmp_path, monkeypatch, compress):
    path = tmp_path / "expanded.tar"
    path.write_bytes(compress(b"\0" * 32768))
    # Exercise a small limit without allocating an oversized production archive.
    monkeypatch.setattr(pixelated_bundle_io, "MAX_ARCHIVE_DECLARED_BYTES", 4096)
    monkeypatch.setattr(pixelated_bundle_io, "MAX_ARCHIVE_MEMBERS", 1)
    calls = []
    monkeypatch.setattr(tarfile, "open", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(PixelatedBundleError, match="expanded TAR"):
        pixelated_bundle_io.read_bundle(path, readable_files=set(), required_files=set())
    assert calls == []


def test_hidden_extension_chain_is_rejected_before_tar_interpretation(tmp_path, monkeypatch):
    # GNU long-name headers recursively consume the following physical header;
    # counting only logical members lets an arbitrary chain bypass the member cap.
    extension = tarfile.TarInfo("././@LongLink")
    extension.type = tarfile.GNUTYPE_LONGNAME
    extension.size = 2
    raw = (extension.tobuf(format=tarfile.GNU_FORMAT) + b"x\0" + bytes(510)) * 65
    path = tmp_path / "extensions.tar.gz"
    path.write_bytes(gzip.compress(raw + bytes(1024)))
    calls = []
    monkeypatch.setattr(tarfile, "open", lambda **kwargs: calls.append(kwargs))
    with pytest.raises(PixelatedBundleError, match="physical TAR"):
        pixelated_bundle_io.read_bundle(path, readable_files=set(), required_files=set())
    assert calls == []


def test_normal_pax_metadata_is_preserved(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        entry = tarfile.TarInfo("test.json")
        entry.pax_headers = {"comment": "ordinary metadata"}
        entry.size = 2
        archive.addfile(entry, io.BytesIO(b"{}"))
    path = tmp_path / "pax.tar.gz"
    path.write_bytes(gzip.compress(stream.getvalue()))
    assert pixelated_bundle_io.read_bundle(
        path, readable_files={"test.json"}, required_files={"test.json"}
    ) == {"test.json": b"{}"}


@pytest.mark.parametrize(
    "payload", [b"\x1f\x8b\x08\0" + bytes(6) + b"\xff" * 32, b"BZh9broken", b"\xfd7zXZ\0broken"]
)
def test_corrupt_compression_is_a_bundle_error(tmp_path, payload):
    path = tmp_path / "corrupt.tar"
    path.write_bytes(payload)
    with pytest.raises(PixelatedBundleError):
        pixelated_bundle_io.read_bundle(path, readable_files=set(), required_files=set())


def test_concatenated_xz_streams_preserve_the_archive(tmp_path, context):
    bundle = copy_bundle(tmp_path)
    path = tmp_path / "bundle.tar"
    write_tar(bundle, path)
    raw = path.read_bytes()
    middle = len(raw) // 2
    path.write_bytes(lzma.compress(raw[:middle]) + bytes(4) + lzma.compress(raw[middle:]))
    assert ingest(path, context) == ingest(bundle, context)


def test_lzma_dictionary_memory_is_bounded(tmp_path):
    # A tiny stream can request a large decoder dictionary without much output.
    path = tmp_path / "dictionary.tar.lzma"
    # LZMA-alone header: lc/lp/pb property, 256 MiB dictionary, unknown output size.
    path.write_bytes(b"\x5d" + (256 * 1024 * 1024).to_bytes(4, "little") + b"\xff" * 8 + bytes(16))
    with pytest.raises(PixelatedBundleError, match="cannot decode bounded TAR"):
        pixelated_bundle_io.read_bundle(path, readable_files=set(), required_files=set())
