# VB.NET results example

Runs an insertion-loss sweep and reads the result. It finds a TSL and a power
meter, connects both, configures 1500 to 1600 nm, runs the reference and
measurement scans, then parses the FlatBuffers payload and prints the IL range and
the first points. A scan needs hardware and your reference path; the build does
not.

```powershell
dotnet run --framework net10.0 -- --help
dotnet run --framework net10.0 -- --lan 192.0.2.10:5000           # TSL over LAN
dotnet run --framework net10.0                                    # both discovered over USB or GPIB
dotnet run --framework net10.0 -- --tsl-product TSL-570 --pm-product MPM-210
```

On Windows the project also targets `net48`, so `dotnet run` there needs the
framework: pass `--framework net48` to build and run the .NET Framework version. Both
targets build as x64, because the native library is x64 only. On .NET Framework the
declarations name `Santec.Library.dll`, because that loader does not append the
extension to a name that already contains a dot.

The default address is a documentation address (RFC 5737), not a lab one.

## Reading the payload

`ReferenceScan` and `MeasurementScan` allocate a FlatBuffers buffer that you copy
and free. `Results.vb` does that, then reads the result set:

```vb
Dim payload = SweepResultSet.GetRootAsSweepResultSet(New ByteBuffer(bytes))
For index = 0 To payload.ResultsLength - 1
    Dim entry = payload.Results(index)
    If Not entry.HasValue Then Continue For

    Select Case entry.Value.ResultsType
        Case SweepResult.ILReferenceResult
            Dim result = entry.Value.Results(Of ILReferenceResult)()
            If result.HasValue Then ReportReferenceResult(result.Value)
        Case SweepResult.ILResult
            Dim result = entry.Value.Results(Of ILResult)()
            If result.HasValue Then ReportInsertionLoss(result.Value)
    End Select
Next
```

Compare `ResultsType` before reading a union member. `Results(Of T)()` does not
check the tag, and the result tables overlap field for field: a measurement read as
a reference returns the measurement's power vector as the reference power, with the
right wavelengths and no exception. `ResultsAsILResult()` fails the other way and
throws when the entry holds another member, which is no better.

The reference result carries `Data` (`power`, `power_monitor`, `polarization`), and
`Results.vb` reports it: the reference power is what the IL calculation is
subtracted from.

## Units

The unit of each vector is an `Int32` in the payload, and the values are easy to
guess wrong:

| Field | 0 | 1 |
|---|---|---|
| `WavelengthUnit` | pm | nm |
| `PowerUnit` | dBm | dBW |

Read the field and label the numbers with it. Zero is not "unknown": it is pm and
dBm, and an enum of the same name from the instrument-parameter layer numbers pm
and dBm as 2 and 3 instead. A picometre sweep stores picometres, so printing them
as nm is off by 1000.

The bindings project at
[`csharp/Santec.Library.FlatBuffers.csproj`](../../csharp/Santec.Library.FlatBuffers.csproj)
compiles the generated classes for .NET Standard 2.0 and brings the
`Google.FlatBuffers` runtime in transitively, so the project reference is the only
thing this example adds. Referencing the built `Santec.Library.FlatBuffers.dll`
instead means adding `Google.FlatBuffers` 25.2.10 to the consuming project
yourself.

The scan parameters are constants at the top of `Program.vb`; change them for the
device under test. Without a reference path and a measurement path the first scan
fails and the log names the cause.
