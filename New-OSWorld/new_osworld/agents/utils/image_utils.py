"""Image encoding / decoding helpers for LLM vision APIs."""

from __future__ import annotations

import base64
import os
import tempfile
from io import BytesIO
from typing import Optional

from PIL import Image


def encode_image_bytes(raw: bytes) -> str:
    """Base64-encode raw image bytes.

    Args:
        raw: PNG/JPEG bytes.

    Returns:
        A base64-encoded string.
    """
    return base64.b64encode(raw).decode("utf-8")


def decode_base64_to_pil(data_str: str) -> Image.Image:
    """Decode a base64 (or data-URI) string into a PIL Image.

    Args:
        data_str: Raw base64 or ``data:image/png;base64,...`` string.
    """
    b64 = data_str.replace("data:image/png;base64,", "")
    return Image.open(BytesIO(base64.b64decode(b64)))


def save_base64_to_tempfile(data_str: str, suffix: str = ".png") -> str:
    """Write a base64 image to a temp file and return the path.

    Args:
        data_str: Base64 or data-URI string.
        suffix: File suffix (default ``.png``).

    Returns:
        Absolute path to the temporary image file.
    """
    img = decode_base64_to_pil(data_str)
    path = os.path.join(tempfile.mkdtemp(), f"tmp_img{suffix}")
    img.save(path)
    return path
