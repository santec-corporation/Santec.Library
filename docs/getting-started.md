# Getting started

This walks through a first swept-wavelength measurement: confirm the library
loads, find the instruments, connect, configure the sweep, take a reference scan,
take a measurement scan, and get the data out. It assumes Windows x64 and at
least a TSL plus a power meter.

The three language-specific documents go into more detail:

- [C/C++ integration](cpp-integration.md)
- [.NET integration](dotnet-integration.md)
- [Python integration](python-integration.md)

Every entry point is listed in the [ABI reference](abi-reference.md).

## 1. Get the library next to your program

The binary is in this repository:

```
lib/win-x64/Santec.Library.dll     the library
lib/win-x64/Santec.Library.lib     MSVC import library (C++ only)
include/SantecLibrary.h/.hpp       declarations
```

Copy `Santec.Library.dll` next to your executable, or somewhere your loader can
find it. Nothing needs installing, and there is no registry entry or service.

Check that you have the right build:

```c
char* version = GetLibraryVersion();   /* free with FreeString */
printf("%s\n", version);
```

## 2. Confirm the instruments are reachable

```c
int32_t count = GetDeviceNum();
```

`GetDeviceNum()` enumerates VISA, FTDI and DAQ devices. It does **not** find
OPM-150 power meters attached over Ethernet, those answer the UDP broadcast
probe in `DiscoverOPMDevices()`.

If `count` is 0:

- confirm the driver is installed (NI-VISA, Keysight VISA, NI-DAQmx, FTDI D2XX , 
  see the table in the [README](../README.md));
- check the instrument with NI-MAX or the vendor's tool;
- call `EnableDebug()` and read `%APPDATA%\Santec\SantecLibrary\logs`: the library
  reports why enumeration failed there, not through a return code.

Then copy the configurations out and pick the ones you want:

```c
ConnectionConfig devices[8];
int32_t written = GetDevices(devices, 8);   /* never more than the capacity */
/* ... use devices[0..written-1] ... */
FreeConnectionConfigs(devices, written);    /* releases the strings inside them */
```

`GetDevices` allocates the strings inside each structure. `FreeConnectionConfigs`
releases those; the array itself is yours. If you forget the free, every
enumeration leaks.

## 3. Connect

```c
bool ok = SetConnections(&tslConfig, &pmConfig, NULL);
```

- `tslConfig` is the TSL, `pmConfig` the power meter, the third pointer an
  optional DAQ device used as the power monitor. Pass `NULL` when you have none.
- `SetConnection(&config)` connects a single device instead, which is what you
  want when reading an OPM-150 without running a sweep.
- An OPM-150 is a supported power meter but **not a sweep-capable one**: it has no
  sweep pipeline, so `ValidateParameters()` returns a message naming it rather than
  passing, and its readings come from `ReadOPMPower()`/`ReadOPMAllChannels()`. For a
  sweep, connect an MPM, an OPM-200 or an Agilent/Keysight LMS.
- Connections live in the library, not in a handle you hold. `Disconnect()`
  releases them all.

## 4. Configure the sweep

```c
ResetParameters();                       /* clear everything from a previous run */
SetSweepParameters(
    1480.0,   /* start wavelength, nm */
    1640.0,   /* stop wavelength, nm  */
    0.01,     /* step width, nm      */
    0.0,      /* output power, dBm   */
    100.0,    /* sweep speed, nm/s   */
    1,        /* cycles              */
    0);       /* delay between cycles, ms */

SetMPMChannel(0, 0, 0);                  /* module, channel, 0 = auto range */
/* or, for a different power meter: SetOPMModule(...) / SetAgilentLMSChannel(...) */
```

`ResetParameters()` matters: the builders are static state that persists between
runs and between `Disconnect()` calls.

Ask the library whether the combination is legal before scanning:

```c
char* error = (char*)ValidateParameters();   /* NULL when the parameters are fine */
if (error) { printf("%s\n", error); FreeString(error); }
```

## 5. Scan

```c
uint8_t* data = NULL;
int32_t length = 0;

if (!ReferenceScan(&data, &length))
{
    /* If this is the first call after connecting, the laser diode was off and has
       just been switched on. Wait a moment and call again. */
}

/* data/length now hold a FlatBuffers SweepResultSet (see python-integration.md
   for how to read it). Free it: */
FreeArrayData(data);
```

Then swap in the device under test and repeat with `MeasurementScan`.

The scans are synchronous: they return when the sweep has finished, which is as
long as the sweep takes (wavelength range divided by speed, times the cycles).

Export to CSV instead of parsing, if that is all you need:

```c
ExportReferenceDataTo("C:\\measurements", "ILReference");
ExportMeasurementDataTo("C:\\measurements", "ILMeasurement");
```

Those write `<directory>\<baseName>_<channel>.csv`, one file per result. The
directory has to exist. (The older `ExportReferenceData()` / `ExportMeasurementData()`
take no arguments and rely on an auto-save configuration the library never sets,
so they have no defined output location, don't use them.)

## 6. Disconnect

```c
Disconnect();
```

Releases the instruments and clears the device cache. Call it in a `finally` /
`__exit__` equivalent: a run that throws on the way out otherwise leaves the
instruments claimed.

## Where the data is

`ReferenceScan` and `MeasurementScan` hand back a FlatBuffers `SweepResultSet`.
It contains, per sweep:

| Result | Contents |
|---|---|
| `ILReferenceResult` | wavelength array, reference power, power-monitor readings |
| `ILResult` | wavelength array, insertion loss, and the rescaled spectrum per channel |

The Python bindings in `python/Santec/` are the fastest way to read it, including
from C# if you generate the equivalents; [`python-integration.md`](python-integration.md)
documents the object graph.

## The two rules that cause most problems

1. **Nothing is thread-safe.** The device cache, the parameter builders and the
   cached results are shared mutable state. Drive the library from one thread.
2. **Free what the library allocates, with the matching function.** The
   [reference](abi-reference.md#entry-points-that-return-memory) lists which entry
   points allocate and what to call.

## Next

- Run one of the examples: `examples/cpp/`, `examples/csharp/`, `python/`.
- Read the [ABI reference](abi-reference.md) for the entry point you need.
- If something returns `false` or `0` and the log explains nothing, the
  [troubleshooting table](../README.md#troubleshooting) covers the usual causes.
