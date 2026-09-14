# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""GeoTIFF orthomosaics as georeferenced reference images (Track G).

A drone survey's orthophoto (WebODM's ``odm_orthophoto.tif``, a QGIS
export) knows exactly where it lies: the TIFF carries an affine pixel →
map transform (ModelPixelScale + ModelTiepoint, or ModelTransformation)
and the CRS in the GeoKey directory. This module reads that header and
decodes the pixels **without GDAL, rasterio or Pillow** — the project's
stance is a hand-ported UTM and Qt for images — so the import places the
picture on the scene's datum at its true size and orientation, and the
model is traced over the real ground.

Decoding covers what orthomosaic exporters actually write: 8-bit RGB /
RGBA (an extra unassociated alpha for the no-data fringe), tiled or
stripped, contiguous or planar, uncompressed / Deflate / PackBits / LZW,
and JPEG-in-TIFF (each tile a JPEG stream sharing the JPEGTables tag,
decoded by Qt). Classic and BigTIFF headers. Anything else — 16-bit
elevation models, float DSMs, palette images — is reported as
unsupported with the reason, never guessed at.

Large mosaics (a 15 000 × 11 000 ODM export is 690 MB of pixels) are
reduced while they stream in, band of rows by band of rows, to the
texture ceiling the caller asks for, so the peak memory is one band plus
the reduced picture — never the full-resolution image.
"""
from __future__ import annotations

import math
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# TIFF tags
_IMAGE_WIDTH = 256
_IMAGE_LENGTH = 257
_BITS_PER_SAMPLE = 258
_COMPRESSION = 259
_PHOTOMETRIC = 262
_STRIP_OFFSETS = 273
_SAMPLES_PER_PIXEL = 277
_ROWS_PER_STRIP = 278
_STRIP_BYTE_COUNTS = 279
_PLANAR_CONFIG = 284
_PREDICTOR = 317
_COLOR_MAP = 320
_TILE_WIDTH = 322
_TILE_LENGTH = 323
_TILE_OFFSETS = 324
_TILE_BYTE_COUNTS = 325
_EXTRA_SAMPLES = 338
_SAMPLE_FORMAT = 339
_JPEG_TABLES = 347
_MODEL_PIXEL_SCALE = 33550
_MODEL_TIEPOINT = 33922
_MODEL_TRANSFORMATION = 34264
_GEO_KEY_DIRECTORY = 34735
_GEO_DOUBLE_PARAMS = 34736
_GEO_ASCII_PARAMS = 34737
_GDAL_NODATA = 42113

# GeoKeys
_GT_MODEL_TYPE = 1024          # 1 projected, 2 geographic
_GT_RASTER_TYPE = 1025         # 1 PixelIsArea, 2 PixelIsPoint
_GT_CITATION = 1026
_GEOGRAPHIC_TYPE = 2048
_PROJECTED_CS_TYPE = 3072
_PCS_CITATION = 3073

# Compression schemes
COMPRESSION_NONE = 1
COMPRESSION_LZW = 5
COMPRESSION_JPEG = 7
COMPRESSION_DEFLATE = 8
COMPRESSION_PACKBITS = 32773
COMPRESSION_DEFLATE_OLD = 32946

_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8,
              11: 4, 12: 8, 16: 8, 17: 8, 18: 8}
_TYPE_FMT = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f",
             12: "d", 16: "Q", 17: "q", 18: "Q"}


class GeoTiffError(ValueError):
    """The file is not a TIFF this reader can place or decode; the message
    says which part (shown to the user as is)."""


@dataclass
class GeoTiffInfo:
    """Header of a GeoTIFF: the raster layout plus its map placement."""
    path: Path
    width: int
    height: int
    samples: int
    bits: tuple
    compression: int
    photometric: int
    planar: int
    tiled: bool
    tile_w: int
    tile_h: int
    offsets: tuple
    bytecounts: tuple
    predictor: int = 1
    jpeg_tables: bytes = b""
    extra_samples: tuple = ()
    sample_format: tuple = ()
    big: bool = False
    byte_order: str = "<"
    #: Pixel → map affine ``(a, b, c, d, e, f)``: X = a·col + b·row + c,
    #: Y = d·col + e·row + f, for the pixel's top-left CORNER (PixelIsPoint
    #: headers are shifted half a pixel here, so callers never care).
    transform: Optional[tuple] = None
    #: EPSG of the map CRS when the file states one.
    epsg: Optional[int] = None
    #: UTM zone / hemisphere the map coordinates are in, or ``None`` when
    #: the CRS is geographic (``geographic=True``: X = lon, Y = lat) or unknown.
    zone: Optional[int] = None
    northern: Optional[bool] = None
    geographic: bool = False
    citation: str = ""
    nodata: Optional[str] = None

    # ---- Placement ----------------------------------------------------------
    @property
    def georeferenced(self) -> bool:
        return self.transform is not None and (self.geographic
                                               or self.zone is not None)

    def pixel_to_map(self, col: float, row: float) -> tuple[float, float]:
        a, b, c, d, e, f = self.transform
        return a * col + b * row + c, d * col + e * row + f

    def corners_geodetic(self) -> list[tuple[float, float]]:
        """``(lat, lon)`` of the picture's corners, in the order the image
        plane wants them: bottom-left, bottom-right, top-right, top-left
        (the picture's own bottom row is its LAST pixel row)."""
        from georef.datum import utm_inverse
        px = [(0.0, float(self.height)), (float(self.width), float(self.height)),
              (float(self.width), 0.0), (0.0, 0.0)]
        out = []
        for col, row in px:
            x, y = self.pixel_to_map(col, row)
            if self.geographic:
                out.append((y, x))
            else:
                out.append(utm_inverse(x, y, self.zone, bool(self.northern)))
        return out

    def ground_size(self) -> tuple[float, float]:
        """Approximate metres covered (width, height) — the pixel scale times
        the raster size; for a geographic CRS scaled by the latitude."""
        a, b, c, d, e, f = self.transform
        w = math.hypot(a, d) * self.width
        h = math.hypot(b, e) * self.height
        if self.geographic:
            lat = math.radians(f + e * self.height / 2.0)
            w *= 111_320.0 * math.cos(lat)
            h *= 110_540.0
        return w, h


# ---- Header ----------------------------------------------------------------
def read_info(path) -> GeoTiffInfo:
    """Parse the first IFD of a TIFF/BigTIFF and its GeoTIFF placement.
    Raises :class:`GeoTiffError` for a file that is not a TIFF."""
    path = Path(path)
    with open(path, "rb") as f:
        head = f.read(16)
        if len(head) < 8 or head[:2] not in (b"II", b"MM"):
            raise GeoTiffError(f"{path.name}: not a TIFF file")
        bo = "<" if head[:2] == b"II" else ">"
        magic = struct.unpack(bo + "H", head[2:4])[0]
        if magic == 42:
            big = False
            ifd = struct.unpack(bo + "I", head[4:8])[0]
        elif magic == 43:
            big = True
            ifd = struct.unpack(bo + "Q", head[8:16])[0]
        else:
            raise GeoTiffError(f"{path.name}: not a TIFF file")
        tags = _read_ifd(f, ifd, bo, big)

        def get(tag, default=None):
            return tags[tag] if tag in tags else default

        width = get(_IMAGE_WIDTH)
        height = get(_IMAGE_LENGTH)
        if not width or not height:
            raise GeoTiffError(f"{path.name}: the TIFF has no image size")
        width, height = int(width[0]), int(height[0])
        samples = int(get(_SAMPLES_PER_PIXEL, (1,))[0])
        bits = tuple(int(b) for b in get(_BITS_PER_SAMPLE, (1,)))
        if len(bits) < samples:
            bits = bits + (bits[-1],) * (samples - len(bits))
        compression = int(get(_COMPRESSION, (1,))[0])
        photometric = int(get(_PHOTOMETRIC, (2 if samples >= 3 else 1,))[0])
        planar = int(get(_PLANAR_CONFIG, (1,))[0])
        tiled = _TILE_OFFSETS in tags
        if tiled:
            tile_w = int(get(_TILE_WIDTH)[0])
            tile_h = int(get(_TILE_LENGTH)[0])
            offsets = tuple(get(_TILE_OFFSETS))
            counts = tuple(get(_TILE_BYTE_COUNTS, ()))
        else:
            if _STRIP_OFFSETS not in tags:
                raise GeoTiffError(f"{path.name}: the TIFF has no image data")
            tile_w = width
            rps = get(_ROWS_PER_STRIP, (height,))[0]
            tile_h = int(min(int(rps), height)) if rps else height
            offsets = tuple(get(_STRIP_OFFSETS))
            counts = tuple(get(_STRIP_BYTE_COUNTS, ()))
        if not counts:
            raise GeoTiffError(f"{path.name}: the TIFF has no byte counts")
        jpeg_tables = bytes(get(_JPEG_TABLES, b"")) if compression == COMPRESSION_JPEG else b""
        info = GeoTiffInfo(
            path=path, width=width, height=height, samples=samples, bits=bits,
            compression=compression, photometric=photometric, planar=planar,
            tiled=tiled, tile_w=tile_w, tile_h=tile_h, offsets=offsets,
            bytecounts=counts, predictor=int(get(_PREDICTOR, (1,))[0]),
            jpeg_tables=jpeg_tables,
            extra_samples=tuple(int(x) for x in get(_EXTRA_SAMPLES, ())),
            sample_format=tuple(int(x) for x in get(_SAMPLE_FORMAT, ())),
            big=big, byte_order=bo)
        nodata = get(_GDAL_NODATA)
        if nodata is not None:
            info.nodata = nodata if isinstance(nodata, str) else str(nodata)
        _read_placement(info, tags)
    return info


def _read_ifd(f, offset: int, bo: str, big: bool) -> dict:
    """The tag → value map of one IFD (values decoded; ASCII as str, bytes
    for UNDEFINED, tuples otherwise)."""
    f.seek(offset)
    n = struct.unpack(bo + ("Q" if big else "H"), f.read(8 if big else 2))[0]
    esize = 20 if big else 12
    raw = f.read(n * esize)
    entries = []
    for i in range(n):
        e = raw[i * esize:(i + 1) * esize]
        if big:
            tag, typ, cnt = struct.unpack(bo + "HHQ", e[:12])
            val = e[12:20]
        else:
            tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
            val = e[8:12]
        entries.append((tag, typ, cnt, val))
    tags: dict = {}
    inline = 8 if big else 4
    for tag, typ, cnt, val in entries:
        size = _TYPE_SIZE.get(typ)
        if size is None:
            continue
        total = size * cnt
        if total <= inline:
            data = val[:total]
        else:
            off = struct.unpack(bo + ("Q" if big else "I"), val)[0]
            f.seek(off)
            data = f.read(total)
            if len(data) < total:
                continue
        if typ == 2:                                   # ASCII
            tags[tag] = data.decode("latin-1").rstrip("\x00")
        elif typ == 7:                                 # UNDEFINED
            tags[tag] = data
        elif typ in (5, 10):                           # RATIONAL
            fmt = "I" if typ == 5 else "i"
            nums = struct.unpack(bo + fmt * (2 * cnt), data)
            tags[tag] = tuple(nums[i] / nums[i + 1] if nums[i + 1] else 0.0
                              for i in range(0, 2 * cnt, 2))
        else:
            tags[tag] = struct.unpack(bo + _TYPE_FMT[typ] * cnt, data)
    return tags


_UTM_RE = re.compile(r"UTM\s*zone\s*(\d{1,2})\s*([NS])", re.IGNORECASE)


def _read_placement(info: GeoTiffInfo, tags: dict) -> None:
    """The affine transform and the CRS from the GeoTIFF tags."""
    scale = tags.get(_MODEL_PIXEL_SCALE)
    tie = tags.get(_MODEL_TIEPOINT)
    matrix = tags.get(_MODEL_TRANSFORMATION)
    transform = None
    if matrix is not None and len(matrix) >= 16:
        m = matrix
        transform = (m[0], m[1], m[3], m[4], m[5], m[7])
    elif scale is not None and tie is not None and len(tie) >= 6:
        sx, sy = float(scale[0]), float(scale[1])
        i, j, _k, x, y, _z = (float(v) for v in tie[:6])
        # Map X of the raster's (0, 0) corner from the tie point (i, j).
        transform = (sx, 0.0, x - i * sx, 0.0, -sy, y + j * sy)
    keys = tags.get(_GEO_KEY_DIRECTORY)
    ascii_params = tags.get(_GEO_ASCII_PARAMS, "") or ""
    model_type = None
    raster_type = 1
    epsg = None
    geographic_type = None
    citation = ""
    if keys and len(keys) >= 4:
        n = int(keys[3])
        for k in range(n):
            base = 4 + 4 * k
            if base + 3 >= len(keys):
                break
            key, loc, count, value = (int(v) for v in keys[base:base + 4])
            if key == _GT_MODEL_TYPE:
                model_type = value
            elif key == _GT_RASTER_TYPE:
                raster_type = value
            elif key == _PROJECTED_CS_TYPE:
                epsg = value
            elif key == _GEOGRAPHIC_TYPE:
                geographic_type = value
            elif key in (_GT_CITATION, _PCS_CITATION) and loc == _GEO_ASCII_PARAMS:
                citation += ascii_params[value:value + count].rstrip("|") + "|"
    info.citation = citation.strip("|")
    info.epsg = epsg if epsg and epsg != 32767 else None
    if transform is not None and raster_type == 2:
        # PixelIsPoint: the tie point names the pixel CENTRE; the image plane
        # wants the corner, half a pixel up-left.
        a, b, c, d, e, f = transform
        transform = (a, b, c - 0.5 * a - 0.5 * b, d, e, f - 0.5 * d - 0.5 * e)
    info.transform = transform
    # UTM zone: from the EPSG when it is a WGS84 UTM code, else from the
    # citation text ("WGS 84 / UTM zone 18S"), else geographic lat/lon.
    zone = northern = None
    if epsg and 32601 <= epsg <= 32660:
        zone, northern = epsg - 32600, True
    elif epsg and 32701 <= epsg <= 32760:
        zone, northern = epsg - 32700, False
    else:
        m = _UTM_RE.search(ascii_params)
        if m:
            zone, northern = int(m.group(1)), m.group(2).upper() == "N"
    if zone is not None:
        info.zone, info.northern = zone, northern
    elif model_type == 2 or (epsg is None and geographic_type is not None
                             and transform is not None
                             and abs(transform[2]) <= 180.0
                             and abs(transform[5]) <= 90.0):
        info.geographic = True


# ---- Pixels ----------------------------------------------------------------
def unsupported_reason(info: GeoTiffInfo) -> Optional[str]:
    """Why this reader cannot decode the raster, or ``None`` when it can."""
    if info.compression not in (COMPRESSION_NONE, COMPRESSION_LZW,
                                COMPRESSION_JPEG, COMPRESSION_DEFLATE,
                                COMPRESSION_PACKBITS, COMPRESSION_DEFLATE_OLD):
        return f"compression scheme {info.compression}"
    if any(b not in (8, 16) for b in info.bits[:info.samples]):
        return f"{info.bits[0]}-bit samples"
    if info.sample_format and any(sf not in (1, 4) for sf in info.sample_format[:info.samples]):
        return "floating-point samples (an elevation model, not a picture)"
    if info.photometric not in (0, 1, 2, 6):
        return f"photometric interpretation {info.photometric}"
    if info.samples not in (1, 2, 3, 4) and info.photometric != 2:
        return f"{info.samples} samples per pixel"
    if info.compression == COMPRESSION_JPEG and (info.bits[0] != 8
                                                 or info.planar != 1):
        return "JPEG-compressed samples in this layout"
    return None


def read_rgba(info: GeoTiffInfo, max_px: int = 8192,
              progress: Optional[Callable[[float], bool]] = None
              ) -> tuple[np.ndarray, int]:
    """Decode the raster to an ``(H', W', 4)`` uint8 RGBA array reduced by an
    integer factor so its longer side fits ``max_px``; returns
    ``(array, factor)``. ``progress(fraction)`` is called per band of rows
    and may return ``False`` to abort (raises :class:`GeoTiffError`)."""
    reason = unsupported_reason(info)
    if reason:
        raise GeoTiffError(f"{info.path.name}: {reason} is not supported")
    factor = 1
    while max(info.width, info.height) / factor > max_px:
        factor *= 2
    if info.tiled and factor > 1:
        while info.tile_w % factor or info.tile_h % factor:
            factor *= 2               # a tile reduces cleanly or not at all
    out_w = -(-info.width // factor)
    out_h = -(-info.height // factor)
    out = np.zeros((out_h, out_w, 4), dtype=np.uint8)
    reducer = _RowReducer(out, factor, info.width)
    bands = _band_count(info)
    if _parallel_ok(info, factor, bands):
        # LZW is pure Python and sequential per tile: a 40 000-px mosaic
        # is minutes on one core. Tiles are independent, so a tile row per
        # worker across the cores — each returns its band already reduced.
        import os
        from concurrent.futures import ProcessPoolExecutor
        from multiprocessing import get_context
        workers = max(2, min(8, (os.cpu_count() or 2)))
        with ProcessPoolExecutor(max_workers=workers,
                                 mp_context=get_context("fork")) as pool:
            futures = [pool.submit(_reduced_band, info, b, factor)
                       for b in range(bands)]
            for band_index, fut in enumerate(futures):
                reducer.push(fut.result(), reduced=True)
                if progress is not None and not progress(
                        (band_index + 1) / bands):
                    for f_ in futures:
                        f_.cancel()
                    raise GeoTiffError("cancelled")
        return out, factor
    with open(info.path, "rb") as f:
        for band_index in range(bands):
            rows = _decode_band(f, info, band_index)
            reducer.push(rows)
            if progress is not None and not progress((band_index + 1) / bands):
                raise GeoTiffError("cancelled")
    reducer.finish()
    return out, factor


def _parallel_ok(info: GeoTiffInfo, factor: int, bands: int) -> bool:
    """Whether the band decode goes to a process pool: only the LZW
    scheme is slow enough to matter, only tiled files reduce a band
    without a carry, only POSIX forks cheaply (a frozen Windows build
    would re-launch the app per worker), and only when there is enough
    work to pay for the workers."""
    import os
    return (info.compression == COMPRESSION_LZW and info.tiled
            and info.tile_h % factor == 0 and bands >= 8
            and os.name == "posix" and sum(info.bytecounts) > 8_000_000)


def _reduced_band(info: GeoTiffInfo, band: int, factor: int) -> np.ndarray:
    """Worker: one tile row decoded and box-reduced (``factor`` divides the
    tile height, so the band is self-contained)."""
    with open(info.path, "rb") as f:
        rows = _decode_band(f, info, band)
    if factor == 1:
        return rows
    h, w, c = rows.shape
    pad_h = (-h) % factor                 # the last band is shorter
    pad_w = (-w) % factor
    if pad_h or pad_w:
        rows = np.pad(rows, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
        h, w = rows.shape[:2]
    block = rows.reshape(h // factor, factor, w // factor, factor, c).astype(np.uint16)
    return (block.sum(axis=(1, 3)) // (factor * factor)).astype(np.uint8)


def _band_count(info: GeoTiffInfo) -> int:
    return -(-info.height // info.tile_h)


def _decode_band(f, info: GeoTiffInfo, band: int) -> np.ndarray:
    """Full-resolution rows ``[band·tile_h, …)`` as an ``(rows, W, 4)``
    uint8 RGBA array."""
    y0 = band * info.tile_h
    rows = min(info.tile_h, info.height - y0)
    planes = info.samples if info.planar == 2 else 1
    per_plane = 1 if info.planar == 2 else info.samples
    if info.tiled:
        tiles_x = -(-info.width // info.tile_w)
        tiles_y = -(-info.height // info.tile_h)
        per_plane_tiles = tiles_x * tiles_y
    else:
        tiles_x = 1
        per_plane_tiles = -(-info.height // info.tile_h)
    raw = np.empty((rows, info.width, info.samples), dtype=np.uint8)
    for plane in range(planes):
        for tx in range(tiles_x):
            index = plane * per_plane_tiles + band * tiles_x + tx
            if index >= len(info.offsets):
                continue
            f.seek(info.offsets[index])
            data = f.read(info.bytecounts[index])
            x0 = tx * info.tile_w
            cols = min(info.tile_w, info.width - x0)
            block = _decode_block(data, info, per_plane)
            block = block[:rows, :cols]
            if info.planar == 2:
                raw[:, x0:x0 + cols, plane] = block[..., 0]
            else:
                raw[:, x0:x0 + cols, :] = block
    return _to_rgba(raw, info)


def _decode_block(data: bytes, info: GeoTiffInfo, samples: int) -> np.ndarray:
    """One tile / strip → ``(tile_h, tile_w, samples)`` uint8 (16-bit data
    is taken down to its high byte)."""
    th, tw = info.tile_h, info.tile_w
    comp = info.compression
    if comp == COMPRESSION_JPEG:
        return _decode_jpeg_block(data, info, samples)
    if comp in (COMPRESSION_DEFLATE, COMPRESSION_DEFLATE_OLD):
        data = zlib.decompress(data)
    elif comp == COMPRESSION_PACKBITS:
        data = _unpackbits(data)
    elif comp == COMPRESSION_LZW:
        data = _lzw_decode(data)
    bits = info.bits[0]
    if bits == 16:
        arr = np.frombuffer(data, dtype=info.byte_order + "u2")
        need = th * tw * samples
        arr = np.pad(arr, (0, max(0, need - arr.size)))[:need]
        arr = arr.reshape(th, tw, samples)
        if info.predictor == 2:
            arr = np.cumsum(arr, axis=1, dtype=np.uint16)
        return (arr >> 8).astype(np.uint8)
    arr = np.frombuffer(data, dtype=np.uint8)
    need = th * tw * samples
    if arr.size < need:
        arr = np.pad(arr, (0, need - arr.size))
    arr = arr[:need].reshape(th, tw, samples)
    if info.predictor == 2:
        arr = np.cumsum(arr, axis=1, dtype=np.uint8)
    return arr


def _decode_jpeg_block(data: bytes, info: GeoTiffInfo, samples: int) -> np.ndarray:
    """A JPEG-in-TIFF tile via Qt. The tile stream omits the quantisation /
    Huffman tables, which live once in the JPEGTables tag: splice them in
    (tables minus their EOI, tile minus its SOI). A 4-sample tile comes
    back from Qt as CMYK8888 with every byte INVERTED against the raw
    samples (the Adobe convention libjpeg applies to any 4-component
    stream) — undoing that gives RGBA exactly; verified against a GDAL
    orthophoto whose no-data fringe reads alpha 0 only after the flip."""
    from PySide6.QtGui import QImage
    tables = info.jpeg_tables
    if tables and data[:2] == b"\xff\xd8" and tables[-2:] == b"\xff\xd9":
        data = tables[:-2] + data[2:]
    img = QImage.fromData(data, "JPEG")
    th, tw = info.tile_h, info.tile_w
    out = np.zeros((th, tw, samples), dtype=np.uint8)
    if img.isNull():
        return out
    h, w = min(img.height(), th), min(img.width(), tw)
    if img.format() == QImage.Format_CMYK8888:
        buf = np.frombuffer(img.constBits(), dtype=np.uint8)
        px = buf.reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4]
        px = 255 - px.reshape(img.height(), img.width(), 4)
        out[:h, :w, :min(samples, 4)] = px[:h, :w, :min(samples, 4)]
        return out
    if img.format() != QImage.Format_RGBA8888:
        img = img.convertToFormat(QImage.Format_RGBA8888)
    buf = np.frombuffer(img.constBits(), dtype=np.uint8)
    px = buf.reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4]
    px = px.reshape(img.height(), img.width(), 4)
    if samples >= 3:
        out[:h, :w, :3] = px[:h, :w, :3]
        if samples == 4:
            out[:h, :w, 3] = 255
    else:
        out[:h, :w, 0] = px[:h, :w, 0]
    return out


def _to_rgba(raw: np.ndarray, info: GeoTiffInfo) -> np.ndarray:
    """Samples → RGBA: grey replicated, RGB gets an opaque alpha, a fourth
    sample is the alpha (both associated and unassociated read the same
    for a nodata fringe), WhiteIsZero inverted."""
    rows, width, samples = raw.shape
    rgba = np.empty((rows, width, 4), dtype=np.uint8)
    if samples == 1 or (samples == 2 and info.photometric in (0, 1)):
        grey = raw[..., 0]
        if info.photometric == 0:
            grey = 255 - grey
        rgba[..., 0] = grey
        rgba[..., 1] = grey
        rgba[..., 2] = grey
        rgba[..., 3] = raw[..., 1] if samples == 2 else 255
        return rgba
    rgba[..., :3] = raw[..., :3]
    if samples >= 4:
        rgba[..., 3] = raw[..., 3]
    else:
        rgba[..., 3] = 255
    return rgba


class _RowReducer:
    """Streams full-resolution row bands into a picture reduced by an
    integer factor (box average), carrying the leftover rows between
    bands so strips of any height reduce cleanly."""

    def __init__(self, out: np.ndarray, factor: int, width: int) -> None:
        self.out = out
        self.k = factor
        self.width = width
        self.row = 0                      # next OUTPUT row to fill
        self.carry: Optional[np.ndarray] = None

    def push(self, rows: np.ndarray, reduced: bool = False) -> None:
        k = self.k
        if k == 1 or reduced:
            n = rows.shape[0]
            self.out[self.row:self.row + n, :rows.shape[1]] = rows
            self.row += n
            return
        if self.carry is not None:
            rows = np.concatenate([self.carry, rows], axis=0)
            self.carry = None
        full = (rows.shape[0] // k) * k
        if full:
            self._emit(rows[:full])
        if rows.shape[0] > full:
            self.carry = rows[full:].copy()

    def finish(self) -> None:
        if self.carry is not None and self.carry.shape[0]:
            self._emit(self.carry, partial=True)
            self.carry = None

    def _emit(self, rows: np.ndarray, partial: bool = False) -> None:
        k = self.k
        h, w, c = rows.shape
        pad_h = (-h) % k
        pad_w = (-w) % k
        if pad_h or pad_w:
            rows = np.pad(rows, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
            h, w = rows.shape[:2]
        block = rows.reshape(h // k, k, w // k, k, c).astype(np.uint16)
        mean = block.sum(axis=(1, 3)) // (k * k)
        n = mean.shape[0]
        cols = min(mean.shape[1], self.out.shape[1])
        self.out[self.row:self.row + n, :cols] = mean[:, :cols].astype(np.uint8)
        self.row += n


def _unpackbits(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        h = data[i]
        i += 1
        if h < 128:
            out += data[i:i + h + 1]
            i += h + 1
        elif h > 128:
            if i < n:
                out += bytes([data[i]]) * (257 - h)
            i += 1
    return bytes(out)


def _lzw_decode(data: bytes) -> bytes:
    """TIFF LZW (MSB-first codes, early change), the classic table
    decoder. Pure Python: fine for a tile, slow for a whole gigapixel
    strip — but LZW orthophotos are tiled in practice."""
    out = bytearray()
    table: list[bytes] = []
    bits = 9
    prev: Optional[bytes] = None
    acc = 0
    nacc = 0
    pos = 0
    n = len(data)

    def reset():
        nonlocal table, bits
        table = [bytes([i]) for i in range(256)] + [b"", b""]
        bits = 9

    reset()
    while True:
        while nacc < bits and pos < n:
            acc = (acc << 8) | data[pos]
            pos += 1
            nacc += 8
        if nacc < bits:
            break
        code = (acc >> (nacc - bits)) & ((1 << bits) - 1)
        nacc -= bits
        acc &= (1 << nacc) - 1            # keep the accumulator small
        if code == 256:
            reset()
            prev = None
            continue
        if code == 257:
            break
        if code < len(table):
            entry = table[code]
        elif prev is not None and code == len(table):
            entry = prev + prev[:1]
        else:
            break                       # corrupt stream: keep what we have
        out += entry
        if prev is not None:
            table.append(prev + entry[:1])
        prev = entry
        if len(table) + 1 >= (1 << bits) and bits < 12:
            bits += 1
    return bytes(out)


# ---- Convenience -------------------------------------------------------------
def rgba_to_qimage(rgba: np.ndarray):
    """An ``(H, W, 4)`` uint8 RGBA array as a detached ``QImage``."""
    from PySide6.QtGui import QImage
    h, w = rgba.shape[:2]
    buf = np.ascontiguousarray(rgba)
    return QImage(buf.data, w, h, w * 4, QImage.Format_RGBA8888).copy()


def describe(info: GeoTiffInfo) -> str:
    """One line for the status bar / log: size, scheme and placement."""
    comp = {1: "raw", 5: "LZW", 7: "JPEG", 8: "Deflate", 32773: "PackBits",
            32946: "Deflate"}.get(info.compression, str(info.compression))
    where = (f"UTM {info.zone}{'N' if info.northern else 'S'}"
             if info.zone else ("lat/lon" if info.geographic else "no CRS"))
    return (f"{info.width}×{info.height} px, {info.samples}×{info.bits[0]} bit, "
            f"{comp}, {'tiled' if info.tiled else 'strips'}, {where}")
