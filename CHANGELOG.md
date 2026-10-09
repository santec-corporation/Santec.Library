# Changelog

All notable changes to this repository are recorded here. The version tracks
`Santec.Library.dll`; the ABI version in `lib/win-x64/versions.json` changes only
when an entry point's signature or behaviour changes.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased], first public release

This release is the first published from this repository. It corresponds to the
library version in `Directory.Build.props` at the time of the split.

> Upgrading from 1.7.x? [`docs/migration-from-pre-1.8.md`](docs/migration-from-pre-1.8.md)
> lists every signature and behaviour change with the code change each one needs.

### Added

- `GetLibraryVersion()`, returns the library version as a UTF-8 string, so a
  binary found on a customer machine can identify itself. Free it with
  `FreeString()`.
- `ExportReferenceDataTo(directory, baseName)` and
  `ExportMeasurementDataTo(directory, baseName)`, write the last scan to
  `<directory>\<baseName>_<channel>.csv`, one file per result. The previous
  zero-argument exports relied on an auto-save configuration that the library
  never sets, so they had no defined output location; they remain for
  compatibility and are documented as legacy.
- `FreeConnectionConfigs(devices, count)`, releases the strings `GetDevices()`
  writes into a caller's buffer.

### Changed

- `GetDevices()` now takes a capacity and returns the number of entries written.
  It cannot overrun the caller's buffer when a device appears between
  `GetDeviceNum()` and `GetDevices()`.
- `SetConnections()` accepts an Agilent/Keysight LMS power meter. Previously only
  a plain MPM passed its type check, which made the LMS path unreachable.
- `SetOPMReadValidation()` takes a `uint8_t` instead of a `bool`, so the
  declaration matches the managed signature on the wire.
- `PolarizationState` is a 32-bit enum in the header, matching the managed enum,
  and includes the previously undocumented `Unknown = 0`.
- `ConnectionConfig.Type` carries the transport markers the header documents , 
  `VISA`, `FTDI`, `DAQ`, `LAN`, `LAN - UDP`, instead of the managed type name
  (`VISAConnectionConfiguration`1`). Callers that match on `Type` now find what
  the documentation promised.
- `GetLibraryVersion()` and every other entry point work regardless of the
  process working directory. An earlier build read its file version from a
  relative path and terminated the host process when the DLL was loaded from
  anywhere else.
- Nothing throws across the API boundary. Unsupported values are logged and
  reported through the documented sentinel instead of terminating the host
  process, and `Wl1650` is accepted by `SetWavelength()` and `Calculation()`.

### Fixed

- `SantecLibrary.h` compiles as C. It used fixed underlying types on its enums
  (`typedef enum NominalWavelength : uint8_t`), which only a C++ compiler accepts,
  so the header named for C could not be included from C at all. The C++ forms are
  unchanged; C sees integer typedefs with prefixed constants.
- `ToIConnectionConfiguration` tolerates a zeroed `ConnectionConfig` instead of
  dereferencing a null `Type`.
- `GetMPMInfo()` documentation said to free its buffer with `FreeString()`; the
  buffer comes from the library's own allocator and must be freed with
  `FreeArrayData()`. Following the old documentation corrupted the heap.
- Scan result buffers are released by the Python examples and cannot leak on the
  export path.
- `SetWavelength()` sets `Wl1650`, which the header and the C++ example had
  advertised since before it worked.

### Known limitations

- Windows x64 only.
- No error-query entry point: failures are reported as sentinels and written to
  `%APPDATA%\Santec\SantecLibrary\logs`.
