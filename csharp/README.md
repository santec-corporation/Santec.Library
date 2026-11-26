# C# FlatBuffers bindings

Reads the payloads `Santec.Library.dll` returns: reference and measurement scans
come back as FlatBuffers byte arrays, and these classes are the generated accessors
for them. C# and VB.NET callers use the same assembly.

`tools/generate_csharp_bindings.py` generates the classes from the schemas in the
private `Santec.FlatBuffers.Shared` submodule and vendors them here, so this folder
builds and ships without the submodule. They target **.NET Standard 2.0**, which is
what .NET Framework 4.6.1 and later, VB.NET and every modern .NET can all consume.

## Use

Reference the project (or the built `Santec.Library.FlatBuffers.dll`) and add the
runtime, which is not vendored:

```xml
<PackageReference Include="Google.FlatBuffers" Version="25.2.10" />
```

The bytes arrive from an entry point such as `ReferenceScan` or `MeasurementScan`.
Copy them before freeing the pointer, then read them:

```csharp
using Google.FlatBuffers;
using Santec.STSProcess.Process.Native.Result;

var set = SweepResultSet.GetRootAsSweepResultSet(new ByteBuffer(bytes));
for (var i = 0; i < set.ResultsLength; i++)
{
    var entry = set.Results(i);
    if (entry is null) continue;

    switch (entry.Value.ResultsType)
    {
        case SweepResult.ILResult:
            var il = entry.Value.ResultsAsILResult();
            Console.WriteLine($"{il.WavelengthLength} points, cycle {il.SweepKey?.Cycle}");
            break;
    }
}
```

`bytes` is the copy you made after the call returned; parsing the pointer after
`FreeArrayData` reads freed memory. The declarations that produce `bytes` are in
`docs/dotnet-integration.md` in the public repository, and `docs/abi-reference.md`
lists every entry point and which call frees what.

The tag check in that loop is load-bearing. `ResultsAsILResult()` and the generated
`Results<T>()` do not compare `ResultsType`: `Results<T>()` reinterprets whatever
table the union holds, and the result tables overlap field for field, so reading a
measurement entry as a reference returns the measurement's power vector as the
reference power. `ResultsAsILResult()` throws on a mismatch instead. Neither is a
substitute for the switch.

## Units

`WavelengthUnit` and `PowerUnit` name the unit of the vector beside them, and the
payload stores them as plain integers:

| Field | 0 | 1 |
|---|---|---|
| `ILResult.WavelengthUnit`, `ILReferenceResult.WavelengthUnit` | pm | nm |
| `SweepData.PowerUnit`, `ILSweepData.PowerUnit` | dBm | dBW |

They are `WavelengthUnit` and `PowerLevelUnit`, the enums the managed result types
use. Read the field rather than casting it through an enum of the same name from the
instrument-parameter layer: that one numbers pm and dBm as 2 and 3 and treats 0 as
unknown, so a payload read through it mislabels a picometre sweep as unknown and a
dBm vector as mW.

## Regenerate

`Santec/` is wholly generated. Do not edit it: a run deletes whatever the current
schemas do not produce, so a hand edit would be lost on the next bump.

```powershell
python tools/generate_csharp_bindings.py           # rewrite csharp/Santec
python tools/generate_csharp_bindings.py --check   # fail when it is stale
```

The generator runs the submodule's own `flatc.exe`, so the C# tree here and the
Python bindings in `python/Santec` are always compiled by the same compiler. It needs
the submodule (`git submodule update --init`) and no network.

## The runtime version guard

flatc stamps its version into every generated type:

```csharp
public static void ValidateVersion() { FlatBufferConstants.FLATBUFFERS_25_12_19(); }
```

The runtime declares only its own version, and the newest published
`Google.FlatBuffers` is 25.2.10, older than the submodule's flatc. The generator
rewrites that call to the version this project pins, so the generated classes
compile against the runtime they ship with. Change the pin and regenerate, and the
guard follows; `--check` fails when the tree and the pin disagree.
