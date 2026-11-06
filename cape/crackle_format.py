"""Pure-Python reference of the Crackle v1 container (pinned upstream SHA 14b39b1).

Used by tests, the format audit (docs/format_audit.md) and diagnostics. It is never used
on a timed encode/decode path. Every rule here mirrors a specific upstream function:

  header           crackle/src/header.hpp      CrackleHeader::assign_from_buffer / tochars
  stream layout    crackle/src/crackle.hpp     compress_helper (lines 75-221)
  pins section     crackle/src/labels.hpp      encode_condensed_pins / decode_condensed_pins
  flat section     crackle/src/labels.hpp      encode_flat / decode_flat
  byte widths      crackle/src/lib.hpp         compute_byte_width

Stream layout:
  header (29 B, crc8 over bytes 5..27)
  z-index: Z x uint32 crack-code sizes, then crc32c(z-index sizes)
  labels section (header.num_label_bytes)
  markov model (header.markov_model_bytes(); only when markov order > 0)
  crack codes (sum of z-index sizes)
  crc32c(labels section)
  Z x uint32: crc32c of each slice-local CC label image
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterable, Sequence

MAGIC = b"crkl"
HEADER_SIZE_V0 = 24
HEADER_SIZE_V1 = 29

FLAT = 0
PINS_FIXED_WIDTH = 1
PINS_VARIABLE_WIDTH = 2

U32 = 0xFFFFFFFF
U64 = 0xFFFFFFFFFFFFFFFF


class FormatError(ValueError):
    """Raised when a stream or record set violates the container rules."""


def byte_width(x: int) -> int:
    """crackle::lib::compute_byte_width: smallest of 1/2/4/8 bytes holding x."""
    if x < 0:
        raise FormatError(f"byte_width of negative value {x}")
    if x <= 0xFF:
        return 1
    if x <= 0xFFFF:
        return 2
    if x <= U32:
        return 4
    if x <= U64:
        return 8
    raise FormatError(f"value {x} does not fit in 8 bytes")


def _log2_width(width: int) -> int:
    try:
        return {1: 0, 2: 1, 4: 2, 8: 3}[width]
    except KeyError as exc:
        raise FormatError(f"invalid byte width {width}") from exc


# --------------------------------------------------------------------------- CRCs

def crc8(data: bytes | bytearray | memoryview) -> int:
    """crackle::crc::crc8 (polynomial 0xE7, init 0xFF, LSB first)."""
    crc = 0xFF
    for b in bytes(data):
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xE7) if (crc & 1) else (crc >> 1)
    return crc


def _make_crc32c_table() -> list[int]:
    poly = 0x82F63B78  # reflected Castagnoli polynomial
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c >> 1) ^ poly) if (c & 1) else (c >> 1)
        table.append(c)
    return table


_CRC32C_TABLE = _make_crc32c_table()


def crc32c(data: bytes | bytearray | memoryview) -> int:
    """Standard CRC-32C (as computed by upstream crc32_impl(0, ...))."""
    crc = U32
    table = _CRC32C_TABLE
    for b in bytes(data):
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ U32


# ------------------------------------------------------------------------- header

@dataclass(frozen=True)
class Header:
    format_version: int
    label_format: int
    crack_format: int
    is_signed: bool
    data_width: int
    stored_data_width: int
    sx: int
    sy: int
    sz: int
    grid_size: int
    num_label_bytes: int
    fortran_order: bool
    markov_model_order: int
    is_sorted: bool
    is_remapped: bool
    crc: int | None = None

    @property
    def header_bytes(self) -> int:
        return HEADER_SIZE_V0 if self.format_version == 0 else HEADER_SIZE_V1

    @property
    def grid_index_bytes(self) -> int:
        return 4 * self.sz if self.format_version == 0 else 4 * (self.sz + 1)

    @property
    def voxels(self) -> int:
        return self.sx * self.sy * self.sz

    @property
    def pin_index_width(self) -> int:
        # Upstream multiplies three uint32 fields in 32-bit arithmetic (wraps at 2**32).
        return byte_width((self.sx * self.sy * self.sz) & U32)

    @property
    def pin_index_width_overflows(self) -> bool:
        return self.sx * self.sy * self.sz > U32

    @property
    def component_width(self) -> int:
        # labels.hpp: compute_byte_width(header.sx * header.sy), uint32 arithmetic.
        return byte_width((self.sx * self.sy) & U32)

    @property
    def num_grids(self) -> int:
        gsize = min(self.grid_size, max(self.sx, self.sy))
        if gsize == 0:
            return 0
        ngrids = ((self.sx + gsize - 1) // gsize) * ((self.sy + gsize - 1) // gsize)
        return max(ngrids, 1) * self.sz

    @property
    def markov_model_bytes(self) -> int:
        if self.markov_model_order == 0:
            return 0
        model_size = 4 ** min(self.markov_model_order, 15)
        return ((model_size * 5) + 4) // 8

    def format_bits(self) -> int:
        bits = _log2_width(self.data_width)
        bits |= _log2_width(self.stored_data_width) << 2
        bits |= (self.crack_format & 0b1) << 4
        bits |= (self.label_format & 0b11) << 5
        bits |= int(self.fortran_order) << 7
        bits |= int(self.is_signed) << 8
        bits |= (self.markov_model_order & 0b1111) << 9
        bits |= int(not self.is_sorted) << 13
        bits |= int(self.is_remapped) << 14
        return bits

    def to_bytes(self) -> bytes:
        """CrackleHeader::tochars (version bumped to 1 if num_label_bytes needs 64 bits)."""
        fmt_ver = self.format_version
        if self.num_label_bytes > U32:
            fmt_ver = 1
        grid_log2 = self.grid_size.bit_length() - 1
        if 1 << grid_log2 != self.grid_size:
            raise FormatError("grid_size must be a power of two")
        out = bytearray(MAGIC)
        out += struct.pack("<BHIIIB", fmt_ver, self.format_bits(), self.sx, self.sy, self.sz, grid_log2)
        if fmt_ver == 0:
            out += struct.pack("<I", self.num_label_bytes)
            return bytes(out)
        out += struct.pack("<Q", self.num_label_bytes)
        out.append(crc8(out[5:28]))
        return bytes(out)


def parse_header(buf: bytes, verify_crc: bool = True) -> Header:
    """CrackleHeader::assign_from_buffer."""
    if len(buf) < HEADER_SIZE_V0:
        raise FormatError("buffer too small for a Crackle header")
    if bytes(buf[:4]) != MAGIC or buf[4] > 1:
        raise FormatError("not a valid Crackle stream (magic/version)")
    fmt_ver = buf[4]
    format_bytes, sx, sy, sz, grid_log2 = struct.unpack_from("<HIIIB", buf, 5)
    if fmt_ver == 0:
        (num_label_bytes,) = struct.unpack_from("<I", buf, 20)
        crc = None
    else:
        if len(buf) < HEADER_SIZE_V1:
            raise FormatError("buffer too small for a v1 header")
        (num_label_bytes,) = struct.unpack_from("<Q", buf, 20)
        crc = buf[28]
        if verify_crc and crc8(buf[5:28]) != crc:
            raise FormatError("header crc8 mismatch")
    return Header(
        format_version=fmt_ver,
        label_format=(format_bytes >> 5) & 0b11,
        crack_format=(format_bytes >> 4) & 0b1,
        is_signed=bool((format_bytes >> 8) & 0b1),
        data_width=1 << (format_bytes & 0b11),
        stored_data_width=1 << ((format_bytes >> 2) & 0b11),
        sx=sx,
        sy=sy,
        sz=sz,
        grid_size=1 << grid_log2,
        num_label_bytes=num_label_bytes,
        fortran_order=bool((format_bytes >> 7) & 0b1),
        markov_model_order=(format_bytes >> 9) & 0b1111,
        is_sorted=not bool((format_bytes >> 13) & 0b1),
        is_remapped=bool((format_bytes >> 14) & 0b1),
        crc=crc,
    )


# ------------------------------------------------------------------- stream split

@dataclass(frozen=True)
class StreamLayout:
    header: Header
    z_index_sizes: tuple[int, ...]
    z_index_crc_stored: int | None
    labels_offset: int
    labels: bytes
    markov_model: bytes
    crack_offset: int
    crack_codes: bytes
    labels_crc_stored: int | None
    cc_crcs: tuple[int, ...]
    total_bytes: int

    @property
    def boundary_payload(self) -> bytes:
        """Everything a label-selection change must not alter (spec section 19, panel A)."""
        return self.markov_model + self.crack_codes + struct.pack(f"<{len(self.cc_crcs)}I", *self.cc_crcs)


def split_stream(buf: bytes, verify: bool = True) -> StreamLayout:
    h = parse_header(buf, verify_crc=verify)
    off = h.header_bytes
    sizes = struct.unpack_from(f"<{h.sz}I", buf, off)
    z_crc = None
    if h.format_version > 0:
        (z_crc,) = struct.unpack_from("<I", buf, off + 4 * h.sz)
        if verify and crc32c(buf[off: off + 4 * h.sz]) != z_crc:
            raise FormatError("z-index crc32c mismatch")
    labels_offset = off + h.grid_index_bytes
    labels_end = labels_offset + h.num_label_bytes
    markov_end = labels_end + h.markov_model_bytes
    crack_end = markov_end + sum(sizes)
    tail = 4 + 4 * h.sz if h.format_version > 0 else 0
    if crack_end + tail != len(buf):
        raise FormatError(f"stream length mismatch: expected {crack_end + tail}, got {len(buf)}")
    labels = bytes(buf[labels_offset:labels_end])
    labels_crc = None
    cc_crcs: tuple[int, ...] = ()
    if h.format_version > 0:
        (labels_crc,) = struct.unpack_from("<I", buf, crack_end)
        cc_crcs = struct.unpack_from(f"<{h.sz}I", buf, crack_end + 4)
        if verify and crc32c(labels) != labels_crc:
            raise FormatError("labels crc32c mismatch")
    return StreamLayout(
        header=h,
        z_index_sizes=tuple(sizes),
        z_index_crc_stored=z_crc,
        labels_offset=labels_offset,
        labels=labels,
        markov_model=bytes(buf[labels_end:markov_end]),
        crack_offset=markov_end,
        crack_codes=bytes(buf[markov_end:crack_end]),
        labels_crc_stored=labels_crc,
        cc_crcs=tuple(cc_crcs),
        total_bytes=len(buf),
    )


def replace_labels_section(buf: bytes, new_labels: bytes, label_format: int | None = None) -> bytes:
    """Rebuild a stream with a different labels section (header length/crc8 + labels crc32c
    recomputed; z-index, markov model, crack codes and CC crcs kept byte-identical)."""
    lay = split_stream(buf)
    h = lay.header
    fields = {k: getattr(h, k) for k in h.__dataclass_fields__ if k != "crc"}
    fields["num_label_bytes"] = len(new_labels)
    if label_format is not None:
        fields["label_format"] = label_format
    new_h = Header(**fields)
    out = bytearray(new_h.to_bytes())
    out += buf[h.header_bytes: lay.labels_offset]  # z-index + its crc are unchanged
    out += new_labels
    out += lay.markov_model + lay.crack_codes
    if h.format_version > 0:
        out += struct.pack("<I", crc32c(new_labels))
        out += struct.pack(f"<{h.sz}I", *lay.cc_crcs)
    return bytes(out)


# --------------------------------------------------------------- pins label section

@dataclass
class PinsSection:
    """Decoded PINS_VARIABLE_WIDTH label section. Pins are (absolute start index, depth);
    CC ids are absolute global ids. Lists are per written (non-background) label."""

    stored_width: int  # w_L
    bgcolor: int
    labels: list[int]
    components_per_grid: list[int]
    component_width: int  # w_G
    index_width: int  # w_I
    num_pins_width: int  # w_N
    depth_width: int  # w_D
    cc_label_width: int  # w_C
    pins: list[list[tuple[int, int]]] = field(default_factory=list)
    cc_ids: list[list[int]] = field(default_factory=list)
    consumed_bytes: int = 0

    @property
    def P(self) -> int:
        return sum(len(p) for p in self.pins)

    @property
    def Q(self) -> int:
        return sum(len(c) for c in self.cc_ids)


def _uint(buf: bytes, off: int, width: int) -> int:
    end = off + width
    if end > len(buf):
        raise FormatError("pin section is malformed or truncated")
    return int.from_bytes(buf[off:end], "little")


def parse_pins_section(section: bytes, header: Header) -> PinsSection:
    """Mirror of labels.hpp decode_condensed_pins, parsing the whole section once."""
    wl = header.stored_data_width
    bg = _uint(section, 0, wl)
    n_labels = _uint(section, wl, 8)
    off = wl + 8
    labels = [_uint(section, off + i * wl, wl) for i in range(n_labels)]
    off += n_labels * wl
    wg = header.component_width
    ngrids = header.num_grids
    comps = [_uint(section, off + i * wg, wg) for i in range(ngrids)]
    off += ngrids * wg
    combined = _uint(section, off, 1)
    off += 1
    wn = 1 << (combined & 0b11)
    wd = 1 << ((combined >> 2) & 0b11)
    wc = 1 << ((combined >> 4) & 0b11)
    wi = header.pin_index_width
    out = PinsSection(wl, bg, labels, comps, wg, wi, wn, wd, wc)
    for _ in range(n_labels):
        num_pins = _uint(section, off, wn)
        off += wn
        idx = [_uint(section, off + j * wi, wi) for j in range(num_pins)]
        dep = [_uint(section, off + num_pins * wi + j * wd, wd) for j in range(num_pins)]
        off += num_pins * (wi + wd)
        for j in range(1, num_pins):
            idx[j] += idx[j - 1]
        num_cc = _uint(section, off, wn)
        off += wn
        ccs = [_uint(section, off + j * wc, wc) for j in range(num_cc)]
        off += num_cc * wc
        for j in range(1, num_cc):
            ccs[j] = (ccs[j] + ccs[j - 1]) & U32  # decoder accumulates in uint32
        out.pins.append(list(zip(idx, dep)))
        out.cc_ids.append(ccs)
    out.consumed_bytes = off
    return out


def _put(out: bytearray, value: int, width: int, strict: bool, what: str) -> None:
    if value < 0:
        raise FormatError(f"{what}: negative value {value}")
    if value >= 1 << (8 * width):
        if strict:
            raise FormatError(f"{what}: value {value} does not fit in {width} byte(s)")
        value &= (1 << (8 * width)) - 1  # upstream itocd silently keeps the low bytes
    out += value.to_bytes(width, "little")


def serialize_pins_section(
    *,
    stored_width: int,
    bgcolor: int,
    labels: Sequence[int],
    components_per_grid: Sequence[int],
    component_width: int,
    index_width: int,
    num_pins_width: int,
    depth_width: int,
    cc_label_width: int,
    pins: Sequence[Iterable[tuple[int, int]]],
    cc_ids: Sequence[Iterable[int]],
    strict: bool = True,
) -> bytes:
    """Inverse of parse_pins_section with explicit records (no hidden decisions).

    strict=True raises on any field overflow (CAPE invariant). strict=False reproduces
    upstream's silent truncation and exists only to replay upstream byte streams.
    """
    if list(labels) != sorted(set(labels)):
        raise FormatError("labels must be strictly increasing")
    if len(pins) != len(labels) or len(cc_ids) != len(labels):
        raise FormatError("one pin list and one CC list per written label")
    out = bytearray()
    _put(out, bgcolor, stored_width, strict, "bgcolor")
    _put(out, len(labels), 8, strict, "num_labels")
    for lab in labels:
        _put(out, lab, stored_width, strict, "label")
    for c in components_per_grid:
        _put(out, c, component_width, strict, "components_per_grid")
    combined = _log2_width(num_pins_width) | (_log2_width(depth_width) << 2) | (_log2_width(cc_label_width) << 4)
    out.append(combined)
    for lab_pins, lab_ccs in zip(pins, cc_ids):
        ordered = sorted(lab_pins)
        _put(out, len(ordered), num_pins_width, strict, "num_pins")
        prev = 0
        for start, _depth in ordered:
            _put(out, start - prev, index_width, strict, "pin index delta")
            prev = start
        for _start, depth in ordered:
            _put(out, depth, depth_width, strict, "pin depth")
        ccs = sorted(lab_ccs)
        _put(out, len(ccs), num_pins_width, strict, "num_cc")
        prev = 0
        for c in ccs:
            _put(out, c - prev, cc_label_width, strict, "cc id delta")
            prev = c
    return bytes(out)


def predict_pins_section_bytes(
    *, stored_width: int, n_written_labels: int, num_grids: int, component_width: int,
    num_pins_width: int, index_width: int, depth_width: int, cc_label_width: int, P: int, Q: int,
) -> int:
    """Spec formula (3) with Z replaced by num_grids (== Z for the default grid size)."""
    return (stored_width + 8 + n_written_labels * stored_width + num_grids * component_width + 1
            + 2 * n_written_labels * num_pins_width + P * (index_width + depth_width) + Q * cc_label_width)


# ------------------------------------------------------- upstream selection replay

def upstream_short_pin_threshold(index_width: int, depth_width: int, cc_label_width: int) -> int:
    """labels.hpp: pins with depth < (index_width + depth_width) / cc_label_width are
    written as explicit CC lists instead of pins (integer division)."""
    return (index_width + depth_width) // cc_label_width


def upstream_background_candidates(selection: dict) -> set[int]:
    """labels.hpp find_bgcolor: most pins, then largest total depth. Remaining ties are
    broken by std::unordered_map iteration order, which is implementation-defined, so all
    tied labels are returned."""
    best = None
    tied: set[int] = set()
    for label, rec in selection.items():
        n = len(rec["x"])
        depth = int(sum(int(e) - int(s) for s, e in zip(rec["z_s"], rec["z_e"])))
        key = (n, depth)
        if best is None or key > best:
            best, tied = key, {int(label)}
        elif key == best:
            tied.add(int(label))
    return tied


def upstream_records(selection: dict, bgcolor: int, sx: int, sy: int, n_components: int,
                     index_width: int) -> dict:
    """Replay labels.hpp encode_condensed_pins on a stock pins_compute() selection."""
    written = sorted(int(k) for k in selection if int(k) != bgcolor)
    max_pins = 0
    max_depth = 0
    for lab in written:
        rec = selection[lab]
        max_pins = max(max_pins, len(rec["x"]))
        for s, e in zip(rec["z_s"], rec["z_e"]):
            max_depth = max(max_depth, int(e) - int(s))
    wn = byte_width(max_pins)
    wd = byte_width(max_depth)
    wc = byte_width(n_components)
    thr = upstream_short_pin_threshold(index_width, wd, wc)
    pins, ccs = [], []
    for lab in written:
        rec = selection[lab]
        lab_pins, lab_ccs = [], []
        offs = rec["ccid_offsets"]
        for i in range(len(rec["x"])):
            depth = int(rec["z_e"][i]) - int(rec["z_s"][i])
            if depth < thr:
                lab_ccs.extend(int(c) for c in rec["ccids"][int(offs[i]): int(offs[i + 1])])
            else:
                start = int(rec["x"][i]) + sx * (int(rec["y"][i]) + sy * int(rec["z_s"][i]))
                lab_pins.append((start, depth))
        pins.append(lab_pins)
        ccs.append(lab_ccs)
    return {"labels": written, "pins": pins, "cc_ids": ccs, "num_pins_width": wn,
            "depth_width": wd, "cc_label_width": wc, "threshold": thr,
            "required_count_width": byte_width(max([0] + [max(len(p), len(c)) for p, c in zip(pins, ccs)]))}


# ---------------------------------------------------------------- flat section

@dataclass
class FlatSection:
    uniq: list[int]
    components_per_grid: list[int]
    key_width: int
    keys: list[int]


def parse_flat_section(section: bytes, header: Header) -> FlatSection:
    n = _uint(section, 0, 8)
    wl = header.stored_data_width
    uniq = [_uint(section, 8 + i * wl, wl) for i in range(n)]
    off = 8 + n * wl
    wg = header.component_width
    comps = [_uint(section, off + i * wg, wg) for i in range(header.num_grids)]
    off += header.num_grids * wg
    kw = byte_width(n)
    if (len(section) - off) % kw:
        raise FormatError("flat key array length is not a multiple of the key width")
    keys = [_uint(section, off + i * kw, kw) for i in range((len(section) - off) // kw)]
    return FlatSection(uniq, comps, kw, keys)
