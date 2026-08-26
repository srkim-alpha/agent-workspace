import os
import sys
import time
import subprocess
import psutil

# Windows 콘솔 인코딩 대응 (UTF-8 설정)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def kill_existing_secretary():
    print("===================================================")
    print("[알파 COO 텔레그램 수석비서 데몬 런처]")
    print("===================================================")
    print("[1/3] 기존 telegram_secretary 프로세스 강제 종료(Force Kill) 수행 중...")

    # 1. WINDOWTITLE 기반 taskkill 명령 실행
    try:
        subprocess.run(
            'taskkill /F /IM python.exe /FI "WINDOWTITLE eq telegram_secretary*"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    # 2. psutil 및 WMI 기반 telegram_secretary.py 프로세스 정밀 탐색 및 강제 종료
    current_pid = os.getpid()
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
            cmdline = proc.info['cmdline']
            if cmdline and any('telegram_secretary.py' in str(arg) for arg in cmdline):
                print(f"  └─ 기존 telegram_secretary 프로세스 (PID: {proc.info['pid']}) 강제 종료 완료.")
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if killed_count == 0:
        print("  └─ 실행 중인 기존 데몬 프로세스가 없거나 정리가 완료되었습니다.")

    time.sleep(1)

def run_daemon():
    print("[2/3] 프로세스 정리 및 세션 대기 완료.")
    print("[3/3] 텔레그램 수석비서 데몬 가동 시작...")

    if os.name == 'nt':
        os.system('title telegram_secretary')

    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_dir, "core", "telegram_secretary.py")

    # 데몬 프로세스 실행
    subprocess.run([sys.executable, script_path])

if __name__ == "__main__":
    kill_existing_secretary()
    run_daemon()
