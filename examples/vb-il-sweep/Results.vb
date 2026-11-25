Imports System
Imports Google.FlatBuffers
Imports Santec.STSProcess.Process.Native.Result

''' <summary>
'''     Reads the FlatBuffers payloads the scan entry points return.
''' </summary>
Public Module Results
    ''' <summary>
    '''     Prints a summary of a reference scan payload.
    ''' </summary>
    Public Sub ReportReference(bytes As Byte())
        If bytes.Length = 0 Then
            Console.WriteLine("Reference scan returned no data.")
            Return
        End If

        Dim payload = SweepResultSet.GetRootAsSweepResultSet(New ByteBuffer(bytes))
        Console.WriteLine($"Reference payload: {payload.ResultsLength} result(s), {bytes.Length} bytes")

        For index = 0 To payload.ResultsLength - 1
            Dim entry = payload.Results(index)
            If Not entry.HasValue Then Continue For

            Dim value = entry.Value.Results(Of ILReferenceResult)()
            If Not value.HasValue Then Continue For

            Console.WriteLine($"  reference {index}: {value.Value.WavelengthLength} points")
        Next
    End Sub

    ''' <summary>
    '''     Prints a summary of a measurement scan payload.
    ''' </summary>
    Public Sub ReportMeasurement(bytes As Byte())
        If bytes.Length = 0 Then
            Console.WriteLine("Measurement scan returned no data.")
            Return
        End If

        Dim payload = SweepResultSet.GetRootAsSweepResultSet(New ByteBuffer(bytes))
        Console.WriteLine($"Measurement payload: {payload.ResultsLength} result(s), {bytes.Length} bytes")

        For index = 0 To payload.ResultsLength - 1
            Dim entry = payload.Results(index)
            If Not entry.HasValue Then Continue For
            If entry.Value.ResultsType <> SweepResult.ILResult Then Continue For

            Dim value = entry.Value.Results(Of ILResult)()
            If Not value.HasValue Then Continue For

            ReportInsertionLoss(value.Value)
        Next
    End Sub

    Private Sub ReportInsertionLoss(result As ILResult)
        Dim loss = result.InsertionLoss
        If Not loss.HasValue Then
            Console.WriteLine($"  IL result: {result.WavelengthLength} wavelengths, no insertion loss data")
            Return
        End If

        Dim sweep = loss.Value
        Dim count = Math.Min(sweep.InsertionLossLength, result.WavelengthLength)
        If count = 0 Then
            Console.WriteLine("  IL result: no points")
            Return
        End If

        Dim cycle = If(result.SweepKey.HasValue, result.SweepKey.Value.Cycle, 0)
        Console.WriteLine($"  cycle {cycle}: {count} points, {result.Wavelength(0):F2} to {result.Wavelength(count - 1):F2} nm")

        Dim lowest = Double.MaxValue
        Dim highest = Double.MinValue
        For index = 0 To count - 1
            Dim value = sweep.InsertionLoss(index)
            If value < lowest Then lowest = value
            If value > highest Then highest = value
        Next
        Console.WriteLine($"    IL {lowest:F3} to {highest:F3} dB")

        For index = 0 To Math.Min(count, 5) - 1
            Console.WriteLine($"    {result.Wavelength(index),8:F2} nm  {sweep.InsertionLoss(index),8:F3} dB")
        Next
    End Sub
End Module
