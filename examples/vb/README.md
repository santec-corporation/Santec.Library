# VB.NET example

Controls a TSL-570 from .NET: connect, set the power and wavelength, read them
back, then run a sweep and print the length of the power logging data. It does the
same work as the [C# example](../csharp/README.md).

```powershell
dotnet run -- --help
dotnet run -- --lan 192.0.2.10:5000
dotnet run                       # discovers a TSL over USB or GPIB instead
```

The default address is a documentation address (RFC 5737), not a lab one: name the
instrument you actually have on the command line.

There is no managed package to install. `Native.vb` declares the entry points this
example calls, and the project copies `..\..\lib\win-x64\Santec.Library.dll` next to
the executable. The entry points not used here are in
[`docs/dotnet-integration.md`](../../docs/dotnet-integration.md) and the
[ABI reference](../../docs/abi-reference.md).

VB.NET cannot use `LibraryImport`: the source generator needs a `Partial` method,
and VB allows those only for `Sub`. The declarations use `DllImport`, and four
details follow from it:

- A `bool` return marshals as a 4-byte Win32 `BOOL` only when the declaration says
  so: `As <MarshalAs(UnmanagedType.Bool)> Boolean`.
- `Declare` takes a string literal for `Lib`, never a constant (`BC30217`), so the
  declarations use `<DllImport>` with a `Const`.
- VB has no `stackalloc`, so `ListDevices` allocates with `Marshal.AllocHGlobal`
  and frees it in a `Finally`.
- `GetTSL2PowerLoggingData` takes a pointer to a pointer and a pointer to a length,
  which VB declares as `ByRef IntPtr` and `ByRef Integer`, then copies the samples
  out with `Marshal.Copy`.
