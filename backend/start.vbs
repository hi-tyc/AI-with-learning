Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d " & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & " && .\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 6003 > server.log 2>&1", 0, False
Set WshShell = Nothing
