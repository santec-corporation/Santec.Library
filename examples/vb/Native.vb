Imports System.Runtime.InteropServices

''' <summary>
'''     Connection Configuration.
''' </summary>
<StructLayout(LayoutKind.Sequential)>
Public Structure ConnectionConfig
    ''' <summary>
    '''     Connection Type.
    ''' </summary>
    Public Type As String

    ''' <summary>
    '''     Vendor Name.
    ''' </summary>
    Public VendorName As String

    ''' <summary>
    '''     Product Name.
    ''' </summary>
    Public ProductName As String

    ''' <summary>
    '''     Address.
    ''' </summary>
    Public Address As String

    ''' <summary>
    '''     Product Number.
    ''' </summary>
    Public ProductNumber As Integer

    ''' <summary>
    '''     Serial Number.
    ''' </summary>
    Public SerialNumber As String

    ''' <summary>
    '''     Firmware Version.
    ''' </summary>
    Public FirmwareVersion As String
End Structure

''' <summary>
'''     The entry points of Santec.Library.dll this sample calls. VB cannot use
'''     <c>LibraryImport</c>: the source generator needs a partial method, and VB allows
'''     those only for <c>Sub</c>. These declarations use <c>DllImport</c> instead.
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

    ' The runtime marshals a plain Boolean return as a 4-byte Win32 BOOL, which is what
    ' the library returns. The attribute spells that out so it cannot drift.
    <DllImport(LibraryName, EntryPoint:="SetConnection")>
    Friend Function SetConnection(devPtr As IntPtr) As <MarshalAs(UnmanagedType.Bool)> Boolean
    End Function

    <DllImport(LibraryName, EntryPoint:="Disconnect")>
    Friend Sub Disconnect()
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetTSLPower")>
    Friend Sub SetTSLPower(power As Double)
    End Sub

    <DllImport(LibraryName, EntryPoint:="GetTSLPower")>
    Friend Function GetTSLPower() As Double
    End Function

    <DllImport(LibraryName, EntryPoint:="SetTSLWavelength")>
    Friend Sub SetTSLWavelength(wavelength As Double)
    End Sub

    <DllImport(LibraryName, EntryPoint:="GetTSLWavelength")>
    Friend Function GetTSLWavelength() As Double
    End Function

    <DllImport(LibraryName, EntryPoint:="SetTSLLDStatus")>
    Friend Sub SetTSLLDStatus(status As Integer)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetTSLSweepStartWavelength")>
    Friend Sub SetTSLSweepStartWavelength(wavelength As Double)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetTSLSweepStopWavelength")>
    Friend Sub SetTSLSweepStopWavelength(wavelength As Double)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetTSLSweepSpeed")>
    Friend Sub SetTSLSweepSpeed(speed As Double)
    End Sub

    <DllImport(LibraryName, EntryPoint:="SetTSLSweepCycle")>
    Friend Sub SetTSLSweepCycle(cycle As Integer)
    End Sub

    <DllImport(LibraryName, EntryPoint:="StartTSLSweep")>
    Friend Sub StartTSLSweep()
    End Sub

    <DllImport(LibraryName, EntryPoint:="GetTSLSweepStatus")>
    Friend Function GetTSLSweepStatus() As Integer
    End Function

    ' The library fills a double** and an int*. VB has no pointer types, so the two
    ' parameters are ByRef and the buffer is copied out with Marshal.Copy.
    <DllImport(LibraryName, EntryPoint:="GetTSL2PowerLoggingData")>
    Friend Sub GetTSL2PowerLoggingData(ByRef data As IntPtr, ByRef length As Integer)
    End Sub

    <DllImport(LibraryName, EntryPoint:="FreeArrayData")>
    Friend Sub FreeArrayData(data As IntPtr)
    End Sub

    ''' <summary>
    '''     Connects to a device.
    ''' </summary>
    ''' <param name="device">The configuration to connect with.</param>
    ''' <returns><c>True</c> when the connection was established.</returns>
    Friend Function Connect(device As ConnectionConfig) As Boolean
        Dim configuration = Marshal.AllocHGlobal(Marshal.SizeOf(Of ConnectionConfig)())
        Try
            Marshal.StructureToPtr(device, configuration, False)
            Return SetConnection(configuration)
        Finally
            ' StructureToPtr allocated a copy of each string. The library copied the
            ' fields during the call, so release the copies and then the block.
            Marshal.DestroyStructure(configuration, GetType(ConnectionConfig))
            Marshal.FreeHGlobal(configuration)
        End Try
    End Function

    ''' <summary>
    '''     Lists the Santec GPIB, USB and LAN devices the drivers can see.
    ''' </summary>
    ''' <returns>The devices, with the library-allocated strings copied out.</returns>
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
            For i = 0 To written - 1
                configs(i) = Marshal.PtrToStructure(Of ConnectionConfig)(buffer + i * size)
            Next

            Return configs
        Finally
            ' The library allocated the strings inside each structure. Release them
            ' now that the values live in managed strings.
            FreeConnectionConfigs(buffer, written)
            Marshal.FreeHGlobal(buffer)
        End Try
    End Function

    ''' <summary>
    '''     Reads the TSL power logging data collected during a sweep.
    ''' </summary>
    ''' <returns>The samples, copied out of the library's buffer.</returns>
    Friend Function GetPowerLoggingData() As Double()
        Dim data As IntPtr = IntPtr.Zero
        Dim length As Integer = 0
        GetTSL2PowerLoggingData(data, length)

        If data = IntPtr.Zero OrElse length <= 0 Then Return Array.Empty(Of Double)()

        Try
            Dim values(length - 1) As Double
            Marshal.Copy(data, values, 0, length)
            Return values
        Finally
            FreeArrayData(data)
        End Try
    End Function

    ''' <summary>
    '''     Decodes a UTF-8 string the library allocated. <c>PtrToStringUTF8</c> arrived in
    '''     .NET Core 3.0, so projects on .NET Framework or .NET Standard decode the bytes
    '''     themselves.
    ''' </summary>
    ''' <param name="pointer">A string the library allocated.</param>
    ''' <returns>The decoded value, or an empty string for a null pointer.</returns>
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
End Module
