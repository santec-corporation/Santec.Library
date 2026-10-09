# Migrating from 1.7.x

This release is the first published from this repository after the split. The
library is still `Santec.Library.dll` with the same entry-point names and the same
flat C ABI, but a handful of signatures and behaviours changed, and the packaging
is different. Work through the section that matches how you consume the SDK.

Compatibility, in one table:

| What you use | Change | Action |
|---|---|---|
| `GetDevices(void*)` | now `int32_t GetDevices(void*, int32_t capacity)` | recompile with the new header and pass the buffer capacity; free the result with `FreeConnectionConfigs` |
| strings/arrays the library returns | unchanged ownership, new free for device lists | call `FreeConnectionConfigs(buffer, count)`, see below |
| `SetOPMReadValidation(serial, bool)` | parameter is now `uint8_t` | pass `1` / `0` |
| `PolarizationState` | 32-bit in the header (was declared 1 byte), and `Unknown = 0` is now documented | recompile; no source change if you used the enum constants |
| `ExportReferenceData()` / `ExportMeasurementData()` | they never wrote anywhere useful | use `...To(directory, baseName)` |
| `Santec.Library.Wrapper` (.NET) | **removed** | declare the entry points yourself, or copy the C# sample |
| pythonnet scripts | no managed assembly to load | use the `ctypes` examples |
| `ConnectionConfig.Type` | now `VISA`, `FTDI`, `DAQ`, `LAN`, `LAN - UDP` | match on those; they used to be managed type names such as `VISAConnectionConfiguration`1` |
| `SetConnections` with an Agilent LMS or OPM power meter | previously rejected | nothing to change; it now connects |

Nothing else moved: the DLL and import library keep their names, the header keeps
its, the entry points keep theirs, no new runtime dependency appeared, and the
platform is still Windows x64.

## Packaging

| Before | After |
|---|---|
| `Santec.Library.zip` (DLL + Python), `Santec.Library.Sample.Cpp.zip`, `Santec.Library.Sample.TSL.Controller.zip` | one `Santec.Library-<version>-win-x64.zip` containing `lib/win-x64` (DLL, import library, `versions.json`), `include/`, and `python/` |
| the binaries only ever arrived by e-mail or an internal share | committed in `lib/win-x64` and attached to every release |

The samples are no longer packaged: they live in this repository under
`examples/`, and they compile against the header that ships here.

## C and C++

Recompile. Two things will fail to build against the new header, on purpose:

```c
/* before */
GetDevices(devices);

/* after */
int32_t written = GetDevices(devices, 8);
```

```c
/* before */
SetOPMReadValidation(serial, true);

/* after */
SetOPMReadValidation(serial, 1);
```

Device lists now hand you library-allocated strings, so release them with the new
entry point:

```c
int32_t written = GetDevices(devices, capacity);
/* ... use the devices ... */
FreeConnectionConfigs(devices, written);
```

Without that call every enumeration leaks the strings inside the structures. The
array itself is still yours, `FreeConnectionConfigs` does not free it.

The header now compiles as C as well as C++. If you compile your translation unit
as C, the enum members are prefixed (`NominalWavelength_Wl1550`,
`PolarizationState_LVP`); as C++ nothing changes (`NominalWavelength::Wl1550`,
`PolarizationState::LVP`).

**One behaviour change worth knowing.** An older build read its version with a
relative path, so the library only worked when the process working directory
happened to contain `Santec.Library.dll`; otherwise the first call terminated the
process. If you had set the working directory in a launcher as a workaround, you
no longer need to.

## .NET

The managed `Santec.Library.Wrapper` assembly is gone, it depended on packages
that cannot be published, so a project that referenced it has to declare the
entry points it uses:

```csharp
[LibraryImport("Santec.Library", EntryPoint = "GetDeviceNum")]
private static partial int GetDeviceNum();

[LibraryImport("Santec.Library", EntryPoint = "GetDevices")]
private static partial int GetDevices(nint devices, int capacity);

