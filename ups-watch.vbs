Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' Set PYTHONPATH so the src folder is found
oShell.Environment("PROCESS")("PYTHONPATH") = oShell.CurrentDirectory & "src"

' Run pythonw hidden (0 = hidden window)
oShell.Run """.venv\Scripts\pythonw.exe"" -m ups_label_cropper.__main__ --watch", 0, False
