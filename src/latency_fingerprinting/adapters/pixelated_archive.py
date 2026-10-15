"""Bound legacy TAR expansion and physical headers before metadata interpretation."""

import bz2
import gzip
import io
import lzma
import tarfile
import zlib

from .pixelated_bundle_common import PixelatedBundleError


def _expanded_bytes(payload: bytes, maximum: int) -> bytes:
    if payload.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as decoder:
            return decoder.read(maximum + 1)
    if payload.startswith(b"BZh"):
        with bz2.BZ2File(io.BytesIO(payload)) as decoder:
            return decoder.read(maximum + 1)
    # Preserve plain TAR and the formats previously accepted by tarfile's r:*.
    try:
        tarfile.TarInfo.frombuf(payload[:512], tarfile.ENCODING, "surrogateescape")
        return payload
    except (tarfile.EmptyHeaderError, tarfile.EOFHeaderError):
        return payload
    except tarfile.HeaderError:
        pass
    # LZMA also declares dictionary memory independently of output size.
    remaining, chunks, size = payload, [], 0
    while remaining:
        decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
        chunk = decoder.decompress(remaining, max_length=maximum + 1 - size)
        chunks.append(chunk)
        size += len(chunk)
        if size > maximum:
            break
        if not decoder.eof:
            raise ValueError("incomplete compressed TAR")
        remaining = decoder.unused_data.lstrip(b"\0")
    return b"".join(chunks)


def bounded_tar_bytes(payload: bytes, *, declared_limit: int, member_limit: int) -> bytes:
    """Cap padding/metadata expansion and recursive GNU/PAX chains as well as files."""
    # Account for physical headers, rounding and the usual final TAR record.
    maximum = declared_limit + member_limit * 1024 + tarfile.RECORDSIZE
    try:
        expanded = _expanded_bytes(payload, maximum)
    except (OSError, EOFError, ValueError, lzma.LZMAError, zlib.error) as error:
        raise PixelatedBundleError("cannot decode bounded TAR archive") from error
    if len(expanded) > maximum:
        raise PixelatedBundleError("expanded TAR archive exceeds the byte limit")
    offset = count = declared = 0
    while offset + 512 <= len(expanded) and any(expanded[offset : offset + 512]):
        count += 1
        if count > member_limit:
            raise PixelatedBundleError(
                f"TAR contains more than {member_limit} members (physical TAR headers)"
            )
        try:
            member = tarfile.TarInfo.frombuf(
                expanded[offset : offset + 512], tarfile.ENCODING, "surrogateescape"
            )
        except tarfile.HeaderError as error:
            raise PixelatedBundleError("invalid physical TAR header") from error
        if member.size < 0:
            raise PixelatedBundleError("negative physical TAR member size")
        declared += member.size
        if declared > declared_limit:
            raise PixelatedBundleError(
                "TAR declared contents exceed the archive size limit (physical headers)"
            )
        offset += 512 + (member.size + 511) // 512 * 512
    return expanded
