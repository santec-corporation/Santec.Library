using System.Runtime.InteropServices;

namespace Santec.Library.Sample.TSL.Controller;

/// <summary>
///     Connection Configuration.
/// </summary>
[StructLayout(LayoutKind.Sequential)]
public struct ConnectionConfig
{
    /// <summary>
    ///     Connection Type.
    /// </summary>
    public string Type;

    /// <summary>
    ///     Vendor Name.
    /// </summary>
    public string VendorName;

    /// <summary>
    ///     Product Name.
    /// </summary>
    public string ProductName;

    /// <summary>
    /// Address.
    /// </summary>
    public string Address;

    /// <summary>
    ///     Product Number.
    /// </summary>
    public int ProductNumber;

    /// <summary>
    ///     Serial Number.
    /// </summary>
    public string SerialNumber;

    /// <summary>
    ///     Firmware Version.
    /// </summary>
    public string FirmwareVersion;
}

/// <summary>
///     The entry points of Santec.Library.dll this sample calls, declared with
///     <c>LibraryImport</c> so the marshalling stubs are generated at compile time.
/// </summary>
internal static partial class Native
{
    /// <summary>
    ///     Santec Library DLL Name.
    /// </summary>
    private const string Library = "Santec.Library";

    /// <summary>
    ///     Sets logging mode to debug.
    /// </summary>
    public static void EnableDebugLogging() => EnableDebug();


    /// <summary>
    ///     Sets logging mode to verbose.
    /// </summary>
    public static void EnableVerboseLogging() => EnableVerbose();

    /// <summary>
    ///     Lists all the Santec GPIB and USB devices.
    /// </summary>
    /// <returns></returns>
    public static unsafe ConnectionConfig[] ListDevices()
    {
        var num = GetDeviceNum();
        if (num <= 0)
            return [];

        var configs = new ConnectionConfig[num];
        var configSize = Marshal.SizeOf<ConnectionConfig>();

        var buffer = stackalloc byte[num * configSize];

        var written = GetDevices((nint)buffer, num);

        for (var i = 0; i < written; i++)
            configs[i] = Marshal.PtrToStructure<ConnectionConfig>((nint)buffer + i * configSize)!;

        // The library allocated the strings inside the structures; release them
        // now that they have been copied into managed strings.
        FreeConnectionConfigs((nint)buffer, written);

        return configs[..written];
    }

    /// <summary>
    ///     Connects to a device.
    /// </summary>
    /// <param name="device"></param>
    /// <returns></returns>
    public static bool Connect(ConnectionConfig device)
    {
        var devicePtr = ConvertConnectionConfigToPtr(device);

        return SetConnection(devicePtr);
    }

    /// <summary>
    ///     Gets the TSL Power Logging Data.
    /// </summary>
    /// <returns></returns>
    public static unsafe double[] GetPowerLoggingData()
    {
        double* data = null;
        var dataLength = 0;

        GetTSL2PowerLoggingData(&data, &dataLength);

        try
        {
            ReadOnlySpan<double> span = new(data, dataLength);

            return span.ToArray();
        }
        finally
        {
            FreeArrayData(data);
        }
    }

    /// <summary>
    ///     Converts a ConnectionConfig config to a pointer.
    /// </summary>
    /// <param name="config"></param>
    /// <returns></returns>
    private static nint ConvertConnectionConfigToPtr(ConnectionConfig? config)
    {
        if (config == null) return nint.Zero;

        var ptr = Marshal.AllocHGlobal(Marshal.SizeOf<ConnectionConfig>());

        Marshal.StructureToPtr(config, ptr, false);

        return ptr;
    }

    #region Santec Library Functions

    [LibraryImport(Library, EntryPoint = "EnableDebug")]
    private static partial void EnableDebug();

    [LibraryImport(Library, EntryPoint = "EnableVerbose")]
    private static partial void EnableVerbose();

    [LibraryImport(Library, EntryPoint = "GetDeviceNum")]
    private static partial int GetDeviceNum();

    [LibraryImport(Library, EntryPoint = "GetDevices")]
    private static partial int GetDevices(nint devices, int capacity);

    [LibraryImport(Library, EntryPoint = "FreeConnectionConfigs")]
    private static partial void FreeConnectionConfigs(nint devices, int count);

    [LibraryImport(Library, EntryPoint = "SetConnection")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetConnection(nint devPtr);

    [LibraryImport(Library, EntryPoint = "Disconnect")]
    private static partial void Disconnect();

    [LibraryImport(Library, EntryPoint = "GetTSLWavelength")]
    internal static partial double GetTSLWavelength();

    [LibraryImport(Library, EntryPoint = "SetTSLWavelength")]
    internal static partial void SetTSLWavelength(double wavelength);

    [LibraryImport(Library, EntryPoint = "GetTSLPower")]
    internal static partial double GetTSLPower();

    [LibraryImport(Library, EntryPoint = "SetTSLPower")]
    internal static partial void SetTSLPower(double power);

    [LibraryImport(Library, EntryPoint = "GetTSLLDStatus")]
    internal static partial int GetTSLLDStatus();

    [LibraryImport(Library, EntryPoint = "SetTSLLDStatus")]
    internal static partial void SetTSLLDStatus(int status);

    [LibraryImport(Library, EntryPoint = "SetTSLSweepStartWavelength")]
    internal static partial void SetTSLSweepStartWavelength(double wavelength);

    [LibraryImport(Library, EntryPoint = "SetTSLSweepStopWavelength")]
    internal static partial void SetTSLSweepStopWavelength(double wavelength);

    [LibraryImport(Library, EntryPoint = "SetTSLSweepSpeed")]
    internal static partial void SetTSLSweepSpeed(double speed);

    [LibraryImport(Library, EntryPoint = "SetTSLSweepCycle")]
    internal static partial void SetTSLSweepCycle(int cycle);

    [LibraryImport(Library, EntryPoint = "StartTSLSweep")]
    internal static partial void StartTSLSweep();

    [LibraryImport(Library, EntryPoint = "CheckTSLBusy")]
    internal static partial int CheckTSLBusy(int waitTime);

    [LibraryImport(Library, EntryPoint = "GetTSLSweepStatus")]
    internal static partial int GetTSLSweepStatus();

    [LibraryImport(Library, EntryPoint = "SetTSLSoftwareTrigger")]
    internal static partial void SetTSLSoftwareTrigger();

    [LibraryImport(Library, EntryPoint = "GetTSL2PowerLoggingData")]
    private static unsafe partial void GetTSL2PowerLoggingData(double** data, int* length);

    [LibraryImport(Library, EntryPoint = "FreeArrayData")]
    private static unsafe partial void FreeArrayData(void* data);

    #endregion
}