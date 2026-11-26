Imports System
Imports Microsoft.VisualBasic

Module Program
    ' The scan parameters suit a quick insertion-loss run on a broadband device.
    ' Change them to match the device under test.
    Private Const StartWavelength As Double = 1500.0
    Private Const StopWavelength As Double = 1600.0
    Private Const StepWidth As Double = 0.1
    Private Const SweepPower As Double = 0.0
    Private Const SweepSpeed As Double = 100.0
    Private Const SweepCycles As Integer = 1
    Private Const SweepDelay As Integer = 0

    ' The LAN details are not baked in: name the instrument you actually have on the
    ' command line. This default is a documentation address (RFC 5737).
    Private Const DocumentationAddress As String = "192.0.2.10:5000"

    Function Main(args As String()) As Integer
        Dim lan = ""
        Dim tslProduct = "TSL"
        Dim pmProduct = "MPM"

        Dim index = 0
        While index < args.Length
            Select Case args(index)
                Case "--lan"
                    If index + 1 >= args.Length Then Return MissingValue(args(index))
                    index += 1
                    lan = args(index)
                Case "--tsl-product"
                    If index + 1 >= args.Length Then Return MissingValue(args(index))
                    index += 1
                    tslProduct = args(index)
                Case "--pm-product"
                    If index + 1 >= args.Length Then Return MissingValue(args(index))
                    index += 1
                    pmProduct = args(index)
                Case "--help", "-h"
                    PrintUsage()
                    Return 0
                Case Else
                    Console.Error.WriteLine($"Unknown option: {args(index)}")
                    PrintUsage()
                    Return 2
            End Select
            index += 1
        End While

        PrintVersion()

        Dim devices = Native.ListDevices()
        For Each device In devices
            Console.WriteLine($"Device: {device.ProductName}, serial {device.SerialNumber}")
        Next

        Dim tsl = If(lan.Length > 0, LanConnection(lan, tslProduct), FindDevice(devices, tslProduct))
        Dim powerMeter = FindDevice(devices, pmProduct)

        If Not IsConfigured(tsl) Then
            Console.Error.WriteLine("No TSL found. Pass --tsl-product, or --lan for a LAN instrument.")
            Return 1
        End If
        If Not IsConfigured(powerMeter) Then
            Console.Error.WriteLine("No power meter found. Pass --pm-product with the name the device reports.")
            Return 1
        End If

        If Not Native.Connect(tsl, powerMeter) Then Return 1

        Try
            Native.ResetParameters()
            Native.SetSweepParameters(StartWavelength, StopWavelength, StepWidth,
                                      SweepPower, SweepSpeed, SweepCycles, SweepDelay)
            Native.SetMPMChannel(0, 0, 0)

            Dim problem = Native.ValidationError()
            If problem.Length > 0 Then
                Console.Error.WriteLine($"The scan parameters did not validate: {problem}")
                Return 1
            End If

            Console.WriteLine($"Reference scan: {StartWavelength} to {StopWavelength} nm, step {StepWidth} nm")
            Dim reference = Native.ReferenceScanBytes()
            If reference.Length = 0 Then
                ' A scan can fail while the laser is still switching on; the log says which.
                Console.WriteLine("Reference scan returned nothing; retrying once.")
                reference = Native.ReferenceScanBytes()
            End If
            If reference.Length = 0 Then
                Console.Error.WriteLine("The reference scan failed. Check the log for the reason.")
                Return 1
            End If
            Results.ReportReference(reference)

            Console.WriteLine("Measurement scan")
            Dim measurement = Native.MeasurementScanBytes()
            If measurement.Length = 0 Then
                Console.Error.WriteLine("The measurement scan failed. Check the log for the reason.")
                Return 1
            End If
            Results.ReportMeasurement(measurement)
        Finally
            Native.Disconnect()
        End Try

        Return 0
    End Function

    Private Function MissingValue(argument As String) As Integer
        Console.Error.WriteLine($"Missing value for {argument}")
        PrintUsage()
        Return 2
    End Function

    Private Sub PrintVersion()
        Dim value = Native.GetLibraryVersion()
        If value = IntPtr.Zero Then Return

        Try
            Console.WriteLine($"Santec.Library {Native.FromUtf8(value)}")
        Finally
            Native.FreeString(value)
        End Try
    End Sub

    Private Sub PrintUsage()
        Console.WriteLine(String.Join(vbCrLf, New String() {
            "Usage: Santec.Library.Sample.IL.Sweep [options]",
            "",
            $"  --lan <host:port>     connect the TSL over LAN, for example {DocumentationAddress}",
            "  --tsl-product <name>  product name to look for (default: TSL)",
            "  --pm-product <name>   power meter product name to look for (default: MPM)",
            "  --help                show this text",
            "",
            "Without --lan the sample discovers both instruments over USB or GPIB.",
            "Put Santec.Library.dll next to the executable, or in lib/win-x64."
        }))
    End Sub

    Private Function LanConnection(address As String, product As String) As ConnectionConfig
        Return New ConnectionConfig With {
            .Type = "LAN",
            .ProductName = product,
            .Address = address
        }
    End Function

    Private Function FindDevice(devices As ConnectionConfig(), product As String) As ConnectionConfig
        Dim found As New ConnectionConfig()
        For Each device In devices
            If device.ProductName IsNot Nothing AndAlso device.ProductName.Contains(product) Then
                found = device
            End If
        Next
        Return found
    End Function

    Private Function IsConfigured(device As ConnectionConfig) As Boolean
        Return device.ProductName IsNot Nothing AndAlso device.ProductName.Length > 0
    End Function
End Module
