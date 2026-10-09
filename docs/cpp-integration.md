# C and C++ integration

Santec.Library is a native DLL with a flat C ABI. This document covers linking it,
owning the memory it hands back, and driving a measurement from C++.

The declarations are in `include/SantecLibrary.hpp`; compiled examples are in
`examples/cpp/`.

## What you need

| File | Purpose |
|---|---|
| `Santec.Library.dll` | the library, loaded at run time |
| `Santec.Library.lib` | MSVC import library, needed at link time |
| `SantecLibrary.hpp` | declarations |

Platform: **Windows x64, C++20**. The header uses scoped enums
(`enum class PolarizationState : int32_t`), so it is a C++ header. A C compiler
cannot parse it as it stands, see "Calling from C" below.

Always take the header from the same release as the import library. The bin/LIB/header
trio in `lib/win-x64` and `include/` is built and verified as a set.

## Linking

With MSVC:

```
cl /std:c++20 /EHsc /utf-8 main.cpp /I include /link /LIBPATH:lib\win-x64 Santec.Library.lib
```

In a `.vcxproj`:

```xml
<ClCompile>
  <LanguageStandard>stdcpp20</LanguageStandard>
  <AdditionalIncludeDirectories>include;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
</ClCompile>
<Link>
  <AdditionalDependencies>Santec.Library.lib;%(AdditionalDependencies)</AdditionalDependencies>
</Link>
```

`Santec.Library.dll` has to be next to the executable or on the search path at run
time; the import library only satisfies the linker. `/utf-8` is worth setting even
in your own project: the header's comments contain non-ASCII characters, and MSVC
warns on code pages that cannot represent them.

## A complete program

```cpp
#include "SantecLibrary.hpp"

#include <array>
#include <cstdio>
#include <cstring>

int main()
{
    SetLogLevel(LogEventLevel::Information);

    if (const int32_t count = GetDeviceNum(); count > 0)
    {
        std::array<ConnectionConfig, 8> devices{};
        const int32_t written = GetDevices(devices.data(), static_cast<int32_t>(devices.size()));

        const ConnectionConfig* tsl = nullptr;
        const ConnectionConfig* pm = nullptr;
        for (int32_t i = 0; i < written; ++i)
            if (devices[i].ProductName && std::strstr(devices[i].ProductName, "TSL")) tsl = &devices[i];
            else if (devices[i].ProductName && std::strstr(devices[i].ProductName, "MPM")) pm = &devices[i];

        if (tsl && pm && SetConnections(tsl, pm, nullptr))
        {
            ResetParameters();
            SetSweepParameters(1480.0, 1640.0, 0.01, 0.0, 100.0, 1, 0);
            SetMPMChannel(0, 0, 0);   /* module, channel, 0 = auto range */

            if (char* error = static_cast<char*>(ValidateParameters()))
            {
                std::printf("invalid parameters: %s\n", error);
                FreeString(error);
            }
            else
            {
                uint8_t* data = nullptr;
                int32_t length = 0;
                if (ReferenceScan(&data, &length))
                {
                    std::printf("reference sweep: %d bytes\n", length);
                    ExportReferenceDataTo("C:\\measurements", "ILReference");
                    FreeArrayData(data);          /* library memory: free it */
                }
                else
                {
                    std::printf("reference scan returned no data; retry if the laser was off\n");
                }
            }

            Disconnect();
        }

        FreeConnectionConfigs(devices.data(), written);   /* releases the strings */
    }

    return 0;
}
```

## ConnectionConfig

`ConnectionConfig` is the only structure in the API. Treat it as opaque except
for the two fields you set when connecting over LAN:

```cpp
const ConnectionConfig tsl{ "LAN", "", "TSL-570", "192.0.2.10:5000" };
```

| Field | Meaning |
|---|---|
| `Type` | transport marker: `"VISA"`, `"FTDI"`, `"DAQ"`, `"LAN"` (and `"LAN - UDP"` for UDP) |
| `VendorName` | vendor, may be empty |
| `ProductName` | **used to pick the driver**: it must contain `TSL`, `MPM`, `OPM`+`150`/`200`, `8163`, `8164`, `PCU`, `XCS`, or `Dev` |
| `Address` | VISA resource string, `host:port` for LAN, product type for DAQ |
| `ProductNumber` | device-type number, `-1` when unused |
| `SerialNumber` | serial number |
| `FirmwareVersion` | version string |

