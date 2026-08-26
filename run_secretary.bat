@echo off
chcp 65001 >nul
title telegram_secretary

echo ===================================================
echo [알파 COO 텔레그램 수석비서 데몬 런처]
echo ===================================================

echo [1/3] 기존 telegram_secretary 프로세스 강제 종료(Force Kill) 수행 중...
:: 1) WINDOWTITLE 기반 taskkill 실행
taskkill /F /IM python.exe /FI "WINDOWTITLE eq telegram_secretary*" >nul 2>&1

:: 2) PowerShell/WMI 기반 telegram_secretary.py 프로세스 정밀 강제 종료
powershell -Command "Get-CimInstance Win32_Process -Filter \"CommandLine like '%%telegram_secretary.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/3] 프로세스 세션 정리 대기 중 (1초)...
powershell -Command "Start-Sleep -Seconds 1"

echo [3/3] 텔레그램 수석비서 데몬 가동 중...
python core/telegram_secretary.py
