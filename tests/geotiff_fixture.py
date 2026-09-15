# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A minimal GeoTIFF writer for the tests (classic TIFF, one IFD): enough
to exercise ``georef.geotiff`` on strips and tiles, raw / Deflate /
PackBits / LZW / JPEG data, with a pixel scale + tie point and a UTM
GeoKey directory."""
from __future__ import annotations

import struct
import zlib

import numpy as np


def write_geotiff(path, rgba: np.ndarray, *, tile: int = 0,
                  compression: int = 1, predictor: int = 1,
                  origin=(500000.0, 8280000.0), scale=(0.5, 0.5),
                  epsg: int = 32718, pixel_is_point: bool = False,
                  samples: int = 4, jpeg_blobs=None, jpeg_tables=b"",
                  bo: str = "<") -> None:
    """Write ``rgba`` (H, W, 4) uint8 as a GeoTIFF. ``tile`` > 0 = tiled
    with that size, else one strip per 16 rows. ``jpeg_blobs`` (a list of
    encoded tiles) replaces the pixel encoding for compression 7."""
    h, w = rgba.shape[:2]
    px = np.ascontiguousarray(rgba[..., :samples])
    blocks = []
    if tile:
        th = tw = tile
        for ty in range(-(-h // th)):
            for tx in range(-(-w // tw)):
                blk = np.zeros((th, tw, samples), np.uint8)
                part = px[ty * th:(ty + 1) * th, tx * tw:(tx + 1) * tw]
                blk[:part.shape[0], :part.shape[1]] = part
                blocks.append(blk)
    else:
        th, tw = 16, w
        for y in range(0, h, th):
            blocks.append(px[y:y + th])
    encoded = []
    for i, blk in enumerate(blocks):
        if compression == 7:
            encoded.append(jpeg_blobs[i])
            continue
        arr = blk
        if predictor == 2:
            arr = np.diff(arr.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
        raw = arr.tobytes()
        if compression == 8:
            raw = zlib.compress(raw)
        elif compression == 32773:
            raw = _packbits(raw)
        elif compression == 5:
            raw = _lzw_encode(raw)
        encoded.append(raw)

    # ---- entries: (tag, type, values) — laid out below
    entries = [
        (256, 4, [w]), (257, 4, [h]), (258, 3, [8] * samples),
        (259, 3, [compression]), (262, 3, [2 if samples >= 3 else 1]),
        (277, 3, [samples]), (284, 3, [1]),
    ]
    if samples == 4:
        entries.append((338, 3, [2]))
    if predictor == 2:
        entries.append((317, 3, [predictor]))
    if compression == 7 and jpeg_tables:
        entries.append((347, 7, jpeg_tables))
    sx, sy = scale
    entries.append((33550, 12, [sx, sy, 0.0]))
    # The tie point names raster (0, 0): the first pixel's corner, or its
    # CENTRE when the file says PixelIsPoint.
    entries.append((33922, 12, [0.0, 0.0, 0.0, origin[0], origin[1], 0.0]))
    entries.append((34735, 3, [1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1,
                               2 if pixel_is_point else 1, 3072, 0, 1, epsg]))
    if tile:
        entries += [(322, 4, [tw]), (323, 4, [th])]
        off_tag, cnt_tag = 324, 325
    else:
        entries.append((278, 4, [th]))
        off_tag, cnt_tag = 273, 279
    entries.append((off_tag, 4, [0] * len(encoded)))        # patched below
    entries.append((cnt_tag, 4, [len(e) for e in encoded]))
    entries.sort(key=lambda e: e[0])

    def packed(typ, values):
        if typ in (2, 7):
            return bytes(values)
        fmt = {1: "B", 3: "H", 4: "I", 12: "d"}[typ]
        return struct.pack(bo + fmt * len(values), *values)

    def count_of(typ, values):
        return len(values)

    # Layout: header, IFD, out-of-line values (in entry order), blocks.
    ifd_size = 2 + len(entries) * 12 + 4
    cursor = 8 + ifd_size
    value_pos = {}
    for tag, typ, values in entries:
        data = packed(typ, values)
        if len(data) > 4:
            value_pos[tag] = cursor
            cursor += len(data) + (len(data) & 1)
    block_pos = []
    for e in encoded:
        block_pos.append(cursor)
        cursor += len(e) + (len(e) & 1)
    entries = [(t, ty, block_pos if t == off_tag else v) for t, ty, v in entries]

    out = bytearray(b"II*\x00" + struct.pack(bo + "I", 8))
    out += struct.pack(bo + "H", len(entries))
    blobs = []
    for tag, typ, values in entries:
        data = packed(typ, values)
        out += struct.pack(bo + "HHI", tag, typ, count_of(typ, values))
        if len(data) > 4:
            out += struct.pack(bo + "I", value_pos[tag])
            blobs.append(data)
        else:
            out += data.ljust(4, b"\x00")
    out += b"\x00\x00\x00\x00"
    for data in blobs:
        out += data + (b"\x00" if len(data) & 1 else b"")
    for e in encoded:
        out += e + (b"\x00" if len(e) & 1 else b"")
    with open(path, "wb") as f:
        f.write(out)


def _packbits(raw: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(raw)
    while i < n:
        run = 1
        while i + run < n and run < 128 and raw[i + run] == raw[i]:
            run += 1
        if run >= 2:
            out += bytes([257 - run, raw[i]])
            i += run
            continue
        j = i
        while (j < n and j - i < 128
               and not (j + 1 < n and raw[j] == raw[j + 1])):
            j += 1
        out += bytes([j - i - 1]) + raw[i:j]
        i = j
    return bytes(out)


def _lzw_encode(raw: bytes) -> bytes:
    """TIFF LZW (MSB-first, early change), the reference encoder."""
    out = 0
    nbits = 0
    buf = bytearray()
    table = {bytes([i]): i for i in range(256)}
    next_code = 258
    bits = 9

    def emit(code):
        nonlocal out, nbits, buf
        out = (out << bits) | code
        nbits += bits
        while nbits >= 8:
            buf.append((out >> (nbits - 8)) & 0xFF)
            nbits -= 8
        out &= (1 << nbits) - 1 if nbits else 0

    emit(256)
    w = b""
    for b in raw:
        wc = w + bytes([b])
        if wc in table:
            w = wc
            continue
        emit(table[w])
        table[wc] = next_code
        next_code += 1
        # libtiff: the encoder widens one entry AFTER the decoder does —
        # the decoder's table lags one behind ("early change").
        if next_code > (1 << bits) - 1 and bits < 12:
            bits += 1
        if next_code >= 4094:
            emit(256)
            table = {bytes([i]): i for i in range(256)}
            next_code = 258
            bits = 9
        w = bytes([b])
    if w:
        emit(table[w])
    emit(257)
    if nbits:
        buf.append((out << (8 - nbits)) & 0xFF)
    return bytes(buf)
