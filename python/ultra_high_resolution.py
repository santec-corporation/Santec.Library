# -*- coding: utf-8 -*-
"""High-resolution insertion-loss scan: TSL + MPM + DAQ.

Drives a swept-wavelength measurement with picometre steps, using the DAQ (SPU)
as the power-monitor source. It is interactive: it prints the instruments it
found, asks for the sweep and the MPM channels, and waits for ENTER before each
scan so the fiber can be moved.

Usage
    python ultra_high_resolution.py
    python ultra_high_resolution.py --dll ..\\lib\\win-x64\\Santec.Library.dll --export-dir measurements

The sweep parameters from the last run are offered again from
scan_parameters.json in the working directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from santec_library import AbiMismatch, Library, LibraryNotFound
from santec_library.results import parse

#: Sweep parameters are cached here and offered again on the next run.
SCAN_PARAMETER_CONFIG_FILE = "scan_parameters.json"

#: MPM dynamic range that means "auto".
AUTO_RANGE = 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dll", help="path to Santec.Library.dll")
    parser.add_argument("--export-dir", default=".", help="directory for the scan CSV files")
    return parser.parse_args(argv)


def connect_instruments(library: Library) -> None:
    """List the instruments, then claim the TSL, MPM and DAQ."""
    devices = library.list_devices()
    print("List of instruments.\n")
    for device in devices:
        print(device)

    # The markers are checked in this order, so a device that claims two of them
    # is treated as the earlier one.
    tsl = mpm = daq = None
    for device in devices:
        if "TSL" in device.product_name:
            tsl = device
        elif "MPM" in device.product_name:
            mpm = device
        elif "Dev" in device.product_name:
            daq = device

    missing = [
        name for name, device in (("TSL", tsl), ("MPM", mpm), ("DAQ", daq)) if device is None
    ]
    if missing:
        raise RuntimeError(f"not found: {', '.join(missing)}")

    if not library.set_connections(tsl, mpm, daq):
        raise RuntimeError("the library refused the connections; the log names the instrument")

    print("\nConnected to the TSL, MPM and DAQ.")


def get_tsl_scan_speed(step_nm: float) -> int:
    """Print the speeds that suit the step and read the user's choice."""
    speed_table = {"1": 1, "2": 2}

    thresholds = [
        (0.5, "3", 5),
        (1, "4", 10),
        (1, "5", 20),
        (2.5, "6", 50),
        (5, "7", 100),
        (100, "8", 200),
    ]

    for limit, key, value in thresholds:
        if step_nm >= limit:
            speed_table[key] = value

    print("\nTSL Speed Table:")
    for key, speed in speed_table.items():
        print(f"No. {key} - {speed} nm/s")

    print("\nRecommended, use lower speeds for better accuracy")
    while True:
        choice = input("Select the scan speed no.: ").strip()
        if choice in speed_table:
            return speed_table[choice]
        print(f"Enter one of: {', '.join(speed_table)}")


def import_scan_parameters(scan_parameters: dict) -> bool:
    """Offer the parameters saved by the previous run, and load them if accepted."""
    if not os.path.exists(SCAN_PARAMETER_CONFIG_FILE):
        print(f"{SCAN_PARAMETER_CONFIG_FILE} not found. Continuing...")
        return False

    choice = input(f"\nLoad the settings from {SCAN_PARAMETER_CONFIG_FILE}? [y|n]: ")
    if not choice.strip().lower().startswith("y"):
        return False

    with open(SCAN_PARAMETER_CONFIG_FILE, encoding="utf-8") as json_file:
        scan_parameters.update(json.load(json_file))

    print("\nLoaded scan parameters.")
    print("Start Wavelength (nm):", scan_parameters["start_wavelength"])
    print("Stop Wavelength (nm):", scan_parameters["stop_wavelength"])
    print(f"Scan Step (pm): {scan_parameters['scan_step'] * 1000:.1f}")
    print("Output Power (dBm):", scan_parameters["power"])
    print("Scan Speed (nm/s):", scan_parameters["scan_speed"])
    print("Scan Cycles:", scan_parameters["scan_cycles"])
    return True


def get_scan_parameters(scan_parameters: dict) -> None:
    """Ask for the sweep, unless the previous run's settings were accepted."""
    if import_scan_parameters(scan_parameters):
        return

    scan_parameters["start_wavelength"] = float(input("\nInput Start Wavelength (nm): "))
    scan_parameters["stop_wavelength"] = float(input("Input Stop Wavelength (nm): "))
    # The step is entered in picometres and kept in nanometres.
    scan_parameters["scan_step"] = float(input("Input Scan Step (pm): ")) / 1000
    scan_parameters["power"] = float(input("Input Output Power (dBm): "))
    scan_parameters["scan_cycles"] = int(input("Input Scan Cycles: "))
    scan_parameters["scan_delay"] = 0
    scan_parameters["scan_speed"] = get_tsl_scan_speed(scan_parameters["scan_step"])


