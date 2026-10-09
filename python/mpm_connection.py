"""Connect to an MPM and read its information and channel powers.

    python mpm_connection.py

Module and channel indices are zero-based, as the header documents.
"""

from __future__ import annotations

import sys

from santec_library import Library


def main() -> int:
    with Library() as library:
        devices = library.list_devices()
        mpm = next((device for device in devices if "MPM" in device.product_name), None)
        if mpm is None:
            print("MPM not found", file=sys.stderr)
            return 1

        print(f"MPM: {mpm}")
        if not library.connect(mpm):
            print("connection failed; see the log", file=sys.stderr)
            return 1

        print(library.mpm_info())
        print(f"module 0 powers  : {library.mpm_module_power(0)}")
        print(f"module 0 channel 0: {library.mpm_channel_power(0, 0)}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
