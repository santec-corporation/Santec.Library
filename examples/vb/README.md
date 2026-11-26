# VB.NET example

Controls a TSL-570 from .NET: connect, set the power and wavelength, read them
back, then run a sweep and print the length of the power logging data. It does the
same work as the [C# example](../csharp/README.md).

```powershell
dotnet run --framework net10.0 -- --help
dotnet run --framework net10.0 -- --lan 192.0.2.10:5000
dotnet run --framework net10.0        # discovers a TSL over USB or GPIB instead
```

On Windows the project also targets `net48`, so `dotnet run` there needs the
framework: pass `--framework net48` to build and run the .NET Framework version. Both
targets build as x64, because the native library is x64 only. On .NET Framework the
declarations name `Santec.Library.dll`, because that loader does not append the
extension to a name that already contains a dot.

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

Two details belong to the runtime rather than to `DllImport`:

- `Marshal.PtrToStringUTF8` arrived in .NET Core 3.0. `Native.FromUtf8` decodes the
  version string itself under `#If NETFRAMEWORK Or NETSTANDARD`, so the same file
  builds for a .NET Framework consumer of the bindings.
- `Marshal.StructureToPtr` allocates a copy of each string field. `Connect` releases
  those copies with `Marshal.DestroyStructure` before it frees the block, which is
  what keeps a reconnect loop from leaking one set of strings per call.
