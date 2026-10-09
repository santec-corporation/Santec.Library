"""Connect to a TSL and read its power and wavelength.

    python tsl_connection.py
"""

from __future__ import annotations

import sys

from santec_library import Library


def main() -> int:
    with Library() as library:
        devices = library.list_devices()
        tsl = next((device for device in devices if "TSL" in device.product_name), None)
        if tsl is None:
            print("TSL not found", file=sys.stderr)
            return 1

        print(f"TSL: {tsl}")
        if not library.connect(tsl):
            print("connection failed; see the log", file=sys.stderr)
            return 1

        library.set_tsl_power(0.1)
        library.set_tsl_wavelength(1355.5)

        print(f"power      : {library.get_tsl_power()}")
        print(f"wavelength : {library.get_tsl_wavelength()}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
