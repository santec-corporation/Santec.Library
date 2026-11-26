Imports System
Imports System.Threading
Imports Microsoft.VisualBasic

Module Program
    ' The LAN details are not baked in: this sample ships publicly, so a real
    ' instrument is named on the command line and the default is a documentation
    ' address (RFC 5737). Without --lan the sample looks for a TSL over USB or GPIB.
    Private Const DocumentationAddress As String = "192.0.2.10:5000"

    Function Main(args As String()) As Integer
        Dim lan = ""
        Dim product = "TSL"

        Dim index = 0
        While index < args.Length
            Select Case args(index)
                Case "--lan"
                    If index + 1 >= args.Length Then Return MissingValue(args(index))
                    index += 1
                    lan = args(index)
                Case "--product"
                    If index + 1 >= args.Length Then Return MissingValue(args(index))
                    index += 1
                    product = args(index)
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

        Dim tsl = If(lan.Length > 0, LanConnection(lan, product), DiscoverConnection(product))

        If Not Native.Connect(tsl) Then Return 1

        Try
            ' Set the power.
            Native.SetTSLPower(0.55)

            ' Set the wavelength.
            Native.SetTSLWavelength(1550)

            ' Get and display the power.
            Dim power = Native.GetTSLPower()
            Console.WriteLine($"TSL Power: {power}")

            ' Get and display the wavelength.
            Dim wavelength = Native.GetTSLWavelength()
            Console.WriteLine($"TSL Wavelength: {wavelength}")

            ' TSL sweep.
            Sweep(1500, 1600, 10, 1)
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
            "Usage: Santec.Library.Sample.TSL.Controller [options]",
            "",
            $"  --lan <host:port>   connect over LAN, for example {DocumentationAddress}",
            "  --product <name>    product name to look for when discovering (default: TSL)",
            "  --help              show this text",
            "",
            "Without --lan the sample lists the instruments the drivers can see and",
            "picks the first one whose product name contains --product. Put",
            "Santec.Library.dll next to the executable, or in lib/win-x64."
        }))
    End Sub

    Private Function LanConnection(address As String, product As String) As ConnectionConfig
        Return New ConnectionConfig With {
            .Type = "LAN",
            .ProductName = product,
            .Address = address
        }
    End Function

    Private Function DiscoverConnection(product As String) As ConnectionConfig
        ' Get the available Santec devices.
        Dim devices = Native.ListDevices()

        Dim found As New ConnectionConfig()
        For Each device In devices
            Console.WriteLine($"Product Name: {device.ProductName}")
            Console.WriteLine($"Serial Number: {device.SerialNumber}")

            If device.ProductName IsNot Nothing AndAlso device.ProductName.Contains(product) Then
                found = device
            End If
        Next

        Return found
    End Function

    Private Sub Sweep(startWavelength As Double, stopWavelength As Double, sweepSpeed As Double,
                      cycles As Integer)
        Native.SetTSLWavelength(1550)
        Native.SetTSLPower(1.0)
        Native.SetTSLLDStatus(1) ' LD On
        Native.SetTSLSweepStartWavelength(startWavelength)
        Native.SetTSLSweepStopWavelength(stopWavelength)
        Native.SetTSLSweepSpeed(sweepSpeed)
        Native.SetTSLSweepCycle(cycles)

        ' Run sweep.
        Native.StartTSLSweep()

        Dim width = Math.Abs(stopWavelength - startWavelength)
        Dim estimatedMilliSeconds = 1100 * (width / sweepSpeed * cycles)

        ShowSweepProgress(estimatedMilliSeconds)

        ' Read result.
        Dim current = Native.GetTSLWavelength()
        Dim status = Native.GetTSLSweepStatus()

        Console.WriteLine($"Current Wavelength: {current}")
        Console.WriteLine($"TSL Sweep Status: {status}")

        Dim powerLoggingData = Native.GetPowerLoggingData()
        Console.WriteLine($"Power Logging Data Length: {powerLoggingData.Length}")
    End Sub

    Private Sub ShowSweepProgress(estimatedMilliSeconds As Double)
        Console.CursorVisible = False
        Dim spinner = New Char() {"|"c, "/"c, "-"c, "\"c}
        Const barWidth As Integer = 20
        Dim startTime = Environment.TickCount
        Dim spin = 0

        While Native.GetTSLSweepStatus() <> 0
            Dim elapsed = Environment.TickCount - startTime
            Dim progress = Math.Min(elapsed / estimatedMilliSeconds, 0.99)
            Dim filled = CInt(Math.Truncate(progress * barWidth))
            Dim bar = New String("#"c, filled).PadRight(barWidth)
            Dim percent = CInt(progress * 100)
            Console.Write($"{vbCr}  [{bar}]  {spinner(spin Mod 4)}  Sweeping... {percent,3}%")
            spin += 1
            Thread.Sleep(100)
        End While

        Console.CursorVisible = True
        Console.WriteLine($"{vbCr}Sweep complete.                                            ")
    End Sub
End Module
