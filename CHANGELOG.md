# Changelog

All notable changes to this repository are recorded here. The version tracks
`Santec.Library.dll`; the ABI version in `lib/win-x64/versions.json` changes only
when an entry point's signature or behaviour changes.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `csharp/`: the generated FlatBuffers accessors for the scan payloads, targeting
  .NET Standard 2.0 so .NET Framework 4.6.1 and later, VB.NET and modern .NET can
  read them. `Google.FlatBuffers` supplies the runtime.
- `examples/vb-il-sweep/`: an insertion-loss sweep that parses the returned
  `SweepResultSet` with those classes and prints the IL range and the first points.
  Its archive carries `csharp/` because the project references it.
- `examples/vb/`: the TSL sample in VB.NET. It declares the entry points with
  `DllImport`, because `LibraryImport` needs a partial method and VB allows partial
  methods only for `Sub`. The four language rules that change the declarations are in
  [`docs/dotnet-integration.md`](docs/dotnet-integration.md#vbnet). `verify.yml` builds
  it and `package_examples.py` ships it.
- `lib/linux-x64/Santec.Library.so`, built from the same sources as the Windows DLL and
  attached to each release as `Santec.Library-<version>-linux-x64.zip`. The build needs
  glibc 2.35 or later and `libstdc++` at run time. VISA instruments need `libvisa32.so`
  to resolve to the installed `libvisa.so`, because the binding asks the loader for
  `visa32`.
- `tests/check_bundle.py --platform`: checks one platform of a checkout that carries
  both, and `tests/abi_surface.py` reads an ELF dynamic symbol table as well as a PE
  export directory.
- The Python package resolves the platform's file name and `lib/<rid>`, so `Library()`
  finds the shared object in `lib/linux-x64` the way it finds the DLL in `lib/win-x64`.
- `examples/vb-il-sweep/` reports the reference `Data` table as well, so the example
  shows the whole payload rather than a point count: `power` and `power_monitor` with
  their units, and `polarization`. The vectors are labelled with the unit the payload
  declares, `WavelengthUnit` and `PowerUnit`, instead of nm and dB unconditionally.

### Changed

- `verify.yml` gains a Linux job that checks the committed object when the checkout
  carries one, and reports that there is nothing to check when it does not.
- The VB examples decode the library's UTF-8 strings through `Native.FromUtf8`, which
  calls `Marshal.PtrToStringUTF8` on modern .NET and copies the bytes under
  `#If NETFRAMEWORK Or NETSTANDARD`. `PtrToStringUTF8` arrived in .NET Core 3.0, so a
  .NET Framework consumer of `csharp/` needs the fallback.
- `examples/vb/` and `examples/vb-il-sweep/` target `net10.0`, and `net48` on Windows,
  build as x64, and pick the `DllImport` name with `#If NETFRAMEWORK`: the Framework
  loader does not append `.dll` to a name that already contains a dot, so the bare
  name only resolves on .NET. The README commands pass `--framework net10.0`, which
  `dotnet run` requires where the project has more than one framework.
- `tools/package_examples.py` writes `--framework` into the generated run command when
  a project declares more than one target framework.
- `docs/dotnet-integration.md` gains the result-binding step, the union tag rule, the
  unit fields, the `DestroyStructure` release call, and the `DllImport` name rule for
  .NET Framework: a name that already contains a dot reaches the loader as written, so
  a Framework caller writes `Santec.Library.dll`.
- `docs/python-integration.md` and `csharp/README.md` document the unit fields:
  `WavelengthUnit` is 0 for pm and 1 for nm, `PowerUnit` is 0 for dBm and 1 for dBW,
  and an enum of the same name from the parameter layer does not carry those values.

### Fixed

- `examples/csharp/`: `Connect()` releases the `ConnectionConfig` block it allocates
  and the string copies inside it. Both leaked on every connection.
- `examples/vb/` and `examples/vb-il-sweep/`: `Connect()` releases the string copies
  `Marshal.StructureToPtr` allocates before it frees the block, which leaked one set
  of strings per call.
- `examples/vb-il-sweep/`: compares `SweepResultEntry.ResultsType` before reading a
  union member. The generated accessors do not check the tag and `ILResult` and
  `ILReferenceResult` overlap field for field, so a measurement read as a reference
  returned the measurement's power vector as the reference power without failing.

## [1.8.0.9] - 2026-11-19

### Added

- `SetReferenceOffset(double)`: sets how far below the sweep power the reference scan
  runs, so a sweep power that suits the device under test does not overload the meter
  while the reference runs. The library lowers the laser for the reference scan,
  restores the sweep power for the device scans, and accounts for the offset in the
  insertion loss it reports. A zero offset, the default after `ResetParameters()`,
  leaves both scans at the sweep power. `ValidateParameters()` reports a negative or
  non-finite value instead of clamping it.
- `python/santec_library/library.py`: `set_reference_offset(offset_db)`.
- `TSLMainParameters.ReferenceOffset` carries the offset through the sweep parameters.

### Changed

- Rebuilt against updated instrument and process packages, with the third-party
  notices regenerated to match.

### Fixed

- `SantecLibrary.hpp` declares the TSL2 entry points, `WaitTSLForSweepStatus()`,
  `GetTSLIsLLPCompatible()`, `GetTSLCommandFormat()` and `SetOPMReadValidation()`,
  which `SantecLibrary.h` already exported.
- `SetPower()` documents its argument as dBm, which is what the DLL takes.

## [1.8.0.7] - 2026-11-11

### Added

- `python/standard_pdl_sts.py`: a polarization-dependent-loss scan over a TSL, a PCU
  and an MPM, exporting the result the way the insertion-loss scripts do. The script
  caches the sweep in `scan_parameters.json`, so the next run starts from the last
  settings.

### Changed

- `SetConnections()` takes the polarization controller as its third pointer, ahead of
  the DAQ configuration. `lib/win-x64/versions.json` records ABI 2, so a caller that
  passes three pointers has to add the PCU argument.
- `GetTSLLoggingData()`, `GetTSLLoggingDataF()`, `GetTSL2PowerLoggingData()` and
  `GetTSL2PowerLoggingDataF()` take `data` and `length` out-parameters. The library
  allocates the buffer; release it with `FreeArrayData()`.
- `set_connections(tsl, meter, pcu=None, spu=None)` puts `pcu` third and `spu` fourth,
  so a positional call passes the PCU, not the DAQ device.
- PDL needs the polarization controller in the same `SetConnections()` call. If the
  caller connects the PCU by another route, PDL stays off.

## [1.8.0.6] - 2026-11-06

Rebuilt with the internal polarization-dependent-loss work. The public API for it
arrived in 1.8.0.7.

## [1.8.0.5] - 2026-11-06

### Changed

- Device discovery includes DAQ devices, which `GetDeviceNum()` and `GetDevices()`
  list, and which connect in the same call as the instruments.

## [1.8.0.4] - 2026-10-29

Rebuilt against an updated `Santec.Instruments`.

## [1.8.0.3] - 2026-10-29

Rebuilt against the NativeAOT 10.0.14 toolchain, with the third-party notices
regenerated to match.

## [1.8.0.2] - 2026-10-22

Rebuilt against updated compiler and instrument dependencies, with the third-party
notices regenerated to match.

The package version is declared once, in `python/santec_library/_version.py`.
`setuptools` reads that declaration into the metadata at build time, so the
distribution version cannot disagree with the DLL.

## [1.8.0.1] - 2026-10-09

The first published release. `GetLibraryVersion()` reports `1.8.0.1`, and
`lib/win-x64/versions.json` records the internal commit the binary was built from.

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
- `ConnectionConfig.Type` carries the transport markers the header documents,
  `VISA`, `FTDI`, `DAQ`, `LAN`, `LAN - UDP`, instead of the managed type name
  (`` `VISAConnectionConfiguration`1 ``). Callers that match on `Type` now find what
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
