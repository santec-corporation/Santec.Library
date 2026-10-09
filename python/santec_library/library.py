"""ctypes bindings for ``Santec.Library.dll``.

``Santec.Library.dll`` is a native library with a flat C ABI. This module loads
it, binds the entry points it needs, and wraps them in a small object API. It
does nothing at import time: no DLL is loaded until you create a :class:`Library`,
so importing the package is safe from anywhere.

    from santec_library import Library

    with Library() as lib:
        for device in lib.list_devices():
            print(device.product_name, device.serial_number)

The result payloads returned by the scans are FlatBuffers; :mod:`santec_library.results`
turns them into plain Python sequences.
"""

from __future__ import annotations

import os
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
from dataclasses import dataclass, field

from ._version import PACKAGE_VERSION

DLL_NAME = "Santec.Library.dll"

#: Serilog levels accepted by ``SetLogLevel``.
LOG_VERBOSE, LOG_DEBUG, LOG_INFORMATION, LOG_WARNING, LOG_ERROR, LOG_FATAL = range(6)


class LibraryNotFound(FileNotFoundError):
    """The native library could not be located."""


class AbiMismatch(RuntimeError):
    """The DLL does not export everything this package calls into.

    Raised with the list of missing entry points, which means the DLL is older
    than this package expects (or is a different build entirely).
    """


class ConnectionConfig(Structure):
    """Mirrors ``ConnectionConfig`` in SantecLibrary.h. The field order is the ABI."""

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
    """Decode a string the library produced.

    The library marshals ``ConnectionConfig`` strings with the platform default,
    which is the ANSI code page on Windows. ASCII names are unaffected; anything
    else is best-effort.
    """
    if not value:
        return ""
    try:
        return value.decode("mbcs")
    except (LookupError, UnicodeDecodeError):
        return value.decode("utf-8", errors="replace")


@dataclass
class Device:
    """One instrument reported by :meth:`Library.list_devices`."""

    type: str
    vendor_name: str
    product_name: str
    address: str
    serial_number: str
    product_number: int
    firmware_version: str
    #: The ABI structure, kept so the device can be handed back to the library.
    config: ConnectionConfig = field(repr=False, compare=False)

    def __str__(self) -> str:
        return f"{self.product_name} ({self.serial_number}) via {self.type}"


