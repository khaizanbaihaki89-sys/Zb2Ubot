"""
IBEKS USERBOT - String Session Generator

Generate STRING_SESSION langsung di environment Replit.
Jalankan: cd userbot && python generate_session.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyrogram import Client

from config import API_ID, API_HASH
from utils.logger import log


def main():
    if not API_ID or not API_HASH:
        log.critical("API_ID dan API_HASH harus di-set di Replit Secrets terlebih dahulu.")
        sys.exit(1)

    log.info("[GenerateSession] Membuat session baru...")
    log.info("[GenerateSession] Ikuti instruksi di bawah:")

    # Nama session file sementara (akan dihapus setelah selesai)
    temp_name = "temp_session_gen"

    client = Client(
        name=temp_name,
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=False,  # Simpan sementara ke disk agar login interaktif berjalan
    )

    try:
        client.start()
        session_string = client.export_session_string()

        print("\n" + "=" * 60)
        print("STRING_SESSION BERHASIL DIBUAT")
        print("=" * 60)
        print(session_string)
        print("=" * 60)
        print("\nSalin string di atas dan simpan ke Replit Secrets dengan key STRING_SESSION.")
        print("Kemudian restart workflow IBEKS USERBOT.")
    except Exception as exc:
        log.exception(f"[GenerateSession] Gagal: {exc}")
        sys.exit(1)
    finally:
        client.stop()
        # Hapus file session sementara
        for ext in [".session", ".session-journal"]:
            temp_file = temp_name + ext
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
