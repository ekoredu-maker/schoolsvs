' SchoolSVS 포터블 숨김 실행기
Option Explicit

Dim shell, fso, baseDir, pythonExe, entryPy, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonExe = fso.BuildPath(baseDir, "runtime\python.exe")
entryPy = fso.BuildPath(baseDir, "app\portable_entry.py")

If Not fso.FileExists(pythonExe) Then
  MsgBox "SchoolSVS 포터블 Python 실행기를 찾을 수 없습니다." & vbCrLf & _
         "runtime 폴더가 포함된 정식 배포 ZIP인지 확인하세요.", vbCritical, "SchoolSVS"
  WScript.Quit 2
End If

If Not fso.FileExists(entryPy) Then
  MsgBox "SchoolSVS 프로그램 파일(app\portable_entry.py)을 찾을 수 없습니다.", vbCritical, "SchoolSVS"
  WScript.Quit 3
End If

shell.Environment("Process")("SCHOOLSVS_PORT") = ""
cmd = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & entryPy & Chr(34)
' 창은 숨기되 Python 자체의 오류처리(MessageBox/startup.log)는 유지한다.
shell.Run cmd, 0, False
