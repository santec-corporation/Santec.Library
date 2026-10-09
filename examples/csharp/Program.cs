namespace Santec.Library.Sample.TSL.Controller;

internal static class Program
{
    // The LAN details are not baked in: this sample ships publicly, so a real
    // instrument is named on the command line and the default is a documentation
    // address (RFC 5737). Without --lan the sample looks for a TSL over USB or GPIB.
    private const string DocumentationAddress = "192.0.2.10:5000";

    private static int Main(string[] args)
    {
        var lan = "";
        var product = "TSL";

        for (var i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--lan" when i + 1 < args.Length:
                    lan = args[++i];
                    break;
                case "--product" when i + 1 < args.Length:
                    product = args[++i];
                    break;
                case "--lan" or "--product":
                    Console.Error.WriteLine($"Missing value for {args[i]}");
                    PrintUsage();
                    return 2;
                case "--help" or "-h":
                    PrintUsage();
                    return 0;
                default:
                    Console.Error.WriteLine($"Unknown option: {args[i]}");
                    PrintUsage();
                    return 2;
            }
        }

        // Connect to the TSL device.
        var tsl = lan.Length > 0 ? LanConnection(lan, product) : DiscoverConnection(product);

        if (!Native.Connect(tsl))
            return 1;

        // Set the power.
        Native.SetTSLPower(0.55);

        // Set the Wavelength.
        Native.SetTSLWavelength(1550);

        // Get and display the power.
        var power = Native.GetTSLPower();
        Console.WriteLine($"TSL Power: {power}");

        // Get and display the wavelength.
        var wavelength = Native.GetTSLWavelength();
        Console.WriteLine($"TSL Wavelength: {wavelength}");

        // TSL Sweep.
        Sweep(1500, 1600, 10, 1);
        return 0;
    }

    private static void PrintUsage()
    {
        Console.WriteLine(
            $"""
             Usage: Santec.Library.Sample.TSL.Controller [options]

               --lan <host:port>   connect over LAN, for example {DocumentationAddress}
               --product <name>    product name to look for when discovering (default: TSL)
               --help              show this text

             Without --lan the sample lists the instruments the drivers can see and
             picks the first one whose product name contains --product. Put
             Santec.Library.dll next to the executable, or in lib/win-x64.
             """);
    }

    private static ConnectionConfig LanConnection(string address, string product)
    {
        return new ConnectionConfig
        {
            Type = "LAN",
            ProductName = product,
            Address = address
        };
    }

    private static ConnectionConfig DiscoverConnection(string product)
    {
        // Get the available Santec devices.
        // Gets the connected Santec GPIB and USB devices.
        var devices = Native.ListDevices();

        ConnectionConfig found = new();
        foreach (var device in devices)
        {
            Console.WriteLine($"Product Name: {device.ProductName}");
            Console.WriteLine($"Serial Number: {device.SerialNumber}");

            if (device.ProductName.Contains(product))
                found = device;
        }

        return found;
    }

    private static void Sweep(double startWavelength, double stopWavelength, double sweepSpeed, int cycles)
    {
        Native.SetTSLWavelength(1550);
        Native.SetTSLPower(1.0);
        Native.SetTSLLDStatus(1); // LD On
        Native.SetTSLSweepStartWavelength(startWavelength);
        Native.SetTSLSweepStopWavelength(stopWavelength);
        Native.SetTSLSweepSpeed(sweepSpeed);
        Native.SetTSLSweepCycle(cycles);

        // Run sweep
        Native.StartTSLSweep();

        var range = Math.Abs(stopWavelength - startWavelength);
        var estimatedMilliSeconds = 1100 * (range / sweepSpeed * cycles);

        ShowSweepProgress(estimatedMilliSeconds);

        // Read result
        var current = Native.GetTSLWavelength();
        var status = Native.GetTSLSweepStatus();

        Console.WriteLine($"Current Wavelength: {current}");
        Console.WriteLine($"TSL Sweep Status: {status}");

        var powerLoggingData = Native.GetPowerLoggingData();
        Console.WriteLine($"Power Logging Data Length: {powerLoggingData.Length}");
    }

    private static void ShowSweepProgress(double estimatedMilliSeconds)
    {
        Console.CursorVisible = false;
        var spinner = new[] { '|', '/', '-', '\\' };
        const int barWidth = 20;
        var startTime = Environment.TickCount;
        var spin = 0;
        while (Native.GetTSLSweepStatus() != 0)
        {
            var elapsed = Environment.TickCount - startTime;
            var progress = Math.Min(elapsed / estimatedMilliSeconds, 0.99);
            var filled = (int)(progress * barWidth);
            var bar = new string('#', filled).PadRight(barWidth);
            var percent = (int)(progress * 100);
            Console.Write($"\r  [{bar}]  {spinner[spin++ % 4]}  Sweeping... {percent,3}%");
            Thread.Sleep(100);
        }

        Console.CursorVisible = true;
        Console.WriteLine("\rSweep complete.                                            ");
    }
}
