"""Generate the simple Campo app monogram without third-party packages."""
import struct
import zlib
from pathlib import Path


def chunk(kind, body):
    return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)


for size in (192, 512):
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            xx, yy = x * 192 / size, y * 192 / size
            mark = (66 <= xx <= 82 and 53 <= yy <= 139) or (66 <= xx <= 129 and (53 <= yy <= 69 or 123 <= yy <= 139)) or ((xx-146)**2 + (yy-131)**2 <= 8**2)
            pixels.extend((184, 225, 132) if mark else (20, 46, 41))
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(pixels))) + chunk(b'IEND', b'')
    (Path(__file__).parent / 'public' / f'icon-{size}.png').write_bytes(data)
