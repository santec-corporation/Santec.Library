# VB.NET results example

Runs an insertion-loss sweep and reads the result. It finds a TSL and a power
meter, connects both, configures 1500 to 1600 nm, runs the reference and
measurement scans, then parses the FlatBuffers payload and prints the IL range and
the first points. A scan needs hardware and your reference path; the build does
not.

```powershell
dotnet run -- --help
dotnet run -- --lan 192.0.2.10:5000                    # TSL over LAN
dotnet run                                             # both discovered over USB or GPIB
dotnet run -- --tsl-product TSL-570 --pm-product MPM-210
```

The default address is a documentation address (RFC 5737), not a lab one.

## Reading the payload

`ReferenceScan` and `MeasurementScan` allocate a FlatBuffers buffer that you copy
and free. `Results.vb` does that, then reads the result set:

```vb
Dim payload = SweepResultSet.GetRootAsSweepResultSet(New ByteBuffer(bytes))
For index = 0 To payload.ResultsLength - 1
    Dim entry = payload.Results(index)
    If Not entry.HasValue Then Continue For
    If entry.Value.ResultsType <> SweepResult.ILResult Then Continue For

    Dim value = entry.Value.Results(Of ILResult)()
    If Not value.HasValue Then Continue For
    ' value.Value.InsertionLoss is the IL sweep
Next
```

`SweepResultEntry.Results(Of T)()` returns a nullable, so the type check and the
`HasValue` check both stay in the code; reading `ResultsAsILResult()` directly
throws when the union holds another result type.

The bindings project at
[`csharp/Santec.Library.FlatBuffers.csproj`](../../csharp/Santec.Library.FlatBuffers.csproj)
compiles the generated classes for .NET Standard 2.0 and brings the
`Google.FlatBuffers` runtime in transitively, so the project reference is the only
thing this example adds.

The scan parameters are constants at the top of `Program.vb`; change them for the
device under test. Without a reference path and a measurement path the first scan
fails and the log names the cause.
