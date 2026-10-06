' SchoolSVS 포터블 종료 도우미
Option Explicit

Dim shell, fso, baseDir, pythonw, stopPy, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonw = fso.BuildPath(baseDir, "runtime\pythonw.exe")
stopPy = fso.BuildPath(baseDir, "app\stop_server.py")

If Not fso.FileExists(pythonw) Or Not fso.FileExists(stopPy) Then
  WScript.Quit 2
End If

cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & stopPy & Chr(34)
shell.Run cmd, 0, True
