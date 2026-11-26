Imports System
Imports Google.FlatBuffers
Imports Santec.STSProcess.Process.Native.Result

''' <summary>
'''     Reads the FlatBuffers payloads the scan entry points return.
''' </summary>
''' <remarks>
'''     Compare <c>SweepResultEntry.ResultsType</c> before reading a union member. The
'''     accessors do not check the tag, and the result tables overlap field for field,
'''     so a mismatched read returns another member's vectors instead of failing.
''' </remarks>
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

            Select Case entry.Value.ResultsType
                Case SweepResult.ILReferenceResult
                    Dim result = entry.Value.Results(Of ILReferenceResult)()
                    If result.HasValue Then ReportReferenceResult(result.Value)
                Case Else
                    Console.WriteLine($"  result {index}: {entry.Value.ResultsType} is not read here")
            End Select
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

            Select Case entry.Value.ResultsType
                Case SweepResult.ILResult
                    Dim result = entry.Value.Results(Of ILResult)()
                    If result.HasValue Then ReportInsertionLoss(result.Value)
                Case Else
                    Console.WriteLine($"  result {index}: {entry.Value.ResultsType} is not read here")
            End Select
        Next
    End Sub

    Private Sub ReportReferenceResult(result As ILReferenceResult)
        Dim data = result.Data
        If Not data.HasValue Then
            Console.WriteLine($"  reference: {result.WavelengthLength} wavelengths, no data table")
            Return
        End If

        Dim sweep = data.Value
        Console.WriteLine($"  reference: {result.WavelengthLength} points in {WavelengthUnitName(result.WavelengthUnit)}, " &
                          $"{sweep.PowerLength} power samples in {PowerUnitName(sweep.PowerUnit)}, " &
                          $"{sweep.PowerMonitorLength} monitor samples, polarization {sweep.Polarization}")
    End Sub

    Private Sub ReportInsertionLoss(result As ILResult)
        Dim loss = result.InsertionLoss
        If Not loss.HasValue Then
            Console.WriteLine($"  IL result: {result.WavelengthLength} wavelengths, no insertion loss data")
            Return
        End If

        Dim sweep = loss.Value
        Dim wavelengths = result.GetWavelengthArray()
        Dim values = sweep.GetInsertionLossArray()
        Dim count = Math.Min(wavelengths.Length, values.Length)
        If count = 0 Then
            Console.WriteLine("  IL result: no points")
            Return
        End If

        Dim cycle = 0
        Dim key = result.SweepKey
        If key.HasValue Then cycle = key.Value.Cycle

        Dim lowest = values(0)
        Dim highest = values(0)
        For index = 1 To count - 1
            If values(index) < lowest Then lowest = values(index)
            If values(index) > highest Then highest = values(index)
        Next

        Dim unit = WavelengthUnitName(result.WavelengthUnit)
        Console.WriteLine($"  cycle {cycle}: {count} points, " &
                          $"{wavelengths(0):F2} to {wavelengths(count - 1):F2} {unit}, " &
                          $"IL {lowest:F3} to {highest:F3} dB")

        For index = 0 To Math.Min(count, 5) - 1
            Console.WriteLine($"    {wavelengths(index),10:F2} {unit}  {values(index),8:F3} dB")
        Next
    End Sub

    ''' <summary>
    '''     Names the unit of a wavelength vector. The payload stores it as an
    '''     <c>Int32</c>: 0 is picometres, 1 is nanometres.
    ''' </summary>
    Private Function WavelengthUnitName(unit As Integer) As String
        Select Case unit
            Case 0
                Return "pm"
            Case 1
                Return "nm"
            Case Else
                Return $"unit {unit}"
        End Select
    End Function

    ''' <summary>
    '''     Names the unit of a power vector. The payload stores it as an
    '''     <c>Int32</c>: 0 is dBm, 1 is dBW.
    ''' </summary>
    Private Function PowerUnitName(unit As Integer) As String
        Select Case unit
            Case 0
                Return "dBm"
            Case 1
                Return "dBW"
            Case Else
                Return $"unit {unit}"
        End Select
    End Function
End Module
