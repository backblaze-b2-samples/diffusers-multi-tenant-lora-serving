"""In-memory stand-in for `app.repo.adapter_store` (no network, no boto3)."""

import hashlib
import json
import struct
from datetime import UTC, datetime


def make_safetensors(seed: int = 0, tensors: int = 1) -> bytes:
    """A tiny, valid safetensors file whose bytes vary with `seed`."""
    header, data = {}, b""
    for i in range(tensors):
        header[f"lora_unet_down.{i}.lora_down.weight"] = {
            "dtype": "F32", "shape": [1], "data_offsets": [len(data), len(data) + 4],
        }
        data += struct.pack("<f", float(seed + i))
    raw = json.dumps(header).encode()
    return struct.pack("<Q", len(raw)) + raw + data


class FakeStore:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.ops: list[tuple[str, str]] = []
        self.presigned: list[tuple[str, str]] = []
        self.fail_on_put: str | None = None
        self.fail_on_upload: str | None = None

    def _etag(self, key):
        return '"' + hashlib.md5(self.objects[key]).hexdigest() + '"'

    def upload_stream(self, key, fileobj, content_type, on_bytes=None):
        if self.fail_on_upload and key.endswith(self.fail_on_upload):
            raise RuntimeError("B2 upload failed: Read timeout on endpoint URL")
        data = fileobj.read()
        if on_bytes:
            on_bytes(len(data))
        self.ops.append(("upload", key))
        self.objects[key] = data
        return hashlib.sha256(data).hexdigest(), len(data)

    def put_bytes(self, key, body, content_type):
        if self.fail_on_put and key.endswith(self.fail_on_put):
            raise RuntimeError("injected put failure")
        self.ops.append(("put", key))
        self.objects[key] = body

    def put_json(self, key, data):
        self.put_bytes(key, json.dumps(data).encode(), "application/json")

    def get_json(self, key):
        if key not in self.objects:
            return None
        return json.loads(self.objects[key]), self._etag(key)

    def head(self, key):
        if key not in self.objects:
            return None
        return len(self.objects[key]), self._etag(key)

    def hash_object(self, key):
        if key not in self.objects:
            return None
        return hashlib.sha256(self.objects[key]).hexdigest(), len(self.objects[key])

    def presign_get(self, key, ttl_seconds):
        self.presigned.append(("GET", key))
        return f"https://b2.example/{key}?X-Amz-Expires={ttl_seconds}"

    def presign_put(self, key, ttl_seconds, content_type):
        self.presigned.append(("PUT", key))
        return f"https://b2.example/{key}?put=1&X-Amz-Expires={ttl_seconds}"

    def iter_objects(self, prefix):
        now = datetime.now(UTC)
        for k in sorted(self.objects):
            if k.startswith(prefix):
                yield {"Key": k, "Size": len(self.objects[k]), "LastModified": now}

    def list_child_prefixes(self, prefix):
        kids = {
            prefix + k[len(prefix):].split("/", 1)[0] + "/"
            for k in self.objects
            if k.startswith(prefix) and "/" in k[len(prefix):]
        }
        return sorted(kids)

    def delete_keys(self, keys):
        for k in keys:
            self.ops.append(("delete", k))
            self.objects.pop(k, None)
        return list(keys)
