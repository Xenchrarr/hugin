from src.config import PRINTER_DEVICE

ESC = b"\x1b"
GS = b"\x1d"

PRINTER_WIDTH = 48


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
            data += self._encode(title[:PRINTER_WIDTH]) + b"\n"
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
        with open(self.device, "wb") as printer:
            printer.write(data)
            printer.flush()

    @staticmethod
    def _encode(text: str) -> bytes:
        return text.encode("latin-1", errors="replace")
