# -*- coding: utf-8 -*-
"""Smallest useful run: find the instruments, take one measurement, print the IL.

Usage
    python quickstart.py --list-only
    python quickstart.py --dll ..\\..\\lib\\win-x64\\Santec.Library.dll
    python quickstart.py --start 1480 --stop 1640 --step 0.01 --power 0 --speed 100

It prompts between the reference and the DUT unless you pass --yes, because the
fiber has to be moved in between.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Running from a checkout: the package sits one directory up. Install it with
# `pip install ..` and this bootstrap can go away.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from santec_library import Library, LibraryNotFound, AbiMismatch  # noqa: E402
from santec_library.results import parse  # noqa: E402


def pick(devices, *fragments):
    """First device whose product name contains one of the fragments."""
    for device in devices:
        name = device.product_name.upper()
        if any(fragment.upper() in name for fragment in fragments):
            return device
    return None


def describe(sweeps, label):
    for sweep in sweeps:
        if sweep.insertion_loss:
            lowest, highest = min(sweep.insertion_loss), max(sweep.insertion_loss)
            print(f"  {label}: {len(sweep.wavelength)} points, IL {lowest:.2f} .. {highest:.2f} dB")
        else:
            print(f"  {label}: {len(sweep.wavelength)} points")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dll", help="path to Santec.Library.dll")
    parser.add_argument("--list-only", action="store_true", help="list the devices and exit")
    parser.add_argument("--start", type=float, default=1480.0, help="start wavelength, nm")
    parser.add_argument("--stop", type=float, default=1640.0, help="stop wavelength, nm")
    parser.add_argument("--step", type=float, default=0.01, help="step width, nm")
    parser.add_argument("--power", type=float, default=0.0, help="output power, dBm")
    parser.add_argument("--speed", type=float, default=100.0, help="sweep speed, nm/s")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--delay", type=int, default=0, help="delay between cycles, ms")
    parser.add_argument("--range", type=int, default=0, help="dynamic range, 0 = auto")
    parser.add_argument("--export-dir", help="write the IL CSV files here")
    parser.add_argument("--yes", action="store_true", help="skip the prompts between scans")
    args = parser.parse_args(argv)

    try:
        library = Library(args.dll)
    except (LibraryNotFound, AbiMismatch) as error:
        print(error, file=sys.stderr)
        return 2

    with library:
        library.enable_debug()

        devices = library.list_devices()
        print(f"{len(devices)} device(s):")
        for device in devices:
            print(f"  {device}")

        if args.list_only:
            return 0

        tsl = pick(devices, "TSL")
        power_meter = pick(devices, "MPM", "OPM", "8163", "8164")
        if tsl is None or power_meter is None:
            print("need a TSL and a power meter; see --list-only output", file=sys.stderr)
            return 1

        if not library.set_connections(tsl, power_meter):
            print("could not connect the instruments; see the log", file=sys.stderr)
            return 1

        library.reset_parameters()
        library.set_sweep_parameters(args.start, args.stop, args.step, args.power,
                                     args.speed, args.cycles, args.delay)
        if "MPM" in power_meter.product_name.upper():
            library.set_mpm_channel(0, 0, args.range)
        elif any(tag in power_meter.product_name for tag in ("8163", "8164")):
            library.set_agilent_lms_channel(0, 0, args.range)
        else:
            library.set_opm_module(0, args.range)

        problem = library.validate_parameters()
        if problem:
            print(f"the sweep is not valid for this hardware: {problem}", file=sys.stderr)
            return 1

        if args.export_dir:
            os.makedirs(args.export_dir, exist_ok=True)

        if not args.yes:
            input("Reference path connected? Press ENTER to measure the reference. ")
        print("reference sweep ...")
        reference = parse(library.reference_scan())
        describe(reference, "reference")
        if args.export_dir:
            library.export_reference_data(args.export_dir, "ILReference")

        if not args.yes:
            input("DUT connected? Press ENTER to measure it. ")
        print("measurement sweep ...")
        measurement = parse(library.measurement_scan())
        describe(measurement, "measurement")
        if args.export_dir:
            library.export_measurement_data(args.export_dir, "ILMeasurement")

        print("done")
        return 0


if __name__ == "__main__":
    sys.exit(main())
