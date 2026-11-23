"""Core object details for the bucket explorer's detail panel.

The starter kit's format-specific extraction (PDF fields, EXIF) is trimmed;
the panel keeps checksums, type and, for images such as generated outputs,
pixel dimensions.
"""

import hashlib
import io
import os
from datetime import datetime

from app.types import FileMetadataDetail
from app.types.formatting import humanize_bytes


def core_metadata(
    data: bytes, filename: str, content_type: str, uploaded_at: datetime
) -> FileMetadataDetail:
    width = height = None
    warning = None
    if content_type.startswith("image/"):
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as img:
                width, height = img.size
        except Exception as e:  # unreadable image: keep the exact core fields
            warning = f"Image dimensions unavailable: {type(e).__name__}"
    return FileMetadataDetail(
        filename=filename,
        size_bytes=len(data),
        size_human=humanize_bytes(len(data)),
        mime_type=content_type,
        extension=os.path.splitext(filename)[1].lower().lstrip("."),
        md5=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_at=uploaded_at,
        metadata_warning=warning,
        image_width=width,
        image_height=height,
    )
