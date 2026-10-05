' SchoolSVS 포터블 숨김 실행기
Option Explicit

Dim shell, fso, baseDir, pythonw, mainPy, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonw = fso.BuildPath(baseDir, "runtime\pythonw.exe")
mainPy = fso.BuildPath(baseDir, "app\main.py")

If Not fso.FileExists(pythonw) Then
  MsgBox "SchoolSVS 포터블 Python 실행기를 찾을 수 없습니다." & vbCrLf & _
         "runtime 폴더가 포함된 정식 배포 ZIP인지 확인하세요.", vbCritical, "SchoolSVS"
  WScript.Quit 2
End If

If Not fso.FileExists(mainPy) Then
  MsgBox "SchoolSVS 프로그램 파일(app\main.py)을 찾을 수 없습니다.", vbCritical, "SchoolSVS"
  WScript.Quit 3
End If

' 포트는 Python 엔진이 사용 가능한 localhost 포트를 자동 선택한다.
shell.Environment("Process")("SCHOOLSVS_PORT") = ""
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & mainPy & Chr(34)
shell.Run cmd, 0, False
