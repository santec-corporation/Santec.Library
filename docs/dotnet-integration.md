# .NET integration

There is no managed wrapper assembly: the SDK is the native DLL, and a .NET caller
declares the entry points it uses. That keeps the managed side honest, the
declarations are checked against the ABI by the compiler, and avoids a wrapper
whose version has to track the library's.

`examples/csharp/` is a working project; this document explains the parts worth
copying.

## Setup

1. Reference the native library so it is copied next to your assembly:

```xml
<ItemGroup>
  <None Include="lib\win-x64\Santec.Library.dll" CopyToOutputDirectory="PreserveNewest" />
</ItemGroup>
```

2. Declare the entry points. `LibraryImport` (not `DllImport`) is the
   source-generated marshaller: it produces the stubs at compile time and AOT-safe
   code.

```csharp
using System.Runtime.InteropServices;

internal static partial class Native
{
    private const string Library = "Santec.Library";

    [LibraryImport(Library, EntryPoint = "GetLibraryVersion")]
    internal static partial nint GetLibraryVersion();

    [LibraryImport(Library, EntryPoint = "GetDeviceNum")]
    internal static partial int GetDeviceNum();

    [LibraryImport(Library, EntryPoint = "GetDevices")]
    internal static partial int GetDevices(nint devices, int capacity);

    [LibraryImport(Library, EntryPoint = "FreeConnectionConfigs")]
    internal static partial void FreeConnectionConfigs(nint devices, int count);

    [LibraryImport(Library, EntryPoint = "SetConnections")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool SetConnections(nint tsl, nint pm, nint spu);

    [LibraryImport(Library, EntryPoint = "ResetParameters")]
    internal static partial void ResetParameters();

    [LibraryImport(Library, EntryPoint = "SetSweepParameters")]
    internal static partial void SetSweepParameters(
        double startWavelength, double stopWavelength, double stepWidth,
        double power, double speed, int cycles, int delay);

    [LibraryImport(Library, EntryPoint = "SetMPMChannel")]
    internal static partial void SetMPMChannel(int moduleNumber, int channelNumber, byte range);

    [LibraryImport(Library, EntryPoint = "ValidateParameters")]
    internal static partial nint ValidateParameters();

    [LibraryImport(Library, EntryPoint = "ReferenceScan")]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static unsafe partial bool ReferenceScan(byte** data, int* length);

    [LibraryImport(Library, EntryPoint = "FreeArrayData")]
    internal static partial void FreeArrayData(nint data);

    [LibraryImport(Library, EntryPoint = "FreeString")]
    internal static partial void FreeString(nint value);

    [LibraryImport(Library, EntryPoint = "Disconnect")]
    internal static partial void Disconnect();
}
```

Two details matter: `bool` returns need `[return: MarshalAs(UnmanagedType.Bool)]`
so the 4-byte BOOL matches, and `SetMPMChannel`'s range is a `byte`. Take the rest
of the entry points from the [ABI reference](abi-reference.md).

The declarations above are `internal` so that the examples below can call them
from another class. If your public wrapper methods live in the same type, make
them `private` instead, the generated stubs work either way.

## ConnectionConfig

The struct must match the header field for field. Declare it yourself, with
`LayoutKind.Sequential` and the fields in order:

```csharp
[StructLayout(LayoutKind.Sequential)]
public struct ConnectionConfig
{
    public string Type;
    public string VendorName;
    public string ProductName;
    public string Address;
    public int ProductNumber;
    public string SerialNumber;
    public string FirmwareVersion;
}
```

The strings are marshalled by the runtime with the default charset, ANSI on
Windows, which is fine for the ASCII product names and serial numbers you will
see, but it is not UTF-8. Do not assume a non-ASCII product name survives.

Reading a device list and releasing it:

```csharp
public static unsafe ConnectionConfig[] ListDevices()
{
    var count = Native.GetDeviceNum();
    if (count <= 0) return [];

    var size = Marshal.SizeOf<ConnectionConfig>();
    var buffer = stackalloc byte[count * size];

    var written = Native.GetDevices((nint)buffer, count);

    var configs = new ConnectionConfig[written];
    for (var i = 0; i < written; i++)
        configs[i] = Marshal.PtrToStructure<ConnectionConfig>((nint)buffer + i * size)!;

    // The library allocated the strings inside the structures: release them now
    // that they have been copied into managed strings.
    Native.FreeConnectionConfigs((nint)buffer, written);

    return configs;
}
```

`stackalloc` is only safe because the count is bounded by the devices physically
attached. If you would rather not rely on that, allocate with `Marshal.AllocHGlobal`
and free it in a `finally`.

Connecting is the same pattern: allocate a `ConnectionConfig`, `StructureToPtr` it,
and pass the pointer.

```csharp
var tslPtr = Marshal.AllocHGlobal(Marshal.SizeOf<ConnectionConfig>());
try
{
    Marshal.StructureToPtr(tsl, tslPtr, false);
    // ... likewise for the power meter ...
    if (!Native.SetConnections(tslPtr, pmPtr, nint.Zero))
        throw new InvalidOperationException("Could not connect the instruments");
}
finally
{
    Marshal.FreeHGlobal(tslPtr);
}
```

## Running a sweep

```csharp
Native.ResetParameters();
Native.SetSweepParameters(1480.0, 1640.0, 0.01, 0.0, 100.0, 1, 0);
Native.SetMPMChannel(0, 0, 0);   // module, channel, 0 = auto range

var error = Native.ValidateParameters();
if (error != nint.Zero)
{
    var message = Marshal.PtrToStringUTF8(error);
    Native.FreeString(error);
    throw new InvalidOperationException(message);
}

byte* data = null;
var length = 0;
if (!Native.ReferenceScan(&data, &length))
{
    // Either the laser diode was off (it has just been switched on, call again)
    // or nothing is connected. The log says which.
}
else
{
    var bytes = new ReadOnlySpan<byte>(data, length).ToArray();
    Native.FreeArrayData((nint)data);   // free as soon as you have copied it
    // bytes now holds a FlatBuffers SweepResultSet
}

Native.Disconnect();
```

Copy the payload before freeing the pointer. Holding `data` and freeing it later
is the usual source of "it worked, then the numbers were garbage".

## Reading the result

`bytes` is a FlatBuffers `SweepResultSet` (see
[python-integration.md](python-integration.md) for the object graph). To read it
from .NET you need the generated FlatBuffers classes for the same schema version.
If you only need numbers in a file, skip the parsing entirely:

```csharp
Native.ExportReferenceDataTo(nintPath("C:\\measurements"), nintPath("ILReference"));
```

or write your own CSV from the parsed data.

## Threading

The library is not thread-safe: the device cache, the parameter builders and the
cached results are shared static state. Serialize every call, a single dedicated
thread (or an `async` pipeline that never overlaps), and do not scan from two
places at once. `Disconnect()` in a `finally` or an `IDisposable.Dispose`.

## Errors

Nothing throws across the boundary, and an exception escaping an entry point would
terminate your process rather than propagate. Every call reports failure through
its return value (`false`, `0`, `NaN`, null) and writes the reason to
`%APPDATA%\Santec\SantecLibrary\logs`. Call `EnableDebug()` while integrating and
read that file; it is the only diagnostic the library produces.

## AOT

The library is Native AOT itself, and the `LibraryImport` declarations above are
AOT- and trim-safe by construction. There is no reflection in this path.