For anything discovered automatically, use the structure `GetDevices` returns
rather than building one by hand: `ProductName` drives which driver the library
constructs, and guessing it is the most common way to get a confusing connection
failure.

`Type` carries one of the markers in the table above (`LAN - UDP` for a LAN
connection using UDP); match on it if you need the transport, or on `ProductName`
and `Address`.

## Memory ownership

The library allocates some of what it hands back. Free it with the matching
function, never with `free()`, and never by writing into a returned structure.
The [ABI reference](abi-reference.md#entry-points-that-return-memory) has the
generated list; these are the ones you will meet:

| Call | Free with |
|---|---|
| `GetDevices` | `FreeConnectionConfigs(buffer, count)`, releases the strings inside, not the array |
| `ReferenceScan`, `MeasurementScan` | `FreeArrayData(pointer)` |
| `ValidateParameters` | `FreeString(pointer)` |
| `GetLibraryVersion` | `FreeString(pointer)` |
| `GetMPMModulePower`, `GetMPMInfo` | `FreeArrayData(pointer)` |
| `ReadOPMAllChannels` | `FreeAllChannelsRead(pointer)` |
| `DiscoverOPMDevices`, `QueryOPMTempConfig`, `SetOPMNetworkConfig`, `ApplyOPMNetworkConfig` | `FreeString(pointer)` |

All of the free functions accept `NULL`, so a cleanup path can call them
unconditionally.

`GetMPMInfo` is the one to be careful with: its documentation used to name
`FreeString`, but the buffer comes from the library's own allocator, so
`FreeArrayData` is correct. Freeing it the other way corrupts the heap.

## Threading

There is no locking anywhere in the library. The device cache, the sweep-parameter
builders and the cached scan results are shared static state, so:

- call the API from one thread at a time, normally the thread that owns the
  instruments;
- do not run two scans concurrently, even on different instruments;
- a background timer or UI thread that reads a single instrument while a sweep
  runs on another will corrupt the sweep.

If you need to drive several instrument sets at once, put each in its own process.

## Errors

Nothing throws and there is no errno-style error code. Each entry point documents
its failure value, `false`, `0`, `NaN`, a null pointer, or "nothing written" , 
and every failure is logged to `%APPDATA%\Santec\SantecLibrary\logs`. Start the log
at Information level while integrating:

```cpp
SetLogLevel(LogEventLevel::Information);   /* Verbose and Debug are also available */
```

The log is the only place that says *why* something failed; check it before
looking for a bug in your own code.

## Two behaviours that surprise people

**The first scan after connecting can return `false`.** If the laser diode is off,
`ReferenceScan`/`MeasurementScan` switch it on and return without measuring. Retry
once; that is the documented contract, not an error.

**`ValidateParameters` returning a string is not an exception.** It returns a
pointer to a message when the sweep parameters are impossible (for example a step
larger than the range). Free it and fix the parameters.

## Calling from C

`SantecLibrary.h` is valid C17 as well as C++20. The C++-only fixed underlying
types are wrapped in `#ifdef __cplusplus`, and C sees integer typedefs instead:

```
cl /TC /std:c17 main.c /I include /link /LIBPATH:lib\win-x64 Santec.Library.lib
```

Two differences from the C++ form of the header:

- the enums become integer typedefs, and their members are prefixed, which is the
  naming already used for the logging levels:
  `NominalWavelength_Wl1550`, `OPMRangeMode_AutoRange`, `OPMGain_Gain2`,
  `PolarizationState_LVP`. C++ keeps the scoped forms , 
  `NominalWavelength::Wl1550`, `PolarizationState::LVP`, so existing C++ code is
  unaffected;
- `PolarizationState`'s C constants are prefixed because an unscoped enum would
  otherwise put `LVP`, `RCP` and `Unknown` into the global namespace of every
  translation unit that includes the header.

```c
#include "SantecLibrary.h"

int main(void)
{
    ConnectionConfig devices[4];
    int32_t written = GetDevices(devices, 4);
    FreeConnectionConfigs(devices, written);

    SetWavelength(NominalWavelength_Wl1550);
    SetPCUSOP(PolarizationState_LVP);
    return 0;
}
```

The internal repository keeps a compile fixture for this (`tools/header_c_check.c`
compiled with `/TC`), because the C++ sample cannot prove the C path.

## Building the example

`examples/cpp/` is a Visual Studio project. Publish the library first, then build
`x64`/`Release`. Its project file includes the header from `include/` rather than
keeping a copy, so it always compiles against the release it ships with.
