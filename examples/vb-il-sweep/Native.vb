Imports System.Runtime.InteropServices

''' <summary>
'''     Connection Configuration.
''' </summary>
<StructLayout(LayoutKind.Sequential)>
Public Structure ConnectionConfig
    Public Type As String
    Public VendorName As String
    Public ProductName As String
    Public Address As String
    Public ProductNumber As Integer
    Public SerialNumber As String
    Public FirmwareVersion As String
End Structure

''' <summary>
'''     The entry points this example calls. VB cannot use <c>LibraryImport</c>, so the
'''     declarations use <c>DllImport</c>.
''' </summary>
Friend Module Native
#If NETFRAMEWORK Then
    ' The .NET Framework loader does not append ".dll" to a name that already
    ' contains a dot, and this target runs on Windows only.
    Private Const LibraryName As String = "Santec.Library.dll"
#Else
    ' .NET appends the platform's extension, so the bare name resolves
    ' Santec.Library.dll on Windows and Santec.Library.so on Linux.
    Private Const LibraryName As String = "Santec.Library"
#End If

    <DllImport(LibraryName, EntryPoint:="GetLibraryVersion")>
    Friend Function GetLibraryVersion() As IntPtr
    End Function

    <DllImport(LibraryName, EntryPoint:="FreeString")>
    Friend Sub FreeString(value As IntPtr)
    End Sub

    <DllImport(LibraryName, EntryPoint:="GetDeviceNum")>
    Friend Function GetDeviceNum() As Integer
    End Function

    <DllImport(LibraryName, EntryPoint:="GetDevices")>
    Friend Function GetDevices(devices As IntPtr, capacity As Integer) As Integer
    End Function

    <DllImport(LibraryName, EntryPoint:="FreeConnectionConfigs")>
    Friend Sub FreeConnectionConfigs(devices As IntPtr, count As Integer)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetConnections")>
    Friend Function SetConnections(tslPtr As IntPtr, mpmPtr As IntPtr, pcuPtr As IntPtr,
                                   spuPtr As IntPtr) As <MarshalAs(UnmanagedType.Bool)> Boolean
    End Function

    <DllImport(LibraryName, EntryPoint:="Disconnect")>
    Friend Sub Disconnect()
    End Sub

    <DllImport(LibraryName, EntryPoint:="ResetParameters")>
    Friend Sub ResetParameters()
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetSweepParameters")>
    Friend Sub SetSweepParameters(startWavelength As Double, stopWavelength As Double,
                                  stepWidth As Double, power As Double, speed As Double,
                                  cycles As Integer, delay As Integer)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetMPMChannel")>
    Friend Sub SetMPMChannel(moduleNumber As Integer, channelNumber As Integer, rangeProfile As Byte)
    End Sub

    <DllImport(LibraryName, EntryPoint:="ValidateParameters")>
    Friend Function ValidateParameters() As IntPtr
    End Function

    <DllImport(LibraryName, EntryPoint:="ReferenceScan")>
    Friend Function ReferenceScan(ByRef data As IntPtr, ByRef length As Integer) As <MarshalAs(UnmanagedType.Bool)> Boolean
    End Function

    <DllImport(LibraryName, EntryPoint:="MeasurementScan")>
    Friend Function MeasurementScan(ByRef data As IntPtr, ByRef length As Integer) As <MarshalAs(UnmanagedType.Bool)> Boolean
    End Function

    <DllImport(LibraryName, EntryPoint:="FreeArrayData")>
    Friend Sub FreeArrayData(data As IntPtr)
    End Sub

    ''' <summary>
    '''     Connects a TSL and a power meter. The PCU and DAQ slots stay empty.
    ''' </summary>
    Friend Function Connect(tsl As ConnectionConfig, powerMeter As ConnectionConfig) As Boolean
        Dim size = Marshal.SizeOf(Of ConnectionConfig)()
        Dim tslPtr = Marshal.AllocHGlobal(size)
        Dim meterPtr = Marshal.AllocHGlobal(size)
        Try
            Marshal.StructureToPtr(tsl, tslPtr, False)
            Marshal.StructureToPtr(powerMeter, meterPtr, False)
            Return SetConnections(tslPtr, meterPtr, IntPtr.Zero, IntPtr.Zero)
        Finally
            ' StructureToPtr allocated a copy of each string. The library copied the
            ' fields during the call, so release the copies and then the blocks.
            Marshal.DestroyStructure(tslPtr, GetType(ConnectionConfig))
            Marshal.DestroyStructure(meterPtr, GetType(ConnectionConfig))
            Marshal.FreeHGlobal(meterPtr)
            Marshal.FreeHGlobal(tslPtr)
        End Try
    End Function

    ''' <summary>
    '''     Lists the instruments the drivers can see.
    ''' </summary>
    Friend Function ListDevices() As ConnectionConfig()
        Dim count = GetDeviceNum()
        If count <= 0 Then Return Array.Empty(Of ConnectionConfig)()

        Dim size = Marshal.SizeOf(Of ConnectionConfig)()
        Dim buffer = Marshal.AllocHGlobal(count * size)
        Dim written = 0
        Try
            written = GetDevices(buffer, count)
            If written <= 0 Then Return Array.Empty(Of ConnectionConfig)()

            Dim configs(written - 1) As ConnectionConfig
            For index = 0 To written - 1
                configs(index) = Marshal.PtrToStructure(Of ConnectionConfig)(buffer + index * size)
            Next
            Return configs
        Finally
            FreeConnectionConfigs(buffer, written)
            Marshal.FreeHGlobal(buffer)
        End Try
    End Function

    ''' <summary>
    '''     Returns the validation message, or an empty string when the parameters pass.
    ''' </summary>
    Friend Function ValidationError() As String
        Dim pointer = ValidateParameters()
        If pointer = IntPtr.Zero Then Return ""

        Try
            Return FromUtf8(pointer)
        Finally
            FreeString(pointer)
        End Try
    End Function

    ''' <summary>
    '''     Decodes a UTF-8 string the library allocated. <c>PtrToStringUTF8</c> arrived in
    '''     .NET Core 3.0, so projects on .NET Framework or .NET Standard decode the bytes
    '''     themselves.
    ''' </summary>
    Friend Function FromUtf8(pointer As IntPtr) As String
        If pointer = IntPtr.Zero Then Return ""

#If NETFRAMEWORK Or NETSTANDARD Then
        Dim length = 0
        While Marshal.ReadByte(pointer, length) <> 0
            length += 1
        End While

        If length = 0 Then Return ""

        Dim bytes(length - 1) As Byte
        Marshal.Copy(pointer, bytes, 0, length)
        Return System.Text.Encoding.UTF8.GetString(bytes)
#Else
        Return Marshal.PtrToStringUTF8(pointer)
#End If
    End Function

    ''' <summary>
    '''     Runs the reference scan and copies the payload out of the library buffer.
    ''' </summary>
    Friend Function ReferenceScanBytes() As Byte()
        Dim data As IntPtr = IntPtr.Zero
        Dim length As Integer = 0
        If Not ReferenceScan(data, length) Then Return Array.Empty(Of Byte)()
        Return CopyAndFree(data, length)
    End Function

    ''' <summary>
    '''     Runs the measurement scan and copies the payload out of the library buffer.
    ''' </summary>
    Friend Function MeasurementScanBytes() As Byte()
        Dim data As IntPtr = IntPtr.Zero
        Dim length As Integer = 0
        If Not MeasurementScan(data, length) Then Return Array.Empty(Of Byte)()
        Return CopyAndFree(data, length)
    End Function

    Private Function CopyAndFree(data As IntPtr, length As Integer) As Byte()
        Try
            If length <= 0 Then Return Array.Empty(Of Byte)()

            Dim bytes(length - 1) As Byte
            Marshal.Copy(data, bytes, 0, length)
            Return bytes
        Finally
            If data <> IntPtr.Zero Then FreeArrayData(data)
        End Try
    End Function
End Module
