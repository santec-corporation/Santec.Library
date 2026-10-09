# Santec.Library.Sample.Cpp

A native C++ console application for driving Santec instruments
(TSL-570, PCU-110, OPM-150) through the **SantecLibrary** C-exported DLL.
It covers device discovery, instrument control, and IL/PDL measurement.

---

## Table of Contents

- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Building](#building)
- [Running the Sample](#running-the-sample)
- [Demos](#demos)
  - [Device Discovery](#device-discovery)
  - [TSL-570 Control](#tsl-570-control)
  - [PCU-110 Control](#pcu-110-control)
  - [OPM-150 Control](#opm-150-control)
  - [OPM-150 Network Configuration](#opm-150-network-configuration)
  - [IL / PDL Calculation (Static)](#il--pdl-calculation-static)
  - [IL / PDL Wavelength Sweep (Interactive)](#il--pdl-wavelength-sweep-interactive)
- [API Overview](#api-overview)
- [Output Files](#output-files)

---

## Requirements

| Requirement | Details |
|---|---|
| **IDE** | Visual Studio 2022 or later (v145 platform toolset) |
| **Language standard** | C++20 |
| **Architecture** | x64 |
| **Runtime** | .NET 10 NativeAOT runtime (consumed via `Santec.Library.dll`) |
| **DLL** | `Santec.Library.dll` must be present in the project directory and copied to the output folder |

---

## Project Structure

```
examples/cpp/
├── Santec.Library.Sample.Cpp.vcxproj
├── sample_options.hpp         # Command-line options shared by the translation units
├── sample_helpers.hpp         # Shared print/format helpers
├── device_discovery.hpp/.cpp  # Device enumeration via GetDeviceNum() / GetDevices()
├── main.cpp                   # Program entry point - orchestrates all demos
├── tsl_control.cpp            # TSL-570 wavelength and power control demo
├── pcu_control.cpp            # PCU-110 polarization state control demo
├── opm_control.cpp            # OPM-150 single-channel and all-channel read demo
├── pdl_calculation.cpp        # IL/PDL calculation demo (static simulated data)
└── il_pdl_sweep.cpp           # IL/PDL wavelength sweep demo (interactive, live hardware)
```

Nothing is copied into this folder. The project compiles against
`..\..\include\SantecLibrary.hpp`, links against
`..\..\lib\win-x64\Santec.Library.lib`, and copies
`..\..\lib\win-x64\Santec.Library.dll` next to the executable after every build.

---

## Building

1. The SDK is already in this repository: `include/` has the headers and
   `lib/win-x64/` has the DLL and its import library. There is nothing to publish
   or install.

2. Open `Santec.Library.Sample.Cpp.vcxproj`, choose `Debug` or `Release` with
   platform **x64** (x86 is not supported: the library and its import library are
   x64 only), and build. From the command line:

   ```powershell
   msbuild examples\cpp\Santec.Library.Sample.Cpp.vcxproj /p:Configuration=Release /p:Platform=x64
   ```

The executable is placed next to the project:

```
examples\cpp\x64\Release\Santec.Library.Sample.Cpp.exe
```

---

## Running the Sample

```powershell
.\examples\cpp\x64\Release\Santec.Library.Sample.Cpp.exe [options]
```

Connection details are arguments, not constants, so no lab address or serial
number is compiled in:

| Option | Meaning | Default |
|---|---|---|
| `--tsl <address>` | TSL LAN address | `192.0.2.10:5000` |
| `--opm <address>` | OPM-150 LAN address | `192.0.2.11:23` |
| `--pcu <address>` | PCU-110 LAN address | `192.0.2.12:5000` |
| `--opm-serial <sn>` | OPM-150 serial number used by the OPM demos | `SN00000` |
| `--opm-network-demo` | run the GIPA/SIPA/TIPA/UIPC network demo | off |
| `--mac <mac>` / `--ip <address>` / `--mask <mask>` | values staged by the network demo | placeholder / `0.0.0.0` (DHCP) / `255.255.255.0` |
| `--help` | print usage |, |

When physical instruments are connected the program runs every demo in sequence.
When **no devices are detected** it falls back to offline mode and runs only the
static IL/PDL calculation demo (no hardware required).

---

## Demos

### Device Discovery

Calls `GetDeviceNum()` then `GetDevices()` to enumerate Santec instruments
reachable over VISA, FTDI, LAN, or DAQ.
Prints each device's type, vendor, product name, address, serial number, and firmware
version to the console.

> **Note:** `GetDevices()` does **not** discover instruments connected over
> Ethernet. To find OPM-150s on the network, use `DiscoverOPMDevices()` (the
> GIPA UDP broadcast). See [OPM-150 Network Configuration](#opm-150-network-configuration).

---

### TSL-570 Control

File: `tsl_control.cpp`

- Reads the current TSL output wavelength (`GetTSLWavelength()`).
- Reads the current TSL output power (`GetTSLPower()`).
- Sets a target wavelength band (`SetWavelength()`).
- Sets a target output power (`SetTSLPower()`).
- Verifies the new power reading.

---

### PCU-110 Control

File: `pcu_control.cpp`

- Reads the PCU power monitor before any state change (`ReadPCUPowerMonitor()`).
- Iterates through all six polarization states (LVP, LHP, LP45, LN45, RCP, LCP).
- For each state: calls `SetPCUSOP()` and reads the updated power monitor.

---

### OPM-150 Control

File: `opm_control.cpp`

- **OP-ETH session timeout**: reads the current TCP port, UDP port, and session timeout from flash
  (`GetOPMFlashConfig()`), sets the timeout to 120 seconds (`SetOPMTimeout()`),
  verifies the staged change (`GetOPMTempConfig()`), and saves to flash (`SaveOPMConfig()`).
  No-op over FTDI (USB).
- **Single-channel read**: activates channel 1 via `SetOPMChannel()` and calls `ReadOPMPower()`.
- **All-channel read**: calls `ReadOPMAllChannels()`, prints every channel's power reading,
  then releases the library-owned buffer with `FreeAllChannelsRead()`.

> The OPM serial number comes from the `--opm-serial` argument (`SN00000` by
> default), so the same binary works with any instrument.

---

### OPM-150 Network Configuration

File: `main.cpp` (inline function `runOPMNetworkDemo()`)

Demonstrates remote IP configuration of OPM-150 devices over UDP broadcast on
port 61022 (OP-ETH module default). This is the **only** way to discover and
configure OPM-150s connected over Ethernet; the standard `GetDevices()` call
covers VISA/FTDI/LAN/DAQ transports but does **not** enumerate Ethernet-attached
instruments. This demo needs no physical USB/VISA connection.

#### Architecture

`DiscoverOPMDevices()` enumerates all active IPv4 NICs on the host, creates a
per-NIC UDP socket bound to each interface, and broadcasts a discovery datagram
on every one. The sockets stay open so OPM-150 replies arrive on the same socket
that sent the broadcast (avoiding a port-mismatch). The library caches only the NICs that
receive a `"MAC=…"` response.

`SetOPMNetworkConfig()`, `QueryOPMTempConfig()`, and `ApplyOPMNetworkConfig()`
**require** a prior `DiscoverOPMDevices()` call; they reuse the cached
responsive NICs instead of re-enumerating, and return an error if no NICs have
been discovered yet.

> **Duplicate responses:** The discovery broadcast goes out on every active
> NIC, so a single OPM-150 device may respond through more than one interface
> (e.g. a host with both Wi-Fi and Ethernet on the same subnet). In that case
> the same `"MAC=…"` response can arrive on multiple sockets. The library does
> not deduplicate; callers should be prepared to filter repeated MAC addresses
> from the returned list.

#### IP Configuration Notes

- Setting the IP address to **`0.0.0.0`** enables **DHCP** on the OP-ETH module.
- If DHCP is enabled but no server responds, the module falls back to **AutoIP**
  (a `169.254.x.x` address with mask `255.255.0.0`).
- The default TCP port is **23** (Telnet). The default UDP port is **61022**,
  with a backup UDP port of **61023** that cannot be changed.

#### Example Console Output

The values below are what you get after passing `--mac`, `--ip` and `--mask`;
the addresses are placeholders, not defaults:

```
[OPM-150 Network Configuration Demo]
------------------------------------------------------------
  Step 1: Broadcasting GIPA discovery ...
  Discovered devices:
MAC=00-00-00-00-00-00,IP=192.0.2.11,MASK=255.255.0.0

  Step 2: Setting temporary IP config via SIPA ...
    MAC  : 00-00-00-00-00-00
    IP   : 192.0.2.11
    Mask : 255.255.255.0
  SIPA response: MAC=00-00-00-00-00-00,IP=192.0.2.11,MASK=255.255.255.0

  Step 3: Querying temporary config via TIPA ...
  TIPA response:
MAC=00-00-00-00-00-00,IP=192.0.2.11,MASK=255.255.255.0

  Step 4: Applying config to flash via UIPC ...
    Target MAC: 00-00-00-00-00-00
  UIPC response: MAC=00-00-00-00-00-00,IP=192.0.2.11,MASK=255.255.255.0
  -> IP configuration successfully saved to flash.
------------------------------------------------------------
  Network demo complete.
```

> The demo only runs with `--opm-network-demo`, because it stages and can commit
> a new IP configuration on the target device. Which device it changes is chosen
> by `--mac`; without that argument it uses the placeholder MAC and finds nothing.

---

### IL / PDL Calculation (Static)

File: `pdl_calculation.cpp`

Validates the `Calculation()` API with hard-coded simulated power data. No hardware needed.

**Inputs** (simulated, in dBm):

| Dataset | LHP | LVP | LP45 | LCP |
|---|---|---|---|---|
| Reference | -3.10 | -3.05 | -3.08 | -3.12 |
| Measurement | -6.50 | -6.30 | -6.70 | -6.40 |
| Ref monitor | -0.10 | -0.08 | -0.09 | -0.11 |
| Meas monitor | -0.12 | -0.10 | -0.11 | -0.13 |

**Outputs**: IL (dB) and PDL (dB) printed to the console.

---

### IL / PDL Wavelength Sweep (Interactive)

File: `il_pdl_sweep.cpp`

Runs an end-to-end IL/PDL measurement. Wavelength range, OPM serial number, and channel are compile-time constants.

#### Configuration

The following values are hardcoded near the top of `runILPDLSweepDemo()`:

| Constant | Default | Description |
|---|---|---|
| `startNm` | `1480` | Start wavelength (nm) |
| `stopNm` | `1640` | Stop wavelength (nm) |
| `opmSerial` | `--opm-serial` argument | OPM-150 serial number |
| `channelRequest` | `1` | Channel number, or `0` for all channels |

The serial number is the only value you are likely to change, and it comes from
the command line. The wavelength range and channel selection are compile-time
constants in `il_pdl_sweep.cpp`: change them and recompile.

#### Workflow

```
1. Select wavelength bands within [startNm, stopNm]:
      850, 980, 1300, 1310, 1490, 1550, 1625, 1650 nm

2. REFERENCE SCAN  (remove DUT, press Enter)
      For each wavelength band:
        For each of the 4 SOP states (LHP -> LVP -> LP45 -> RCP):
          SetWavelength()        - configures TSL-570 + OPM-150 band
          SetPCUSOP()            - sets polarization state on PCU-110
          ReadOPMPower()         - captures OPM-150 power reading
            or ReadOPMAllChannels() when channelRequest = 0
          ReadPCUPowerMonitor()  - captures PCU-110 monitor reading

3. MEASUREMENT SCAN  (insert DUT, press Enter)
      Same capture loop as the reference scan.

4. CALCULATE
      For each wavelength x channel:
        Calculation() -> IL (dB) and PDL (dB)

5. EXPORT  ->  il_pdl_sweep_results.csv
```

#### Supported Wavelength Bands

| Enum | Centre wavelength |
|---|---|
| `Wl850` | 850 nm |
| `Wl980` | 980 nm |
| `Wl1300` | 1300 nm |
| `Wl1310` | 1310 nm |
| `Wl1490` | 1490 nm |
| `Wl1550` | 1550 nm |
| `Wl1625` | 1625 nm |
| `Wl1650` | 1650 nm |

#### Example Console Session

```
[IL/PDL Wavelength Sweep]
------------------------------------------------------------
  Wavelength bands selected:
    1490 nm
    1550 nm
    1625 nm

--- REFERENCE SCAN ---
  Remove DUT. Connect reference path. Press ENTER when ready ...

  Wavelength 1490 nm
    SOP LHP  (Linear Horizontal)      OPM ch1 = -3.0512 dBm  monitor = -0.0842 dBm
    ...

--- MEASUREMENT SCAN ---
  Insert DUT. Press ENTER when ready ...
  ...

--- RESULTS ---
  Wavelength   Channel   IL (dB)       PDL (dB)
------------------------------------------------------------
  1490 nm      ch 1      IL = +3.4987 dB  PDL = 0.2341 dB
  1550 nm      ch 1      IL = +3.5102 dB  PDL = 0.1987 dB
  1625 nm      ch 1      IL = +3.4891 dB  PDL = 0.2108 dB

  Results exported to: il_pdl_sweep_results.csv
```

---

## API Overview

All functions are declared in `SantecLibrary.hpp` with `extern "C"` linkage and
resolved at link time from `Santec.Library.dll`.

| Function | Description |
|---|---|
| `SetLogLevel(level)` | Set minimum log verbosity |
| `GetDeviceNum()` | Return number of discoverable devices |
| `GetDevices(devices)` | Fill array with `ConnectionConfig` for each device |
| `SetConnection(dev)` | Connect to a single device |
| `Disconnect()` | Disconnect all devices and release resources |
| `GetTSLWavelength()` | Read current TSL output wavelength (nm) |
| `SetWavelength(wl)` | Set TSL wavelength band and sync OPM-150 |
| `GetTSLPower()` | Read current TSL output power (dBm) |
| `SetTSLPower(power)` | Set TSL output power (dBm) |
| `SetPCUSOP(sop)` | Set polarization state on PCU-110 |
| `ReadPCUPowerMonitor()` | Read PCU-110 internal power monitor (dBm) |
| `SetOPMChannel(serial, ch)` | Activate a channel on OPM-150 |
| `ReadOPMPower(serial)` | Read power from active OPM-150 channel (dBm) |
| `ReadOPMAllChannels(serial, &data, &len)` | Read all OPM-150 channels; caller must free with `FreeAllChannelsRead()` |
| `FreeAllChannelsRead(data)` | Free buffer returned by `ReadOPMAllChannels()` |
| `DiscoverOPMDevices()` | Enumerate NICs, broadcast discovery, cache responsive NICs; returns device list |
| `SetOPMNetworkConfig(mac, ip, mask)` | Set temporary IP/mask on cached NICs (requires discovery first) |
| `QueryOPMTempConfig()` | Query temporary config on cached NICs (requires discovery first) |
| `ApplyOPMNetworkConfig(mac)` | Commit temp config to flash on cached NICs (requires discovery first) |
| `FreeString(str)` | Free a string returned by the OPM network config functions |
| `Calculation(wl, ref, meas, refMon, measMon, &il, &pdl)` | Calculate IL and PDL from four-SOP power data |

### Key Types

```cpp
enum class NominalWavelength : uint8_t  { Unknown = 0xFF, Wl850, Wl980, Wl1300, Wl1310, Wl1490, Wl1550, Wl1625, Wl1650 }
enum class PolarizationState : uint8_t  { LVP, LHP, LP45, LN45, RCP, LCP }
enum class LogEventLevel     : int32_t  { Verbose, Debug, Information, Warning, Error, Fatal }

struct ConnectionConfig { const char* Type, *VendorName, *ProductName, *Address, *SerialNumber, *FirmwareVersion; int32_t ProductNumber; }
struct PowerData        { double Power[4]; }  // [0]=LHP  [1]=LVP  [2]=LP45  [3]=LCP
```

---

## Output Files

| File | Generated by | Contents |
|---|---|---|
| `il_pdl_sweep_results.csv` | `runILPDLSweepDemo()` | Wavelength, channel, IL (dB), PDL (dB), one row per measurement point |

The CSV goes to the **working directory** of the executable. This is the
project root when run from Visual Studio, or the folder containing the `.exe`
when run from a terminal.
