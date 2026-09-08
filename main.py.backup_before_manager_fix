import os
import signal
import subprocess
import sys
import time


def run_bots():
    print("🚀 [IBEKS SYSTEM] Menyalakan IBEKS Manager Bot & Userbot Runner...", flush=True)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    manager_main = os.path.join(base_dir, "manager", "main.py")
    manager_process = None
    stopping = False

    def handle_signal(sig, _frame):
        nonlocal stopping, manager_process
        if stopping:
            return
        stopping = True
        print("\n🛑 [IBEKS SYSTEM] Sinyal berhenti diterima. Mematikan Manager...", flush=True)
        if manager_process is not None and manager_process.poll() is None:
            try:
                manager_process.terminate()
                manager_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                print("⚠️ [IBEKS SYSTEM] Manager belum berhenti, mengirim SIGKILL...", flush=True)
                manager_process.kill()
                manager_process.wait()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stopping:
        print(f"🤖 [MANAGER] Menjalankan: {manager_main}", flush=True)
        manager_process = subprocess.Popen(
            [sys.executable, "-u", manager_main],
            cwd=base_dir,
        )

        ret_code = manager_process.wait()
        if stopping:
            break

        print(
            f"⚠️ [IBEKS SYSTEM] Proses Manager berhenti dengan kode {ret_code}. "
            "Merestart otomatis dalam 2 detik...",
            flush=True,
        )
        time.sleep(2)


if __name__ == "__main__":
    run_bots()
