"""Generate the three toolbar icons (pill: red half, green half). Run: python make_icons.py"""
import struct
import zlib
from pathlib import Path


def png(n: int, path: Path) -> None:
    rows = []
    for y in range(n):
        row = b"\x00"
        for x in range(n):
            cx, cy = x - n / 2 + 0.5, y - n / 2 + 0.5
            inside = cx * cx + cy * cy < (n / 2) ** 2
            c = (255, 93, 108) if inside and cx < 0 else (59, 240, 126) if inside else (5, 8, 6)
            row += bytes(c)
        rows.append(row)

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


for size in (16, 48, 128):
    png(size, Path(__file__).parent / "icons" / f"{size}.png")