def resolve_dll(explicit: str | None = None) -> str:
    """Find ``Santec.Library.dll``.

    In order: the path you pass, ``$SANTEC_LIBRARY_DLL``, the working directory,
    the directory holding this package, then ``lib/win-x64`` in either of those
    directories (the layout the release archive uses).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        explicit,
        os.environ.get("SANTEC_LIBRARY_DLL"),
        os.path.join(os.getcwd(), DLL_NAME),
        os.path.join(here, DLL_NAME),
        os.path.join(os.getcwd(), "lib", "win-x64", DLL_NAME),
        os.path.join(os.path.dirname(here), "lib", "win-x64", DLL_NAME),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise LibraryNotFound(
        f"{DLL_NAME} was not found. Pass its path, set SANTEC_LIBRARY_DLL, or copy it next to your script."
    )


class Library:
    """A loaded ``Santec.Library.dll`` and the calls this package makes into it.

    Use it as a context manager, or call :meth:`disconnect` yourself: the
    instruments stay claimed until then.
    """

    #: Entry points this package uses, with their ctypes signatures. Binding them
    #: up front turns "the DLL is older than the package" into one clear error
    #: instead of an AttributeError in the middle of a measurement.
    SIGNATURES = {
        "GetDeviceNum": ([], c_int),
        "GetLibraryVersion": ([], c_void_p),
        "GetDevices": ([c_void_p, c_int], c_int),
        "FreeConnectionConfigs": ([c_void_p, c_int], None),
        "SetConnection": ([c_void_p], c_bool),
        "SetConnections": ([c_void_p, c_void_p, c_void_p], c_bool),
        "Disconnect": ([], None),
        "EnableDebug": ([], None),
        "EnableVerbose": ([], None),
        "SetLogLevel": ([c_int], None),
        "ResetParameters": ([], None),
        "EnableHighResolution": ([], None),
        "SetSweepParameters": ([c_double, c_double, c_double, c_double, c_double, c_int, c_int], None),
        "SetMPMChannel": ([c_int, c_int, c_ubyte], None),
        "SetOPMModule": ([c_int, c_ubyte], None),
        "SetAgilentLMSChannel": ([c_int, c_int, c_ubyte], None),
        "ValidateParameters": ([], c_void_p),
        "ReferenceScan": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], c_bool),
        "MeasurementScan": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], c_bool),
        "ExportReferenceDataTo": ([c_char_p, c_char_p], None),
        "ExportMeasurementDataTo": ([c_char_p, c_char_p], None),
        "DiscoverOPMDevices": ([], c_void_p),
        "GetMPMInfo": ([POINTER(POINTER(c_ubyte)), POINTER(c_int)], None),
        "GetMPMModulePower": ([c_int, POINTER(POINTER(c_double)), POINTER(c_int)], c_bool),
        "GetMPMPower": ([c_int, c_int], c_double),
        "GetTSLWavelength": ([], c_double),
        "SetTSLWavelength": ([c_double], None),
        "GetTSLPower": ([], c_double),
        "SetTSLPower": ([c_double], None),
        "FreeArrayData": ([c_void_p], None),
        "FreeString": ([c_void_p], None),
    }

    def __init__(self, dll_path: str | None = None, *, check_version: bool = True):
        self.path = resolve_dll(dll_path)
        self._dll = CDLL(self.path)

        self.missing_exports: list[str] = []
        for name, (argtypes, restype) in self.SIGNATURES.items():
            try:
                function = getattr(self._dll, name)
            except AttributeError:
                self.missing_exports.append(name)
                continue
            function.argtypes = argtypes
            function.restype = restype
        if self.missing_exports:
            raise AbiMismatch(
                f"{os.path.basename(self.path)} does not export: {', '.join(self.missing_exports)}. "
                f"This package needs a {PACKAGE_VERSION} build or later."
            )

        self._device_buffer = None
        self._device_count = 0

        if check_version:
            self.check_version()

    # lifecycle
    @property
    def dll(self):
        """The raw ``ctypes`` handle, for entry points this class does not wrap.

        The generated TSL surface alone is ninety-four entry points; only the ones
        the examples need are wrapped here. Call anything else through this handle,
        remembering that you own the free of whatever it allocates.
        """
        return self._dll

    def __enter__(self) -> "Library":
        return self

    def __exit__(self, *_exc) -> None:
        self.disconnect()

    def disconnect(self) -> None:
        """Release the instruments and the device list.

        Safe to call twice. The device strings are freed first: a
        ``ConnectionConfig`` still points into that memory.
        """
        if self._device_count > 0 and self._device_buffer is not None:
            self._dll.FreeConnectionConfigs(cast(self._device_buffer, c_void_p), self._device_count)
            self._device_count = 0
        self._dll.Disconnect()

    # version
    @property
    def version(self) -> str:
        """The library version reported by the DLL itself."""
        pointer = self._dll.GetLibraryVersion()
        if not pointer:
            return ""
        try:
            return cast(pointer, c_char_p).value.decode("utf-8", errors="replace")
        finally:
            self._dll.FreeString(pointer)

    def check_version(self, expected: str | None = None) -> None:
        """Warn when the DLL's version differs from ``expected`` (default: this package).

        A mismatch is only a warning: the entry-point check in :meth:`__init__` is
        what proves the two are actually compatible.
        """
        expected = expected or PACKAGE_VERSION
        actual = self.version
        if actual and actual != expected:
            print(
                f"warning: {os.path.basename(self.path)} reports version {actual}, "
                f"this package is {expected}. The entry points it needs are present."
            )

    # logging
    def enable_debug(self) -> None:
        """Log at Debug level. Reads from ``%APPDATA%\\Santec\\SantecLibrary\\logs``."""
        self._dll.EnableDebug()

    def enable_verbose(self) -> None:
        self._dll.EnableVerbose()

    def set_log_level(self, level: int) -> None:
        self._dll.SetLogLevel(level)

    # reads
    def mpm_info(self) -> str:
        """Model, serial, firmware and per-module details of the connected MPM.

        Returns an empty string when no MPM is connected. The buffer comes from
        the library's own allocator, not the CRT, and is released here.
        """
        data = POINTER(c_ubyte)()
        length = c_int(0)
        self._dll.GetMPMInfo(byref(data), byref(length))
        if not data or length.value <= 0:
            return ""
        try:
            return string_at(data, length.value).rstrip(b"\0").decode("utf-8", errors="replace")
        finally:
            self._dll.FreeArrayData(cast(data, c_void_p))

    def mpm_module_power(self, module: int) -> list[float]:
        """Power of every channel on an MPM module, in dBm. Zero-based module index."""
        data = POINTER(c_double)()
        length = c_int(0)
        if not self._dll.GetMPMModulePower(module, byref(data), byref(length)) or not data:
            return []
        try:
            return [data[index] for index in range(length.value)]
        finally:
            self._dll.FreeArrayData(cast(data, c_void_p))

    def mpm_channel_power(self, module: int, channel: int) -> float:
        """Power of one MPM channel, in dBm, or NaN when it does not exist."""
        return self._dll.GetMPMPower(module, channel)

    def get_tsl_wavelength(self) -> float:
        """Current TSL wavelength in nanometres."""
        return self._dll.GetTSLWavelength()

    def set_tsl_wavelength(self, nanometers: float) -> None:
        """Set the TSL wavelength in nanometres."""
        self._dll.SetTSLWavelength(nanometers)

    def get_tsl_power(self) -> float:
        """Current TSL output power."""
        return self._dll.GetTSLPower()

    def set_tsl_power(self, value: float) -> None:
        """Set the TSL output power, in the unit currently configured on the laser."""
        self._dll.SetTSLPower(value)

    # discovery
    def list_devices(self) -> list[Device]:
        """Enumerate the instruments the drivers can see.

        Finds VISA, FTDI and DAQ devices. An OPM-150 attached over Ethernet is
        not among them: it answers :func:`discover_opm_devices` instead.

        The list stays valid until :meth:`disconnect`; the entries are handed
        back to :meth:`connect`.
        """
        count = self._dll.GetDeviceNum()
        if count <= 0:
            return []

        buffer = (ConnectionConfig * count)()
        written = self._dll.GetDevices(cast(buffer, c_void_p), count)
        self._device_buffer = buffer
        self._device_count = written

        return [
            Device(
                type=_decode(buffer[i].Type),
                vendor_name=_decode(buffer[i].VendorName),
                product_name=_decode(buffer[i].ProductName),
                address=_decode(buffer[i].Address),
                serial_number=_decode(buffer[i].SerialNumber),
                product_number=buffer[i].ProductNumber,
                firmware_version=_decode(buffer[i].FirmwareVersion),
                config=buffer[i],
            )
            for i in range(written)
        ]

    # connection
    def connect(self, device: Device) -> bool:
        """Connect a single device, without starting a sweep pipeline."""
        return bool(self._dll.SetConnection(byref(device.config)))

    def set_connections(self, tsl: Device, power_meter: Device, spu: Device | None = None) -> bool:
        """Connect the TSL and the power meter, plus an optional DAQ device."""
        return bool(
            self._dll.SetConnections(
                byref(tsl.config),
                byref(power_meter.config),
                byref(spu.config) if spu is not None else None,
            )
        )

    # parameters
    def reset_parameters(self) -> None:
        """Clear the sweep parameters. They persist across :meth:`disconnect`."""
        self._dll.ResetParameters()

    def enable_high_resolution(self) -> None:
        """Put the power-meter builders into high-resolution mode.

        Required for sweeps with picometre steps. It is a separate call, not a
        side effect of :meth:`set_sweep_parameters`, so a coarse sweep can skip
        it and keep the faster processing path.
        """
        self._dll.EnableHighResolution()

    def set_sweep_parameters(
        self,
        start_nm: float,
        stop_nm: float,
        step_nm: float,
        power_dbm: float,
        speed_nm_s: float,
        cycles: int = 1,
        delay_ms: int = 0,
    ) -> None:
        """Configure the sweep. Units are the ones in the argument names.

        Call :meth:`enable_high_resolution` as well when ``step_nm`` is below a
        nanometre; the power meters process the finer grid only in that mode.
        """
        self._dll.SetSweepParameters(start_nm, stop_nm, step_nm, power_dbm, speed_nm_s, cycles, delay_ms)

    def set_mpm_channel(self, module: int, channel: int, dynamic_range: int = 0) -> None:
        """Select an MPM channel. ``dynamic_range`` 0 means auto-ranging."""
        self._dll.SetMPMChannel(module, channel, dynamic_range)

    def set_opm_module(self, module: int, dynamic_range: int = 0) -> None:
        """Select an OPM module. ``dynamic_range`` 0 means auto-ranging."""
        self._dll.SetOPMModule(module, dynamic_range)

    def set_agilent_lms_channel(self, module: int, channel: int, dynamic_range: int = 0) -> None:
        """Select an Agilent/Keysight LMS channel. ``dynamic_range`` 0 means auto-ranging."""
        self._dll.SetAgilentLMSChannel(module, channel, dynamic_range)

    def validate_parameters(self) -> str | None:
        """Check the configured sweep against the connected instruments.

        Returns the library's message when the combination is impossible, or
        ``None`` when it is fine.
        """
        pointer = self._dll.ValidateParameters()
        if not pointer:
            return None
        try:
            return cast(pointer, c_char_p).value.decode("utf-8", errors="replace")
        finally:
            self._dll.FreeString(pointer)

    # scanning
    def _scan(self, entry_point: str, attempts: int = 3, retry_delay: float = 1.0) -> bytes:
        """Run a scan and return a copy of the payload.

        The library allocates the payload and this method frees it, so the caller
        gets owned bytes. A ``False`` result is retried: the first scan after
        connecting returns nothing when the laser diode was off, because the call
        switches it on.
        """
        import time

        scan = getattr(self._dll, entry_point)
        data = POINTER(c_ubyte)()
        length = c_int(0)

        for attempt in range(1, attempts + 1):
            # A fresh out-pointer per attempt: on failure the library does not
            # always write to it.
            data = POINTER(c_ubyte)()
            length = c_int(0)
            if scan(byref(data), byref(length)):
                try:
                    return string_at(data, length.value)
                finally:
                    if data:
                        self._dll.FreeArrayData(cast(data, c_void_p))
            if attempt < attempts:
                time.sleep(retry_delay)

        raise RuntimeError(
            f"{entry_point} returned no data after {attempts} attempts. "
            "Check the log (%APPDATA%\\Santec\\SantecLibrary\\logs): nothing may be connected, "
            "or the laser may not be emitting."
        )

    def reference_scan(self, attempts: int = 3) -> bytes:
        """Run the reference sweep and return the payload bytes."""
        return self._scan("ReferenceScan", attempts)

    def measurement_scan(self, attempts: int = 3) -> bytes:
        """Run the measurement sweep and return the payload bytes."""
        return self._scan("MeasurementScan", attempts)

    def export_reference_data(self, directory: str, base_name: str = "ILReference") -> None:
        """Write the last reference sweep to ``<directory>\\<base_name>_<channel>.csv``.

        One file per result; the directory must already exist.
        """
        self._dll.ExportReferenceDataTo(directory.encode("utf-8"), base_name.encode("utf-8"))

    def export_measurement_data(self, directory: str, base_name: str = "ILMeasurement") -> None:
        """Write the last measurement sweep to ``<directory>\\<base_name>_<channel>.csv``."""
        self._dll.ExportMeasurementDataTo(directory.encode("utf-8"), base_name.encode("utf-8"))

    # OPM-150 over Ethernet
    def discover_opm_devices(self) -> list[dict[str, str]]:
        """Find OPM-150 power meters on the network by UDP broadcast.

        Returns one dict per responder with ``mac``, ``ip`` and ``mask`` keys, or
        an empty list when nothing answers. Ethernet-attached OPM-150s do not
        appear in :meth:`list_devices`, because that covers the VISA, FTDI and DAQ
        transports only.
        """
        pointer = self._dll.DiscoverOPMDevices()
        if not pointer:
            return []
        try:
            text = cast(pointer, c_char_p).value.decode("utf-8", errors="replace")
        finally:
            self._dll.FreeString(pointer)

        devices = []
        for line in text.splitlines():
            fields = {
                key.strip().lower(): value.strip()
                for key, _, value in (part.partition("=") for part in line.split(","))
                if value
            }
            if fields:
                devices.append(fields)
        return devices
