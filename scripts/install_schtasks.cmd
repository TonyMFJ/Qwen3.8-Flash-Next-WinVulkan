@echo off
REM 注册 Windows 计划任务 QwenPawLlamaServerJoined（开机可用 schtasks /run 拉起服务）
REM 需管理员权限运行。默认假定解压在 C:\llama-build；其他位置请改下面 SET PKG= 一行。

set PKG=C:\llama-build

schtasks /create /tn QwenPawLlamaServerJoined /tr "%PKG%\scripts\start_llamaserver_joined.cmd" /sc onlogon /rl highest /f
if errorlevel 1 (
  echo.
  echo [!] 注册失败：请右键"以管理员身份运行"本脚本。
  pause
  exit /b 1
)
echo [OK] 任务已注册。启动服务：
echo     schtasks /run /tn QwenPawLlamaServerJoined
echo 约 2 分钟后验证: curl http://127.0.0.1:1234/health
pause
