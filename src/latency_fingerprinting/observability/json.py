"""N4 text decoding caps; bundle/no-follow file adoption belongs to Step 5."""

from ..json_io import MAX_CONTRACT_JSON_BYTES, strict_json_loads


def decode_trace_json(data):
    if isinstance(data, (bytes, bytearray)):
        if len(data) > MAX_CONTRACT_JSON_BYTES:
            raise ValueError("trace JSON exceeds byte limit")
        data = data.decode("utf-8")
    if not isinstance(data, str):
        raise ValueError("trace JSON must be text or UTF-8 bytes")
    if len(data.encode("utf-8")) > MAX_CONTRACT_JSON_BYTES:
        raise ValueError("trace JSON exceeds byte limit")
    depth, quoted, escaped = 0, False, False
    for char in data:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 32:
                raise ValueError("trace JSON exceeds depth 32")
        elif char in "]}":
            depth -= 1
    return strict_json_loads(data)