def read_ints(prompt: str) -> list[int]:
    """Read a comma-separated list of numbers."""
    return [int(value) for value in input(prompt).replace(",", " ").split()]


def get_mpm_parameters(library: Library) -> dict[int, tuple[list[int], list[int]]]:
    """Ask which MPM modules, channels and dynamic ranges to measure.

    The returned keys are zero-based module indices; the channels and ranges are
    kept as typed, because they are what the operator reads off the instrument.
    """
    print("\n")
    print(library.mpm_info())

    modules: dict[int, tuple[list[int], list[int]]] = {}
    for module in read_ints("\nEnter the mpm modules to be used (Example: 1,2): "):
        channels = read_ints(f"\nEnter the module {module} channels to be used (Example: 1,2): ")
        ranges = read_ints(f"Enter the range for module {module} (e.g., 1,2): ")
        modules[module - 1] = (channels, ranges)

    return modules


def apply_mpm_parameters(
    library: Library, modules: dict[int, tuple[list[int], list[int]]], is_reference: bool
) -> None:
    """Select the MPM channels.

    A reference scan measures every range, so it auto-ranges each channel; a
    measurement scan uses the ranges chosen for it.
    """
    for module, (channels, ranges) in modules.items():
        for channel in channels:
            for dynamic_range in ([AUTO_RANGE] if is_reference else ranges):
                library.set_mpm_channel(module, channel, dynamic_range)


def export_scan_parameters(scan_parameters: dict) -> None:
    json_data = {
        "start_wavelength": scan_parameters["start_wavelength"],
        "stop_wavelength": scan_parameters["stop_wavelength"],
        "scan_step": scan_parameters["scan_step"],
        "power": scan_parameters["power"],
        "scan_speed": scan_parameters["scan_speed"],
        "scan_cycles": scan_parameters["scan_cycles"],
        "scan_delay": scan_parameters["scan_delay"],
    }

    with open(SCAN_PARAMETER_CONFIG_FILE, "w", encoding="utf-8") as export_file:
        json.dump(json_data, export_file, indent=4)

    print(f"\nSaved scan parameters to the file {SCAN_PARAMETER_CONFIG_FILE}.")


def prepare_scan(library: Library, scan_parameters: dict) -> None:
    """Configure the sweep, for either of the two scans."""
    library.reset_parameters()
    library.set_sweep_parameters(
        scan_parameters["start_wavelength"],
        scan_parameters["stop_wavelength"],
        scan_parameters["scan_step"],
        scan_parameters["power"],
        scan_parameters["scan_speed"],
        scan_parameters["scan_cycles"],
        scan_parameters["scan_delay"],
    )
    # The steps are in picometres, so the power meters need high-resolution mode.
    library.enable_high_resolution()


def describe(sweeps, label: str) -> None:
    for sweep in sweeps:
        print(f"  {label}: {sweep}")


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        library = Library(args.dll)
    except (LibraryNotFound, AbiMismatch) as error:
        print(error, file=sys.stderr)
        return 2

    with library:
        library.enable_debug()

        try:
            connect_instruments(library)
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 1

        # The reference scan is also where the sweep and the MPM channels are chosen.
        scan_parameters: dict = {}
        get_scan_parameters(scan_parameters)
        modules = get_mpm_parameters(library)

        # The channel selection does not survive a reset, so it is applied just
        # before each scan: every range for the reference, the chosen ones after.
        prepare_scan(library, scan_parameters)
        apply_mpm_parameters(library, modules, is_reference=True)
        input("\nPress ENTER to start the Reference scan operation....")
        print("Starting Reference....")
        reference = parse(library.reference_scan())
        print("Reference Complete.")
        describe(reference, "reference")

        prepare_scan(library, scan_parameters)
        apply_mpm_parameters(library, modules, is_reference=False)
        input("\nPress ENTER to start the Measurement scan operation....")
        print("Starting Measurement....")
        measurement = parse(library.measurement_scan())
        print("Measurement Complete.")
        describe(measurement, "measurement")

        print("Saving scan parameters...")
        export_scan_parameters(scan_parameters)

        os.makedirs(args.export_dir, exist_ok=True)
        print("Saving reference scan data...")
        library.export_reference_data(args.export_dir, "ILReference")
        print("Saving measurement scan data...")
        library.export_measurement_data(args.export_dir, "ILMeasurement")

    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
