# C# example

Controls a TSL-570 from .NET: connect, set the power and wavelength, read them
back, then run a sweep and print the length of the power logging data.

```powershell
dotnet run -- --help
dotnet run -- --lan 192.0.2.10:5000
dotnet run                       # discovers a TSL over USB or GPIB instead
```

The default address is a documentation address (RFC 5737), not a lab one: name the
instrument you actually have on the command line.

There is no managed package to install. `Native.cs` declares the entry points this
example calls with `LibraryImport`, and `ConnectionConfig` with
`StructLayout(LayoutKind.Sequential)`; the project copies
`..\..\lib\win-x64\Santec.Library.dll` next to the executable. The entry points not
used here are in [`docs/dotnet-integration.md`](../../docs/dotnet-integration.md)
and the [ABI reference](../../docs/abi-reference.md).

`LibraryImport` (rather than `DllImport`) generates the marshalling stubs at
compile time, which is what keeps the example AOT-safe. Two details in the
declarations are easy to get wrong: a `bool` return needs
`[return: MarshalAs(UnmanagedType.Bool)]` so the 4-byte Windows `BOOL` matches, and
`SetMPMChannel` takes the dynamic range as a `byte`.
