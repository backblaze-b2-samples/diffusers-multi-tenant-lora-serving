"""Accept only safetensors adapters: parse the header, never unpickle anything.

A `.bin` / `.pt` / `.ckpt` file is a pickle and can execute code on load, so
the registry refuses every format but safetensors, and checks the header is
well formed and accounts for the whole file before a byte goes to B2.
"""

import json
import struct
from typing import BinaryIO

_MAX_HEADER = 100 * 1024 * 1024


class NotSafetensorsError(ValueError):
    pass


def validate_safetensors(fileobj: BinaryIO, size: int) -> int:
    """Validate the header of a seekable file. Returns the tensor count.

    Rewinds the file before returning. Raises NotSafetensorsError.
    """
    fileobj.seek(0)
    head = fileobj.read(8)
    if len(head) != 8:
        raise NotSafetensorsError("file is too small to be safetensors")
    (header_len,) = struct.unpack("<Q", head)
    if header_len <= 1 or header_len > _MAX_HEADER or 8 + header_len > size:
        raise NotSafetensorsError("not a safetensors file (bad header length)")
    raw = fileobj.read(header_len)
    try:
        header = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NotSafetensorsError("not a safetensors file (header is not JSON)") from None
    if not isinstance(header, dict):
        raise NotSafetensorsError("not a safetensors file (header is not an object)")
    end = 0
    tensors = 0
    for name, entry in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(entry, dict) or "data_offsets" not in entry or "dtype" not in entry:
            raise NotSafetensorsError(f"tensor entry '{name}' is malformed")
        start, stop = entry["data_offsets"]
        if not (isinstance(start, int) and isinstance(stop, int) and 0 <= start <= stop):
            raise NotSafetensorsError(f"tensor entry '{name}' has bad offsets")
        end = max(end, stop)
        tensors += 1
    if tensors == 0:
        raise NotSafetensorsError("safetensors file holds no tensors")
    if 8 + header_len + end != size:
        raise NotSafetensorsError("safetensors header does not account for the file size")
    fileobj.seek(0)
    return tensors
