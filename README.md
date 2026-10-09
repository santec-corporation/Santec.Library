# Santec.Library

SDK for controlling Santec optical instruments in swept-wavelength Insertion Loss
(IL) and Polarization Dependent Loss (PDL) measurements. This repository carries
the prebuilt native library, the C/C++ header it exports, and worked examples for
C++, .NET and Python.

| What you get | Where |
|---|---|
| `Santec.Library.dll` + `Santec.Library.lib` (win-x64) | `lib/win-x64/` |
| C and C++ declarations | `include/SantecLibrary.h`, `include/SantecLibrary.hpp` |
| Entry-point reference (generated from the header) | `docs/abi-reference.md` |
| Examples | `examples/cpp/`, `examples/csharp/`, and the Python scripts in `python/` |
| Python bindings and FlatBuffers result types | `python/` |
| Version, build commit and file hashes | `lib/win-x64/versions.json` |

Supported instruments: TSL-570/775 tunable lasers, MPM-210H multi-channel power
meters, OPM-200 optical power meters, Agilent/Keysight 8163B/8164A lightwave
measurement systems, PCU-110 polarization controllers, and NI USB-6001-class DAQ
devices used as the power-monitor source. The OPM-150 is supported for single
readings and network configuration, not for sweeps: it has no sweep pipeline, and
`ValidateParameters()` says so rather than passing.

**Platform: Windows x64.** The library targets `net10.0-windows8.0` and links the
Windows-only YY-Thunks runtime.

## Install

The binaries are in this repository, so there is nothing to fetch:

```powershell
git clone https://github.com/santec-corporation/Santec.Library.git
```

Copy `lib/win-x64/Santec.Library.dll` next to your application, or keep it in
`lib/win-x64` and load it by path. Every release is also attached to the
[releases page](https://github.com/santec-corporation/Santec.Library/releases) as
`Santec.Library-<version>-win-x64.zip`.

## Prerequisites

The library calls into the instrument drivers installed on your machine; it does
not ship them.

| Instrument connection | Required |
|---|---|
| GPIB / USB (VISA) | NI-VISA, or Keysight VISA |
| DAQ (SPU power monitor) | NI-DAQmx |
| FTDI-based OPM-150 over USB | FTDI D2XX driver |
| OPM-150 over Ethernet (OP-ETH) | none, the library speaks UDP/TCP directly |

NI-MAX is useful for confirming that an instrument is reachable before blaming
your code. If no driver is present, device discovery returns zero devices rather
than an error, see [Troubleshooting](#troubleshooting).

## Quick start

### C++

Link against the import library and include the header:

```cpp
#include "SantecLibrary.hpp"

int main()
{
    SetLogLevel(LogEventLevel::Information);

    const int32_t count = GetDeviceNum();
    if (count <= 0) return 0;

    std::array<ConnectionConfig, 8> devices{};
    const int32_t written = GetDevices(devices.data(), static_cast<int32_t>(devices.size()));
    // ... pick a device, then:
    // SetConnections(&tsl, &pm, nullptr);
    // ReferenceScan(&data, &length);  // free with FreeArrayData
    FreeConnectionConfigs(devices.data(), written);
}
```

`examples/cpp/` is a complete program: device discovery, TSL/PCU/OPM control,
IL/PDL calculation and an interactive sweep. Build it with the project file after
copying `lib/win-x64` next to it, or read it as a reference.

### .NET

There is no managed wrapper assembly: declare the entry points you use, as
`examples/csharp/` does.

```csharp
[LibraryImport("Santec.Library", EntryPoint = "GetDeviceNum")]
private static partial int GetDeviceNum();

[LibraryImport("Santec.Library", EntryPoint = "GetDevices")]
private static partial int GetDevices(nint devices, int capacity);
```

### Python

```bash
pip install ./python                 # 64-bit Python 3.10+; flatbuffers comes with it
python python/examples/quickstart.py --list-only
```

`python/examples/quickstart.py` runs the whole flow, discover, connect, reference,
measurement, export. Three more scripts use the same package and show the flows it
grew out of: `python/ultra_high_resolution.py` (picometre steps, TSL + MPM + DAQ,
interactive), `python/mpm_connection.py` and `python/tsl_connection.py` (single
instrument checks), and `python/examples/agilent_integration.py` (TSL + Agilent
8163B/8164A). They need the DLL beside them, in `lib/win-x64`, or via `--dll`.

## Documentation

| Document | Contents |
|---|---|
| [`docs/abi-reference.md`](docs/abi-reference.md) | Every entry point, its parameters, and what to free. Generated from the header. |
| [`docs/getting-started.md`](docs/getting-started.md) | First measurement, step by step. |
| [`docs/cpp-integration.md`](docs/cpp-integration.md) | Linking, threading, memory ownership. |
| [`docs/dotnet-integration.md`](docs/dotnet-integration.md) | P/Invoke declarations and `ConnectionConfig` marshalling. |
| [`docs/python-integration.md`](docs/python-integration.md) | Reading scan results with the FlatBuffers bindings. |
| [`docs/migration-from-pre-1.8.md`](docs/migration-from-pre-1.8.md) | What changed, and what to do about it, if you are upgrading from 1.7.x. |

Two rules apply to everything in the API and cause most of the problems people
hit, so they are worth repeating:

- **Nothing is thread-safe.** The device cache, the parameter builders and the
  cached scan results are shared mutable state. Call the API from one thread.
- **Entry points that return data allocate it.** Free it with the function named
  in the reference (`FreeArrayData`, `FreeString`, `FreeConnectionConfigs`), never
  with `free()`.

## Licensing

- The headers, examples, documentation and scripts in this repository are
  licensed under the [Apache License 2.0](LICENSE).
- `Santec.Library.dll` and `Santec.Library.lib` in `lib/` are **not** open source.
  They are licensed separately under the terms in
  [`lib/win-x64/LICENSE.txt`](lib/win-x64/LICENSE.txt), which travel with them.
- Third-party components are listed in
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `GetDeviceNum()` returns 0 | No driver installed, or the instrument is on another subnet. Confirm with NI-MAX; for an OPM-150 over Ethernet use `DiscoverOPMDevices()`, which does not rely on VISA. |
| Device discovery finds nothing over Ethernet | `GetDeviceNum` covers VISA, FTDI and DAQ transports. Ethernet-attached OPM-150s are found by `DiscoverOPMDevices()`. |
| The process dies calling into the library | Check `GetLibraryVersion()` against the header version you compiled against; a mismatch means two different builds are on the machine. |
| A scan returns `false` the first time | Expected when the laser diode was off: the call switches it on and reports no data. Retry. |

## Support

This is an SDK, not a supported product: see Article 19 of the binary licence.
Bug reports and questions about the examples are welcome as GitHub issues; please
include the output of `GetLibraryVersion()` and the relevant part of
`%APPDATA%\Santec\SantecLibrary\logs`.

Security issues: see [SECURITY.md](SECURITY.md).
