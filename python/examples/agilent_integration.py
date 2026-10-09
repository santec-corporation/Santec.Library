# -*- coding: utf-8 -*-
"""Insertion-loss swept test: Santec TSL + Agilent/Keysight 8163B or 8164A.

Talks to ``Santec.Library.dll`` directly through ``ctypes``. No managed wrapper
assembly and no pythonnet: the DLL is the ABI, the same one the C and C++
examples use.

Instruments
    Laser        Santec TSL-570 (or compatible)
    Power meter  Agilent/Keysight 8163B or 8164A lightwave multimeter

Usage
    python agilent_integration.py                       interactive
    python agilent_integration.py --list-only           list devices and exit (no hardware needed)
    python agilent_integration.py --dll <path>          explicit DLL path

The DLL is looked up in this order: ``--dll``, ``$SANTEC_LIBRARY_DLL``, the
directory holding this script, then the working directory. Python must be 64-bit
to load the x64 DLL.

Notes for maintainers
    * This example ships publicly; keep it free of customer-identifying content.
    * Scan step is entered and stored in nanometres, matching the DLL's
      ``SetSweepParameters`` contract. (The high-resolution harness asks for
      picometres and converts: the two scripts should be given one convention
      when the Python layer is consolidated.)
    * The result buffers ``ReferenceScan``/``MeasurementScan`` hand back are
      allocated by the DLL and freed here with ``FreeArrayData``.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
from ctypes import (
    CDLL,
    POINTER,
    Structure,
    byref,
    c_bool,
    c_char_p,
    c_double,
    c_int,
    c_ubyte,
    c_void_p,
    cast,
    string_at,
)

TSL_PARAMETER_CONFIG_FILE = "tsl_parameters.json"
DLL_NAME = "Santec.Library.dll"

# TSL-570 sweep-speed table (nm/s) and the step at which each entry becomes usable.
SPEED_VALUES = {"3": 5, "4": 10, "5": 20, "6": 50, "7": 100, "8": 200}
SPEED_FILTER = [(0.5, "3"), (1.0, "4"), (1.0, "5"), (2.5, "6"), (5.0, "7"), (100.0, "8")]


# --------------------------------------------------------------------------
# DLL bindings
# --------------------------------------------------------------------------
class ConnectionConfig(Structure):
    """Mirrors ``ConnectionConfig`` in SantecLibrary.h (ABI - do not reorder)."""

    _fields_ = [
        ("Type", c_char_p),
        ("VendorName", c_char_p),
        ("ProductName", c_char_p),
        ("Address", c_char_p),
        ("ProductNumber", c_int),
        ("SerialNumber", c_char_p),
        ("FirmwareVersion", c_char_p),
    ]


def _decode(value: bytes | None) -> str:
    """Decode a string produced by the DLL.

    The library marshals ``ConnectionConfig`` strings through the default
    ``CharSet`` (ANSI on Windows), so try that first and fall back to UTF-8.
    """
    if not value:
        return ""
    try:
        return value.decode("mbcs")
    except (LookupError, UnicodeDecodeError):
        return value.decode("utf-8", errors="replace")


class Instrument:
    """One device reported by ``GetDevices``."""

    def __init__(self, config: ConnectionConfig, keepalive=None):
        self.config = config
        # The struct is a window into the buffer filled by the DLL; hold the
        # buffer so the pointers stay valid.
        self._keepalive = keepalive

    @property
    def product_name(self) -> str:
        return _decode(self.config.ProductName)

    @property
    def serial_number(self) -> str:
        return _decode(self.config.SerialNumber)

    @property
    def connection_type(self) -> str:
        return _decode(self.config.Type)

    @property
    def firmware_version(self) -> str:
        return _decode(self.config.FirmwareVersion) or "N/A"

    def __repr__(self) -> str:
        return f"<Instrument {self.product_name!r} sn={self.serial_number!r} via {self.connection_type}>"


class Library:
    """Thin facade over the exported C entry points."""

    #: Entry points this example uses, with their ctypes signatures.
    _SIGNATURES = {
        "GetDeviceNum": ([], c_int),
        "GetDevices": ([c_void_p, c_int], c_int),
        "FreeConnectionConfigs": ([c_void_p, c_int], None),
        "SetConnection": ([c_void_p], c_bool),
        "SetConnections": ([c_void_p, c_void_p, c_void_p], c_bool),
        "Disconnect": ([], None),
        "EnableDebug": ([], None),
        "EnableVerbose": ([], None),
        "ResetParameters": ([], None),
        "SetSweepParameters": ([c_double, c_double, c_double, c_double, c_double, c_int, c_int], None),
        "SetAgilentLMSChannel": ([c_int, c_int, c_ubyte], None),
        "ValidateParameters": ([], c_void_p),
        "ReferenceScan": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], c_bool),
        "MeasurementScan": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], c_bool),
        "ExportReferenceDataTo": ([c_char_p, c_char_p], None),
        "ExportMeasurementDataTo": ([c_char_p, c_char_p], None),
        "FreeArrayData": ([c_void_p], None),
        "FreeString": ([c_void_p], None),
    }

    def __init__(self, path: str):
        self.path = path
        self._dll = CDLL(path)
        self._device_buffer: object | None = None
        self._device_buffer_count = 0

        # Bind what this build exports and report the rest: a DLL older than the
        # script is the most common cause of a confusing AttributeError later.
        self.missing: list[str] = []
        for name, (argtypes, restype) in self._SIGNATURES.items():
            try:
                function = getattr(self._dll, name)
            except AttributeError:
                self.missing.append(name)
                continue
            function.argtypes = argtypes
            function.restype = restype
        if self.missing:
            print(f"Warning: {os.path.basename(path)} does not export "
                  f"{', '.join(self.missing)}: it is older than this example expects.")

    # discovery
    def list_devices(self) -> list[Instrument]:
        count = self._dll.GetDeviceNum()
        if count <= 0:
            return []
        buffer = (ConnectionConfig * count)()
        written = self._dll.GetDevices(cast(buffer, c_void_p), count)
        # Keep the buffer and the strings the library wrote into it alive: the
        # structures are handed back to SetConnections, which reads them.
        self._device_buffer = buffer
        self._device_buffer_count = written
        return [Instrument(buffer[i], buffer) for i in range(written)]

    # connection
    def set_connections(self, tsl: Instrument, pm: Instrument) -> bool:
        """Connect the TSL and the power meter.

        The structs are passed by address: the DLL expects ``ConnectionConfig*``.
        """
        return bool(self._dll.SetConnections(byref(tsl.config), byref(pm.config), None))

    def disconnect(self) -> None:
        # Release the strings the library wrote into the device buffer before
        # dropping the instruments; the configurations still point into it.
        if self._device_buffer_count > 0:
            self._dll.FreeConnectionConfigs(
                cast(self._device_buffer, c_void_p), self._device_buffer_count)
            self._device_buffer_count = 0
        self._dll.Disconnect()

    # parameters
    def enable_debug(self) -> None:
        self._dll.EnableDebug()

    def enable_verbose(self) -> None:
        self._dll.EnableVerbose()

    def reset_parameters(self) -> None:
        self._dll.ResetParameters()

    def set_sweep_parameters(self, start_nm, stop_nm, step_nm, power, speed, cycles, delay) -> None:
        self._dll.SetSweepParameters(start_nm, stop_nm, step_nm, power, speed, cycles, delay)

    def set_lms_channel(self, module: int, channel: int, dynamic_range: int) -> None:
        """``dynamic_range`` is 0 for auto-ranging, otherwise 1-based."""
        self._dll.SetAgilentLMSChannel(module, channel, dynamic_range)

    def validate_parameters(self) -> str | None:
        """Return the validation error, or None when the parameters are valid."""
        ptr = self._dll.ValidateParameters()
        if not ptr:
            return None
        try:
            return _decode(cast(ptr, c_char_p).value)
        finally:
            self._dll.FreeString(ptr)

    # scanning
    def _scan(self, name: str, attempts: int = 3) -> bytes | None:
        """Run a scan and return a copy of the result buffer, or None.

        The library returns false on the first scan after connecting because it
        has just switched the laser diode on, so a false result is retried.
        """
        scan = getattr(self._dll, name)
        for attempt in range(1, attempts + 1):
            data_ptr = POINTER(c_ubyte)()  # fresh each attempt: on failure the DLL
            length = c_int(0)              # does not always touch the out params
            if scan(byref(data_ptr), byref(length)):
                try:
                    return string_at(data_ptr, length.value)
                finally:
                    if data_ptr:
                        self._dll.FreeArrayData(cast(data_ptr, c_void_p))
            if attempt < attempts:
                print(f"  {name} returned no data (attempt {attempt}/{attempts}): "
                      f"laser may have just been enabled; retrying")
                time.sleep(1.0)
        return None

    def reference_scan(self) -> bytes | None:
        return self._scan("ReferenceScan")

    def measurement_scan(self) -> bytes | None:
        return self._scan("MeasurementScan")

    def export_reference_data(self, directory: str, base_name: str) -> None:
        self._dll.ExportReferenceDataTo(directory.encode("utf-8"), base_name.encode("utf-8"))

    def export_measurement_data(self, directory: str, base_name: str) -> None:
        self._dll.ExportMeasurementDataTo(directory.encode("utf-8"), base_name.encode("utf-8"))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def resolve_dll(explicit: str | None) -> str:
    candidates = [explicit, os.environ.get("SANTEC_LIBRARY_DLL"),
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), DLL_NAME),
                  os.path.join(os.getcwd(), DLL_NAME)]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise SystemExit(
        f"Could not find {DLL_NAME}. Pass --dll <path> or set SANTEC_LIBRARY_DLL.")


def parse_int_list(text: str, label: str) -> list[int]:
    values = [item.strip() for item in text.split(",") if item.strip()]
    if not values:
        raise SystemExit(f"No {label} given.")
    try:
        return [int(item) for item in values]
    except ValueError:
        raise SystemExit(f"Could not read {label} from {text!r}; expected e.g. \"1,2\".")


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{text}{suffix}: ").strip()
    return answer or (default or "")


def prompt_yes_no(text: str, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    answer = input(f"{text} [{marker}]: ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def ask_scan_speed(step_nm: float) -> int:
    """Show the TSL-570 speed table for this step and return the selected nm/s."""
    table = {"1": 1, "2": 2}
    for threshold, key in SPEED_FILTER:
        if step_nm >= threshold:
            table[key] = SPEED_VALUES[key]

    print("\nTSL speed table:")
    for key in sorted(table, key=int):
        print(f"  {key} - {table[key]} nm/s")

    default = max(table, key=lambda key: table[key])
    while True:
        choice = prompt("Select scan speed", default)
        if choice in table:
            return table[choice]
        print("  Enter one of the numbers listed above.")


def load_parameters(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    if not prompt_yes_no(f"\nLoad the most recent parameters from {path}?", True):
        return None
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    print("\nLoaded parameters:")
    for key in ("start_wavelength", "stop_wavelength", "scan_step", "power",
                "scan_speed", "scan_cycles", "scan_delay"):
        print(f"  {key}: {saved.get(key)}")
    return saved


def collect_parameters(path: str) -> dict:
    saved = load_parameters(path)
    if saved is not None:
        return saved

    step_nm = float(prompt("Input scan step (nm)"))
    return {
        "start_wavelength": float(prompt("Input start wavelength (nm)")),
        "stop_wavelength": float(prompt("Input stop wavelength (nm)")),
        "scan_step": step_nm,
        "power": float(prompt("Input output power (dBm)")),
        "scan_speed": ask_scan_speed(step_nm),
        "scan_cycles": int(prompt("Input scan cycles", "1")),
        "scan_delay": int(prompt("Input scan delay (s)", "0")),
    }


def save_parameters(path: str, parameters: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(parameters, handle, indent=4)
    print(f"\nSaved parameters to {path}.")


def configure_power_meter(lib: Library, pm: Instrument, args) -> None:
    """Configure the LMS modules and channels."""
    is_8164a = "8164A" in pm.product_name
    auto_range = args.range == 0 if args.range is not None else prompt_yes_no(
        "\nUse the power meter's automatic dynamic range?", False)

    modules = args.modules or prompt("Power meter modules to use (example: 1,2)")
    for module in parse_int_list(modules, "modules"):
        # The 8164A addresses its modules from 1; the 8163B from 0.
        module_index = module if is_8164a else module - 1

        channels = args.channels or prompt(f"Module {module} channels to use (example: 1,2)")
        channel_list = parse_int_list(channels, "channels")

        if auto_range:
            ranges = [0]
        elif args.range is not None:
            ranges = [args.range]
        else:
            print("\nDynamic range setting: see the instrument manual for the ranges.")
            ranges = parse_int_list(
                prompt(f"Module {module} dynamic range to use (example: 1,2)"), "ranges")

        for channel in channel_list:
            for dynamic_range in ranges:
                # The user counts channels from 1; the DLL takes a zero-based index.
                lib.set_lms_channel(module_index, channel - 1, dynamic_range)


def select_instruments(devices: list[Instrument]) -> tuple[Instrument | None, Instrument | None]:
    tsl = pm = None
    for device in devices:
        name = device.product_name
        if "TSL" in name and tsl is None:
            tsl = device
        elif ("8163B" in name or "8164A" in name) and pm is None:
            pm = device
    return tsl, pm


def run(args) -> int:
    if struct.calcsize("P") * 8 != 64:
        raise SystemExit("Python must be 64-bit to load the x64 Santec.Library.dll.")

    dll_path = resolve_dll(args.dll)
    print(f"Using {dll_path}")
    lib = Library(dll_path)
    if args.debug:
        lib.enable_debug()
    if args.verbose:
        lib.enable_verbose()

    devices = lib.list_devices()

    print(f"\nFound {len(devices)} device(s):")
    for device in devices:
        print(f"  {device.product_name}  sn={device.serial_number}  "
              f"fw={device.firmware_version}  via {device.connection_type}")

    if args.list_only:
        # Listing no devices is a valid outcome: this is the no-hardware smoke path.
        return 0

    if not devices:
        print("No instruments found. Check the connections and the VISA/DAQ drivers.")
        return 1

    tsl, pm = select_instruments(devices)
    if tsl is None:
        print("\nNo TSL found.")
        return 1
    if pm is None:
        print("\nNo Agilent 8163B/8164A power meter found.")
        return 1

    print(f"\nTSL: {tsl.product_name} ({tsl.serial_number})")
    print(f"Power meter: {pm.product_name} ({pm.serial_number})")
    if not lib.set_connections(tsl, pm):
        print("\nInstrument connection failed. Check the connections again.")
        return 1

    try:
        parameters = collect_parameters(TSL_PARAMETER_CONFIG_FILE)

        lib.reset_parameters()
        lib.set_sweep_parameters(
            parameters["start_wavelength"],
            parameters["stop_wavelength"],
            parameters["scan_step"],
            parameters["power"],
            parameters["scan_speed"],
            int(parameters["scan_cycles"]),
            int(parameters["scan_delay"]),
        )
        configure_power_meter(lib, pm, args)

        error = lib.validate_parameters()
        if error:
            print(f"\nParameter validation failed:\n{error}")
            return 1
        print("\nParameters accepted.")

        if not args.no_export:
            # The export entry points write into an existing directory; they do
            # not create it.
            os.makedirs(args.export_dir, exist_ok=True)

        print("\nReference scan")
        if not args.yes:
            input("Connect the reference path and press ENTER to start: ")
        if lib.reference_scan() is None:
            print("Reference scan failed.")
            return 1
        if not args.no_export:
            lib.export_reference_data(args.export_dir, "ILReference")
        print("Reference scan done.")

        print("\nDUT scan")
        if not args.yes:
            input("Connect the DUT and press ENTER to start: ")
        if lib.measurement_scan() is None:
            print("Measurement scan failed.")
            return 1
        if not args.no_export:
            lib.export_measurement_data(args.export_dir, "ILMeasurement")
        print("Measurement scan done.")

        save_parameters(TSL_PARAMETER_CONFIG_FILE, parameters)
        return 0
    finally:
        lib.disconnect()
        print("Disconnected.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dll", help="path to Santec.Library.dll")
    parser.add_argument("--list-only", action="store_true",
                        help="list the detected devices and exit")
    parser.add_argument("--modules", help="power meter modules, e.g. \"1,2\"")
    parser.add_argument("--channels", help="channels per module, e.g. \"1,2\"")
    parser.add_argument("--range", type=int, choices=range(0, 5),
                        help="dynamic range: 0 = auto, 1-4 = fixed")
    parser.add_argument("--yes", action="store_true",
                        help="skip the ENTER prompts before each scan")
    parser.add_argument("--no-export", action="store_true",
                        help="scan without exporting the IL data")
    parser.add_argument("--export-dir", default=".",
                        help="directory for the exported IL CSV files (created if missing)")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    parser.add_argument("--verbose", action="store_true", help="enable verbose logging")
    return parser


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
