"""Codec adapter contract (spec section 25).

    availability() -> dict          {"status": AVAILABLE | UNAVAILABLE | UNAVAILABLE_BUILD, "version", "reason"}
    encode(array, options) -> bytes  canonical (Z,Y,X) C-order unsigned array -> standalone stream
    decode(payload, options)         stream -> canonical (Z,Y,X) array; never touches the original
    decode_roi(payload, bbox, opts)  UnsupportedOperation unless the codec has chunk access

Accounting rule (spec 39.7, one rule for every method): total_bytes = len(stored stream);
metadata_bytes = bytes of an uncompressed container header added by the adapter outside the
codec's own stream (0 when the native stream is standalone or the header sits inside a wrapper
frame); payload_bytes = total_bytes - metadata_bytes.
"""

from __future__ import annotations

import struct

import numpy as np


class UnsupportedOperation(Exception):
    """Requested operation (e.g. ROI decode) is not implemented by this codec."""


class AdapterUnavailable(Exception):
    """Dependency or build missing; reported as UNAVAILABLE / UNAVAILABLE_BUILD, never faked."""


class UnsupportedDtype(Exception):
    """The codec cannot store this dtype without a separately named conversion adapter."""


class CodecAdapter:
    adapter_name = "base"
    supported_dtypes: tuple[str, ...] = ("uint8", "uint16", "uint32", "uint64")
    crackle_format = False

    def __init__(self, method_id: str, options: dict | None = None, threads: int = 1):
        self.method_id = method_id
        self.options = dict(options or {})
        self.threads = int(threads)
        self.last_diagnostics: dict = {}
        self.last_metadata_bytes = 0

    # -- contract ---------------------------------------------------------------
    def availability(self) -> dict:
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        return "unknown"

    def check_dtype(self, dtype) -> None:
        if str(np.dtype(dtype)) not in self.supported_dtypes:
            raise UnsupportedDtype(f"{self.method_id} does not support {np.dtype(dtype)} (supported: "
                                   f"{', '.join(self.supported_dtypes)}); no silent cast")

    def encode(self, array: np.ndarray, options: dict | None = None) -> bytes:
        raise NotImplementedError

    def decode(self, payload: bytes, options: dict | None = None) -> np.ndarray:
        raise NotImplementedError

    def decode_roi(self, payload: bytes, bbox, options: dict | None = None):
        raise UnsupportedOperation(f"{self.method_id}: ROI decode is not supported")

    def secondary_check(self, payload: bytes, array: np.ndarray) -> dict:
        """Optional extra verification outside the timed region (e.g. a second decoder)."""
        return {}


# ------------------------------------------------------------ generic container
CONTAINER_MAGIC = b"CPGN"
CONTAINER_VERSION = 1
_HEADER = struct.Struct("<4sBBBBQQQI")  # magic, version, codec, itemsize, reserved, Z, Y, X, extra_len


def pack_container(codec_id: int, array_dtype, shape_zyx, payload: bytes, extra: bytes = b"") -> tuple[bytes, int]:
    header = _HEADER.pack(CONTAINER_MAGIC, CONTAINER_VERSION, codec_id, np.dtype(array_dtype).itemsize, 0,
                          *[int(v) for v in shape_zyx], len(extra)) + extra
    return header + payload, len(header)


def unpack_container(stream: bytes, codec_id: int) -> tuple[np.dtype, tuple[int, int, int], bytes, memoryview]:
    if len(stream) < _HEADER.size:
        raise ValueError("container too short")
    magic, ver, cid, itemsize, _res, z, y, x, extra_len = _HEADER.unpack_from(stream, 0)
    if magic != CONTAINER_MAGIC or ver != CONTAINER_VERSION or cid != codec_id:
        raise ValueError("not a CAPE generic container for this codec")
    dtype = np.dtype({1: "<u1", 2: "<u2", 4: "<u4", 8: "<u8"}[itemsize])
    off = _HEADER.size
    extra = bytes(stream[off: off + extra_len])
    return dtype, (z, y, x), extra, memoryview(stream)[off + extra_len:]
