#!/usr/bin/env python3

import argparse
import sys


ESC = b"\x1b"
GS = b"\x1d"


def receipt() -> bytes:
    data = bytearray()

    # Initialize printer
    data += ESC + b"@"

    # Center align
    data += ESC + b"a" + b"\x01"
    data += b"CASHINO PTP-III\n"

    # Double height + width
    data += GS + b"!" + b"\x11"
    data += b"TEST PRINT\n"

    # Normal text
    data += GS + b"!" + b"\x00"
    data += b"\n"

    # Left align
    data += ESC + b"a" + b"\x00"
    data += b"Hello from Python\n"
    data += b"Printing through /dev/usb/lp0\n"
    data += b"------------------------\n"
    data += b"Item             NOK\n"
    data += b"Coffee          25.00\n"
    data += b"Printer test     0.00\n"
    data += b"------------------------\n"
    data += b"\n\n\n"

    # Cut. Portable printers may ignore this.
    data += GS + b"V" + b"\x00"

    return bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device",
        default="/dev/usb/lp0",
        help="Printer device, default: /dev/usb/lp0",
    )
    args = parser.parse_args()

    try:
        with open(args.device, "wb") as printer:
            printer.write(receipt())
            printer.flush()

        print(f"Printed to {args.device}")
        return 0

    except PermissionError:
        print(f"Permission denied: {args.device}", file=sys.stderr)
        print("Try: sudo chmod a+rw /dev/usb/lp0", file=sys.stderr)
        print("Or add yourself to the lp group.", file=sys.stderr)
        return 1

    except FileNotFoundError:
        print(f"Printer device not found: {args.device}", file=sys.stderr)
        print("Check with: ls -l /dev/usb/lp*", file=sys.stderr)
        return 1

    except OSError as e:
        print(f"Printer error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())