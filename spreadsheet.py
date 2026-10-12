
import os
import json
import logging

import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials


# =========================================================
# GOOGLE SHEET CONFIG
# =========================================================

SPREADSHEET_ID = "1J3_Go0MdiNaDxVl6EuA00hJMsamB35Gjq0eHEg96ZMw"
SHEET_NAME = "Members"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

logger = logging.getLogger(__name__)


# =========================================================
# GOOGLE SERVICE ACCOUNT
# =========================================================

def connect_sheet():
    """
    Membuka koneksi Google Spreadsheet.
    Menggunakan environment variable GOOGLE_SERVICE_ACCOUNT.
    """

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT", "").strip()

    if not service_account_json:
        raise RuntimeError(
            "Environment variable GOOGLE_SERVICE_ACCOUNT belum diatur."
        )

    service_account_info = json.loads(service_account_json)

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    client = gspread.authorize(credentials)

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    worksheet = spreadsheet.worksheet(SHEET_NAME)

    return worksheet


# =========================================================
# HEADER TAMBAHAN UNTUK REGISTRASI
# =========================================================

def ensure_registration_headers(sheet):
    """
    Memastikan kolom J dan K memiliki header.
    Kolom A-I yang sudah ada tidak diubah.
    """

    current_headers = sheet.row_values(1)

    if len(current_headers) < 10 or not current_headers[9].strip():
        sheet.update_acell("J1", "id_wallet")

    current_headers = sheet.row_values(1)

    if len(current_headers) < 11 or not current_headers[10].strip():
        sheet.update_acell("K1", "gmail_broker")


# =========================================================
# SAVE REGISTRATION BARU
# =========================================================

def save_registration(data, admin_id=None):
    """
    Menyimpan registrasi setelah admin menekan APPROVED.

    Kolom:
    A = telegram_id
    B = username
    C = nama
    D = broker yang digunakan (menggantikan paket)
    E = harga (kosong)
    F = register
    G = expired (kosong)
    H = status
    I = referral (kosong)
    J = id_wallet
    K = gmail_broker
    """

    try:
        sheet = connect_sheet()
        ensure_registration_headers(sheet)

        telegram_id = data.get("telegram_id", "")
        username = data.get("username", "")
        nama = data.get("full_name", data.get("nama", ""))
        broker = data.get("broker", "")
        wallet_id = data.get("wallet_id", "")
        gmail_broker = data.get("gmail_broker", "")

        register_time = (
            data.get("registered_at")
            or data.get("register")
            or datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        )

        row = [
            telegram_id,      # A: telegram_id
            username,         # B: username
            nama,             # C: nama
            broker,           # D: broker, bukan paket langganan
            "",               # E: harga
            register_time,    # F: register
            "",               # G: expired
            "APPROVED",       # H: status
            "",               # I: referral
            wallet_id,        # J: id_wallet
            gmail_broker,     # K: gmail_broker
        ]

        print("=== DATA REGISTRASI KE GOOGLE SHEET ===")
        print({
            "telegram_id": telegram_id,
            "username": username,
            "nama": nama,
            "broker": broker,
            "wallet_id": wallet_id,
            "gmail_broker": gmail_broker,
            "status": "APPROVED",
        })

        sheet.append_row(
            row,
            value_input_option="RAW",
        )

        print("[SHEET] Registrasi berhasil disimpan.")
        return True

    except Exception:
        logger.exception("[SHEET] Gagal menyimpan registrasi.")
        return False


# =========================================================
# SAVE MEMBER LAMA - KOMPATIBILITAS BOT SEBELUMNYA
# =========================================================

def save_member(data):
    """
    Fungsi lama dipertahankan.
    Tetap menyimpan sembilan kolom A-I sesuai format lama.
    """

    try:
        sheet = connect_sheet()

        row = [
            data.get("telegram_id", ""),
            data.get("username", ""),
            data.get("nama", ""),
            data.get("paket", ""),
            data.get("harga", ""),
            data.get("register", ""),
            data.get("expired", ""),
            data.get("status", ""),
            data.get("referral", ""),
        ]

        print("=== DATA MEMBER LAMA KE GOOGLE SHEET ===")
        print(data)

        sheet.append_row(
            row,
            value_input_option="RAW",
        )

        print("[SHEET] Member berhasil disimpan.")
        return True

    except Exception:
        logger.exception("[SHEET] Gagal menyimpan member lama.")
        return False


# =========================================================
# GET EXPIRED GROUP MEMBERS
# =========================================================

def get_expired_group_members():
    """
    Fungsi lama untuk memeriksa member grup yang kedaluwarsa.
    Hanya paket '2 bulan' dan '3 bulan' yang diperiksa,
    sesuai implementasi sebelumnya.
    """

    expired_members = []

    try:
        sheet = connect_sheet()
        rows = sheet.get_all_records()
        now = datetime.now()

        for row in rows:
            package = str(
                row.get("paket", "")
            ).strip().lower()

            status = str(
                row.get("status", "")
            ).strip().upper()

            if package not in ("2 bulan", "3 bulan"):
                continue

            if status == "EXPIRED":
                continue

            expired_text = str(
                row.get("expired", "")
            ).strip()

            if not expired_text:
                continue

            expired_at = None

            for date_format in (
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
            ):
                try:
                    expired_at = datetime.strptime(
                        expired_text,
                        date_format,
                    )
                    break
                except ValueError:
                    continue

            if expired_at is None:
                logger.warning(
                    "[EXPIRED] Format tanggal tidak dikenali: %s",
                    expired_text,
                )
                continue

            if now >= expired_at:
                expired_members.append({
                    "telegram_id": row.get("telegram_id", ""),
                    "username": row.get("username", ""),
                    "nama": row.get("nama", ""),
                    "paket": row.get("paket", ""),
                    "expired": expired_text,
                    "referral": row.get("referral", ""),
                    "status": status,
                })

        print(
            f"[EXPIRED CHECK] Ditemukan "
            f"{len(expired_members)} member expired."
        )

        return expired_members

    except Exception:
        logger.exception("[SHEET] Gagal memeriksa member expired.")
        return []


# =========================================================
# UPDATE MEMBER STATUS
# =========================================================

def update_member_status(telegram_id, new_status):
    """
    Mengubah status pada kolom H.
    Mencari member berdasarkan telegram_id di kolom A.
    """

    try:
        sheet = connect_sheet()
        rows = sheet.get_all_records()

        for index, row in enumerate(rows, start=2):
            row_telegram_id = str(
                row.get("telegram_id", "")
            ).strip()

            if row_telegram_id == str(telegram_id).strip():
                sheet.update_cell(
                    index,
                    8,
                    new_status,
                )

                print(
                    f"[SHEET] {telegram_id} -> {new_status}"
                )

                return True

        print(
            f"[SHEET] Telegram ID {telegram_id} tidak ditemukan."
        )

        return False

    except Exception:
        logger.exception("[SHEET] Gagal memperbarui status member.")
        return False