[LibraryImport("Santec.Library", EntryPoint = "FreeConnectionConfigs")]
private static partial void FreeConnectionConfigs(nint devices, int count);
```

`examples/csharp/` is a complete replacement, including the `ConnectionConfig`
struct and the sweep sequence; the [.NET integration
guide](dotnet-integration.md) explains the marshalling. The wrapper's convenience
methods map to entry points one for one, so the port is mechanical: `ListDevices`
→ `GetDeviceNum`/`GetDevices`, `ConnectInstruments` → `SetConnections`,
`SetParameters` → `SetSweepParameters`, `SetLMSChannel` → `SetAgilentLMSChannel`,
`PerformReferenceScan`/`PerformMeasurementScan` → `ReferenceScan`/
`MeasurementScan`, `DisconnectInstruments` → `Disconnect`.

Two things the wrapper hid and you now have to do yourself:

- **free the scan buffer.** `ReferenceScan(&data, &length)` allocates; copy what
  you need and call `FreeArrayData(data)`. Skipping this leaks the whole payload
  of every scan.
- **handle the first scan returning `false`.** If the laser diode was off, the
  call switches it on and reports no data. Retry once.

If you exported IL data through the wrapper, replace it with the explicit
destination, which is the fix for the export that used to write nowhere:

```csharp
Native.ExportReferenceDataTo(dirPtr, namePtr);
Native.ExportMeasurementDataTo(dirPtr, namePtr);
```

## Python

Use the scripts in `python/` as the reference. The changes that affect an existing
script:

- **the harness moved**, from the old customer-named folder to `python/`, and the
  entry point is `python/ultra_high_resolution.py`;
- **the DLL is found by path**: `--dll <path>`, then `$SANTEC_LIBRARY_DLL`, then
  next to the script, then the working directory. The old scripts required the
  DLL to be in the current directory;
- **buffers are freed.** The examples call `FreeArrayData`/`FreeString`/
  `FreeConnectionConfigs`; a script that does not will grow by one scan payload
  per scan;
- **the first scan is retried**, because of the laser-off behaviour described
  above (the old scripts raised "scan failed");
- **the pythonnet path is gone.** A script that did
  `clr.AddReference("Santec.Library.Wrapper")` has to be ported to `ctypes`; the
  Agilent example is a worked example of exactly that;
- **`ExportReferenceData()` → `ExportReferenceDataTo(directory, baseName)`**, with
  both arguments as `bytes`. The output is `<directory>\<baseName>_<channel>.csv`.

## Behaviour changes that may affect measurements

- **Unsupported wavelength values no longer abort.** `SetWavelength` and
  `Calculation` log a warning and report through their sentinel (`NaN` for the
  calculation). Previously they threw, which terminated the host process. If you
  relied on the crash to notice a bad parameter, check the return value now.
- **`Wl1650` works.** The header and the C++ example had advertised it for some
  time; `SetWavelength` and `Calculation` used to reject it.
- **`SetConnections` accepts more power meters.** Any of MPM, OPM-150, OPM-200 or
  an Agilent/Keysight LMS now passes the type check. Before, only a plain MPM did,
  which silently made the LMS path unusable. An OPM-150 is the exception among them
  in one respect: it has no sweep pipeline, so `ValidateParameters` reports that
  rather than calling the configuration valid, and its readings come from
  `ReadOPMPower`/`ReadOPMAllChannels` instead of a scan.
- **Nothing throws across the boundary**, and entry points that enumerate devices
  catch driver failures and report zero devices instead of ending the process.
- **Pause and restart a sweep on a TSL only.** A TSL2 device supports starting
  and stopping a sweep, not pausing or restarting one. The library exports
  `StartTSL2Sweep` and `StopTSL2Sweep` for that connection and no TSL2
  counterpart to `PauseTSLSweep` or `RestartTSLSweep`, which address a TSL.
  Calling pause or restart through .NET raises analyzer `TSL002`.

## Staying on 1.7.x

The previous bundles remain on the old releases page. They are not updated and
will not receive fixes; the working-directory defect in particular is only fixed
here.

## Checklist

1. Take `include/` and `lib/win-x64` from the same release, never mix versions.
2. Recompile; fix the `GetDevices` and `SetOPMReadValidation` call sites.
3. Add `FreeConnectionConfigs` after every `GetDevices`.
4. If the scan payload is not parsed, switch to `Export*To` for the CSV output.
5. If you are on .NET, port off the wrapper assembly.
6. Verify `GetLibraryVersion()` matches the version you intended to take.
7. Run once with no instruments attached: discovery should report zero devices and
   nothing should crash.
