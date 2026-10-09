# Python integration

There are two ways in, and they are the same code: the `santec_library` package,
and the `ctypes` calls it wraps. Start with the package unless you are debugging a
binding.

## Using the package

```bash
pip install ./python        # or ./python[numpy] for the array helpers
```

Requires 64-bit Python 3.10 or later. The library loads the DLL through `ctypes`,
so there is nothing to compile, and the same `Santec.Library.dll` the C and C++
callers use.

```python
from santec_library import Library
from santec_library.results import parse

with Library() as library:                       # finds the DLL, or pass its path
    library.enable_debug()
    for device in library.list_devices():
        print(device)

    library.set_connections(tsl, power_meter)
    library.reset_parameters()
    library.set_sweep_parameters(1480, 1640, 0.01, 0.0, 100.0)

    reference = parse(library.reference_scan())     # retries the first, laser-off scan

    problem = library.validate_parameters()
    if problem:
        raise SystemExit(f"the sweep is not valid for this hardware: {problem}")

    measurement = parse(library.measurement_scan())
    if measurement[0].insertion_loss:
        print(min(measurement[0].insertion_loss), max(measurement[0].insertion_loss))
```

What the package does for you, all of which the raw calls make you do yourself:

- finds the DLL (`--dll`-style path, `$SANTEC_LIBRARY_DLL`, the working directory,
  next to the package, or `lib/win-x64`) and refuses an older build by naming the
  entry points it is missing, rather than failing later with a `TypeError`;
- frees every buffer the library allocates, including on the error path;
- retries the first scan after connecting, which returns nothing because the call
  has just switched the laser diode on;
- turns the FlatBuffers payload into plain sequences: `parse()` returns `Sweep`
  objects with `wavelength`, `power`/`power_monitor`, or `insertion_loss` and the
  rescaled spectra;
- disconnects in `__exit__`, so `with` releases the instruments even if the body
  raises.

One thing it does not do for you: a sweep with picometre steps also needs
`library.enable_high_resolution()`, which switches the power meters to the
high-resolution path. `python/ultra_high_resolution.py` is that flow end to end , 
sweep settings, MPM channels and ranges, the two scans, and the CSV export.

`python/examples/quickstart.py` is the whole flow in one file, including the
prompts between the reference and the measurement.

## Using ctypes directly

The rest of this document is that same integration at the `ctypes` level. Read it
if you are writing your own wrapper or debugging a signature.

## Requirements

- **64-bit Python.** The DLL is x64; a 32-bit interpreter raises
  `OSError: [WinError 193] %1 is not a valid Win32 application`.
- The DLL beside your script, or an explicit path.
- `numpy` only if you use the `...AsNumpy()` result helpers. The plain flatbuffers
  accessors work without it.

## Loading the library

```python
import ctypes
import os

DLL_NAME = "Santec.Library.dll"

def load_library(explicit: str | None = None):
    for candidate in (explicit,
                      os.environ.get("SANTEC_LIBRARY_DLL"),
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), DLL_NAME),
                      os.path.join(os.getcwd(), DLL_NAME)):
        if candidate and os.path.isfile(candidate):
            return ctypes.CDLL(os.path.abspath(candidate))
    raise FileNotFoundError(f"{DLL_NAME} not found")

lib = load_library()
```

The library works regardless of the process working directory, so a full path is
always fine.

## Declaring what you call

ctypes needs the structure layout and the signatures, set them once, up front.
Getting a signature wrong here is the usual cause of a crash rather than an
exception.

```python
class ConnectionConfig(ctypes.Structure):
    """Mirrors ConnectionConfig in SantecLibrary.h: field order is the ABI."""
    _fields_ = [
        ("Type", ctypes.c_char_p),
        ("VendorName", ctypes.c_char_p),
        ("ProductName", ctypes.c_char_p),
        ("Address", ctypes.c_char_p),
        ("ProductNumber", ctypes.c_int),
        ("SerialNumber", ctypes.c_char_p),
        ("FirmwareVersion", ctypes.c_char_p),
    ]

lib.GetDeviceNum.argtypes = []
lib.GetDeviceNum.restype = ctypes.c_int

lib.GetDevices.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.GetDevices.restype = ctypes.c_int

lib.FreeConnectionConfigs.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.FreeConnectionConfigs.restype = None

lib.SetConnections.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.SetConnections.restype = ctypes.c_bool

lib.ReferenceScan.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                             ctypes.POINTER(ctypes.c_int)]
lib.ReferenceScan.restype = ctypes.c_bool

lib.FreeArrayData.argtypes = [ctypes.c_void_p]
lib.FreeArrayData.restype = None
```

## Finding and connecting instruments

```python
count = lib.GetDeviceNum()
if count <= 0:
    raise SystemExit("no instruments - check the driver and the log")

devices = (ConnectionConfig * count)()
written = lib.GetDevices(ctypes.cast(devices, ctypes.c_void_p), count)

for i in range(written):
    print(devices[i].ProductName, devices[i].SerialNumber)

# The structs stay valid until you free them, and SetConnections reads them, so
# free at the end rather than straight after listing.
try:
    tsl = next(d for d in devices if d.ProductName and b"TSL" in d.ProductName)
    pm = next(d for d in devices if d.ProductName and b"MPM" in d.ProductName)
    if not lib.SetConnections(ctypes.byref(tsl), ctypes.byref(pm), None):
        raise SystemExit("connection failed")
    ...
finally:
    lib.FreeConnectionConfigs(ctypes.cast(devices, ctypes.c_void_p), written)
    lib.Disconnect()
```

