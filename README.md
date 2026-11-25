# Santec.Library

SDK for controlling Santec optical instruments in swept-wavelength Insertion Loss
(IL) and Polarization Dependent Loss (PDL) measurements. This repository carries
the prebuilt native library, the C/C++ header it exports, and worked examples for
C++, C#, VB.NET and Python.

| What you get | Where |
|---|---|
| `Santec.Library.dll` + `Santec.Library.lib` (win-x64) | `lib/win-x64/` |
| `Santec.Library.so` (linux-x64) | `lib/linux-x64/` |
| C and C++ declarations | `include/SantecLibrary.h`, `include/SantecLibrary.hpp` |
| Entry-point reference (generated from the header) | `docs/abi-reference.md` |
| Examples | `examples/cpp/`, `examples/csharp/`, `examples/vb/`, `examples/vb-il-sweep/`, and the Python scripts in `python/` |
| Python bindings and FlatBuffers result types | `python/` |
| Version, build commit and file hashes | `lib/<platform>/versions.json` |

Supported instruments: TSL-570/775 tunable lasers, MPM-210H multi-channel power
meters, OPM-200 optical power meters, Agilent/Keysight 8163B/8164A lightwave
measurement systems, PCU-110 polarization controllers, and NI USB-6001-class DAQ
devices used as the power-monitor source. The OPM-150 is supported for single
readings and network configuration, not for sweeps: it has no sweep pipeline, and
`ValidateParameters()` says so rather than passing.

**Platforms: Windows x64 and Linux x64.** Both binaries are built from the same
sources, and every release attaches one archive per platform. The Linux build needs
glibc 2.35 or later and `libstdc++` at run time.

## Install

The binaries are in this repository, so there is nothing to fetch:

```powershell
git clone https://github.com/santec-corporation/Santec.Library.git
```

Copy `lib/win-x64/Santec.Library.dll` or `lib/linux-x64/Santec.Library.so` next to your
application, or keep it in `lib/` and load it by path. Every release is also attached to
the [releases page](https://github.com/santec-corporation/Santec.Library/releases) as
`Santec.Library-<version>-win-x64.zip` and `Santec.Library-<version>-linux-x64.zip`, and
`lib/` carries the platforms that release committed.

## Prerequisites

The library calls into the instrument drivers installed on your machine; it does
not ship them.

| Instrument connection | Required |
|---|---|
| GPIB / USB / LAN (VISA) | NI-VISA, or Keysight VISA. On Linux, link `libvisa32.so` at the installed `libvisa.so`, see [VISA on Linux](#visa-on-linux) |
| DAQ (SPU power monitor) | NI-DAQmx |
| FTDI-based OPM-150 over USB | FTDI D2XX driver (`libftd2xx.so` on Linux) |
| OPM-150 over Ethernet (OP-ETH) | none, the library speaks UDP/TCP directly |

NI-MAX is useful for confirming that an instrument is reachable before blaming
your code; on Linux, `visaconf` and `pyvisa` do the same. If no driver is present,
device discovery returns zero devices rather than an error, see
[Troubleshooting](#troubleshooting).

### VISA on Linux

The binding asks the loader for `visa32`, which on Linux means `libvisa32.so`.
NI-VISA and Keysight install the file as `libvisa.so`, so link the name at the
installed library once per machine:

```bash
sudo ln -s /usr/lib/x86_64-linux-gnu/libvisa.so /usr/lib/x86_64-linux-gnu/libvisa32.so
sudo ldconfig
python -c "import ctypes; ctypes.CDLL('libvisa32.so')"   # proves the name resolves
```

FTDI and Ethernet instruments work without that link; only VISA instruments
disappear from `GetDeviceNum()`.

## Quick start

### C++

Link against the import library on Windows, or the shared object on Linux, and
include the header:

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
IL/PDL calculation and an interactive sweep. Build it with the project file on
Windows, or with g++ on Linux, after copying the binary next to it:

```bash
g++ -std=c++20 main.cpp -I include -L lib/linux-x64 -Wl,-rpath,'$ORIGIN' \
    -l:Santec.Library.so -o main
```

Read it as a reference if you are starting your own project.

### .NET

There is no managed wrapper assembly: declare the entry points you use, as
`examples/csharp/` and `examples/vb/` do.

```csharp
[LibraryImport("Santec.Library", EntryPoint = "GetDeviceNum")]
private static partial int GetDeviceNum();

[LibraryImport("Santec.Library", EntryPoint = "GetDevices")]
private static partial int GetDevices(nint devices, int capacity);
```

`csharp/` holds the generated classes for the scan payloads; they target .NET
Standard 2.0, and `examples/vb-il-sweep/` runs a sweep and reads the result with
them.

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
8163B/8164A). They need the library beside them, in `lib/<platform>`, or via `--dll`.

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
- The binaries in `lib/` are **not** open source. Each is licensed under the
  `LICENSE.txt` beside it, which travels with it; the win-x64 copy is
  [here](lib/win-x64/LICENSE.txt), and the Linux one carries the same terms.
- Third-party components are listed in
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

## Troubleshooting

| Symptom | Cause |
|---|---|
| `GetDeviceNum()` returns 0 | No driver installed, or the instrument is on another subnet. Confirm with NI-MAX; for an OPM-150 over Ethernet use `DiscoverOPMDevices()`, which does not rely on VISA. |
| VISA instruments are missing on Linux | `libvisa32.so` does not resolve, so the VISA binding reports itself unavailable. Link it at the installed `libvisa.so`, see [VISA on Linux](#visa-on-linux). |
| Device discovery finds nothing over Ethernet | `GetDeviceNum` covers VISA, FTDI and DAQ transports. Ethernet-attached OPM-150s are found by `DiscoverOPMDevices()`. |
| The process dies calling into the library | Check `GetLibraryVersion()` against the header version you compiled against; a mismatch means two different builds are on the machine. |
| A scan returns `false` the first time | Expected when the laser diode was off: the call switches it on and reports no data. Retry. |

## Support

This is an SDK, not a supported product: see Article 19 of the binary licence.
Bug reports and questions about the examples are welcome as GitHub issues; please
include the output of `GetLibraryVersion()` and the relevant part of
`%APPDATA%\Santec\SantecLibrary\logs`, or `~/.config/Santec/SantecLibrary/logs` on
Linux.

Security issues: see [SECURITY.md](SECURITY.md).
