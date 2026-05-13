import io
import textwrap
import threading

from PIL import Image

from src.config import PRINTER_DEVICE

ESC = b"\x1b"
GS = b"\x1d"

PRINTER_WIDTH = 48
PRINTER_IMAGE_WIDTH = 576  # 80mm paper @ 203 dpi

_print_lock = threading.Lock()


class PrintService:
    def __init__(self, device: str = None):
        self.device = device or PRINTER_DEVICE

    def print_content(self, lines: list, title: str = None, footer: str = None):
        data = self._build(lines=lines, title=title, footer=footer)
        self._write(data)

    def _build(self, lines: list, title: str = None, footer: str = None) -> bytes:
        data = bytearray()

        # Initialize printer
        data += ESC + b"@"

        if title:
            # Center align, bold
            data += ESC + b"a" + b"\x01"
            data += ESC + b"E" + b"\x01"
            for line in textwrap.wrap(title, PRINTER_WIDTH):
                data += self._encode(line) + b"\n"
            data += ESC + b"E" + b"\x00"
            data += self._encode("-" * PRINTER_WIDTH) + b"\n"

        # Left align, normal size
        data += ESC + b"a" + b"\x00"
        data += GS + b"!" + b"\x00"

        for line in lines:
            data += self._encode(line) + b"\n"

        if footer:
            data += b"\n"
            data += self._encode("-" * PRINTER_WIDTH) + b"\n"
            data += self._encode(footer[:PRINTER_WIDTH]) + b"\n"

        data += b"\n\n\n\n\n\n"

        # Cut
        data += GS + b"V" + b"\x00"

        return bytes(data)

    def _write(self, data: bytes):
        with _print_lock:
            with open(self.device, "wb") as printer:
                printer.write(data)
                printer.flush()

    def print_image(self, image_bytes: bytes):
        data = self._build_image(image_bytes)
        self._write(data)

    def _build_image(self, image_bytes: bytes) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.rotate(90, expand=True)
        img = img.convert("L")  # grayscale
        aspect = img.height / img.width
        new_height = int(PRINTER_IMAGE_WIDTH * aspect)
        img = img.resize((PRINTER_IMAGE_WIDTH, new_height), Image.LANCZOS)
        img = img.convert("1")  # 1-bit with Floyd-Steinberg dither

        width_bytes = PRINTER_IMAGE_WIDTH // 8  # 72
        height = img.height

        data = bytearray()
        data += ESC + b"@"  # initialize printer
        data += ESC + b"a" + b"\x01"  # center align

        # GS v 0 — raster bit image
        # Format: GS 0x76 0x30 m xL xH yL yH [data]
        # m=0 normal density, width in bytes, height in dots
        data += GS + b"\x76\x30\x00"
        data += bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
        data += bytes([height & 0xFF, (height >> 8) & 0xFF])

        pixels = img.load()
        for y in range(height):
            row = bytearray(width_bytes)
            for x in range(PRINTER_IMAGE_WIDTH):
                if pixels[x, y] == 0:  # black pixel
                    row[x // 8] |= 0x80 >> (x % 8)
            data += row

        data += b"\n\n\n\n\n\n"
        data += GS + b"V" + b"\x00"  # cut

        return bytes(data)

    @staticmethod
    def _encode(text: str) -> bytes:
        return text.encode("latin-1", errors="replace")