`c_char_p` members read as `bytes`, not `str`, decode them yourself. The library
marshals them with the platform default (ANSI on Windows), not UTF-8, which only
matters for non-ASCII product names:

```python
name = config.ProductName.decode("mbcs") if config.ProductName else ""
```

Pass structures by address (`byref`). Passing a struct where the DLL expects a
pointer works on x64 for large structures, but only by accident of the calling
convention, `byref` is correct and self-documenting.

## Configuring and running a sweep

```python
lib.ResetParameters()
lib.SetSweepParameters(1480.0, 1640.0, 0.01, 0.0, 100.0, 1, 0)
lib.SetMPMChannel(0, 0, 0)          # module, channel, 0 = auto range

error = lib.ValidateParameters()
if error:
    raise SystemExit(ctypes.cast(error, ctypes.c_char_p).value.decode("utf-8"))

def scan(name="ReferenceScan"):
    data = ctypes.POINTER(ctypes.c_ubyte)()
    length = ctypes.c_int(0)
    # The first scan after connecting returns False when the laser diode was off:
    # the call switches it on. Retry.
    for attempt in range(3):
        data = ctypes.POINTER(ctypes.c_ubyte)()
        length = ctypes.c_int(0)
        if getattr(lib, name)(ctypes.byref(data), ctypes.byref(length)):
            try:
                return ctypes.string_at(data, length.value)
            finally:
                lib.FreeArrayData(data)
        time.sleep(1)
    raise RuntimeError(f"{name} returned no data")

payload = scan()
```

Three things are load-bearing in that snippet:

- **a fresh out-pointer per attempt.** On failure the DLL does not always write to
  it, so reusing one can look at stale memory;
- **`FreeArrayData` in a `finally`.** The buffer belongs to the library and leaks
  otherwise, once per scan, which adds up in a sweep loop;
- **the retry.** A single `False` from the first scan is the documented
  laser-was-off behaviour, not a failure.

## Reading the result

The payload is a FlatBuffers `SweepResultSet`. The generated bindings for it live
in `python/Santec/` and are the same classes the C# code uses:

```python
from Santec.STSProcess.Process.Native.Result.SweepResultSet import SweepResultSet
from Santec.STSProcess.Process.Native.Result.SweepResult import SweepResult
from Santec.STSProcess.Process.Native.Result.ILReferenceResult import ILReferenceResult
from Santec.STSProcess.Process.Native.Result.ILResult import ILResult

result_set = SweepResultSet.GetRootAsSweepResultSet(payload, 0)

for i in range(result_set.ResultsLength()):
    entry = result_set.Results(i)

    if entry.ResultsType() == SweepResult().ILReferenceResult:
        reference = ILReferenceResult()
        reference.Init(entry.Results().Bytes, entry.Results().Pos)

        wavelength = reference.WavelengthAsNumpy()          # nm
        power = reference.Data().PowerAsNumpy()             # dBm
        monitor = reference.Data().PowerMonitorAsNumpy()

    elif entry.ResultsType() == SweepResult().ILResult:
        measurement = ILResult()
        measurement.Init(entry.Results().Bytes, entry.Results().Pos)

        insertion_loss = measurement.InsertionLoss().InsertionLossAsNumpy()

        for j in range(measurement.RescaledDataLength()):
            rescaled = measurement.RescaledData(j)
            key = rescaled.Key()                            # channel identity
            spectrum = rescaled.PowerLog().DataAsNumpy()
            monitor = rescaled.PowerMonitorLog().DataAsNumpy()
```

`SweepResult().ILReferenceResult` and `.ILResult` are the flatbuffers union type
tags: compare against them, do not construct them.

The `...AsNumpy()` helpers return numpy arrays; every one has a plain
`...Length()` / `... (index)` accessor if you would rather avoid the dependency.

## Exporting to CSV instead

If you do not need the arrays in memory:

```python
lib.ExportReferenceDataTo(b"C:\\measurements", b"ILReference")
lib.ExportMeasurementDataTo(b"C:\\measurements", b"ILMeasurement")
```

These write `<directory>\<baseName>_<channel>.csv`, one file per result; the
directory must already exist. The argument order is directory then file-name stem,
and both are `bytes`. The older zero-argument exports have no defined output
location, see [getting-started.md](getting-started.md#5-scan).

## Pitfalls

| Symptom | Cause |
|---|---|
| `OSError [WinError 193]` | 32-bit Python. Use a 64-bit interpreter. |
| Garbage bytes / `ArgumentError` | A signature is missing or wrong: without `argtypes`, ctypes passes Python objects as C ints. |
| The process exits with no traceback | An argument was wrong for an entry point that does not validate; check against the [ABI reference](abi-reference.md). |
| Memory grows across a sweep loop | A returned buffer was not freed. `FreeArrayData`, `FreeString` and `FreeConnectionConfigs` cover all of them. |
| Non-ASCII device names come out mangled | `ConnectionConfig` strings are ANSI; decode with `"mbcs"`. |
| `Scan failed` on the first scan of a session | Expected once: the laser diode was off. Retry. |

Threading is the last one: nothing in the library is thread-safe, so do not call
it from several threads, and do not read an instrument from a background thread
while a sweep runs.
