On Error Resume Next
Set oFSO = CreateObject("Scripting.FileSystemObject")
sDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = sDir

' Log startup attempt
Set oLogFile = oFSO.OpenTextFile(sDir & "ups-watch.log", 8, True)
oLogFile.WriteLine Now & " - Starting ups_label_cropper..."
oLogFile.WriteLine "Working dir=" & sDir

sPyExe = sDir & ".venv\Scripts\pythonw.exe"
oLogFile.WriteLine "Python exe: " & sPyExe
If Not oFSO.FileExists(sPyExe) Then
    oLogFile.WriteLine "ERROR: pythonw.exe not found at expected path"
End If

' Use cmd /c to run with PYTHONPATH set inline (more reliable environment inheritance)
sCmd = "cmd /c ""set PYTHONPATH=" & sDir & "src && """ & sPyExe & """ -m ups_label_cropper.__main__ --watch"""
oLogFile.WriteLine "Running: " & sCmd

' Run hidden (0 = hidden window), wait for exit = False
iResult = oShell.Run(sCmd, 0, False)
oLogFile.WriteLine "Run result: " & iResult
If Err.Number <> 0 Then
    oLogFile.WriteLine "Error: " & Err.Number & " - " & Err.Description
End If
oLogFile.Close
