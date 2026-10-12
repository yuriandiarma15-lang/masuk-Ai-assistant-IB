
import os
import json
import logging

import gspread

from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials


# =========================================================
# GOOGLE SHEET CONFIG
# =========================================================

SPREADSHEET_ID = "1J3_Go0MdiNaDxVl6EuA00hJMsamB35Gjq0eHEg96ZMw"
SHEET_NAME = "Members"

TIMEZONE = ZoneInfo("Asia/Jakarta")

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
    Membuka koneksi Google Spreadsheet menggunakan
    environment variable GOOGLE_SERVICE_ACCOUNT.
    """

    service_account_json = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT", ""
    ).strip()

    if not service_account_json:
        raise RuntimeError(
            "Environment variable GOOGLE_SERVICE_ACCOUNT "
            "belum diatur."
        )

    service_account_info = json.loads(service_account_json)

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    return spreadsheet.worksheet(SHEET_NAME)


# =========================================================
# HEADER REGISTRASI
# =========================================================

def ensure_registration_headers(sheet):
    """
    Memastikan header J dan K tersedia.
    Kolom A-I yang sudah ada tidak diubah.
    """

    current_headers = sheet.row_values(1)

    if len(current_headers) < 10 or not str(
        current_headers[9]
    ).strip():
        sheet.update_acell("J1", "id_wallet")

    current_headers = sheet.row_values(1)

    if len(current_headers) < 11 or not str(
        current_headers[10]
    ).strip():
        sheet.update_acell("K1", "gmail_broker")


# =========================================================
# HITUNG TANGGAL REGISTRASI DAN KEDALUWARSA
# =========================================================

def calculate_registration_dates(data):
    """
    F = register: DD-MM-YYYY HH:MM:SS
    G = expired:  DD-MM-YYYY, tiga tahun setelah registrasi.

    Menggunakan registered_at dari main.py apabila tersedia.
    """

    register_value = (
        data.get("registered_at")
        or data.get("register")
    )

    register_datetime = None

    if isinstance(register_value, datetime):
        register_datetime = register_value

    elif register_value:
        register_value = str(register_value).strip()

        date_formats = (
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        )

        for date_format in date_formats:
            try:
                register_datetime = datetime.strptime(
                    register_value,
                    date_format,
                )
                break
            except ValueError:
                continue

    if register_datetime is None:
        register_datetime = datetime.now(TIMEZONE)

    # Pastikan waktu mengikuti WIB.
    if register_datetime.tzinfo is None:
        register_datetime = register_datetime.replace(
            tzinfo=TIMEZONE
        )
    else:
        register_datetime = register_datetime.astimezone(
            TIMEZONE
        )

    register_text = register_datetime.strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    expired_datetime = (
        register_datetime + relativedelta(years=3)
    )

    expired_text = expired_datetime.strftime(
        "%d-%m-%Y"
    )

    return register_text, expired_text


# =========================================================
# CARI BARIS KOSONG BERIKUTNYA
# =========================================================

def find_next_registration_row(sheet):
    """
    Mencari baris kosong berikutnya berdasarkan kolom A.

    Data registrasi baru ditulis pada satu baris penuh,
    dari kolom A sampai K.
    """

    column_a = sheet.col_values(1)

    # Baris 1 adalah header.
    # Minimal data baru dimulai pada baris 2.
    return max(2, len(column_a) + 1)


# =========================================================
# SAVE REGISTRATION BARU
# =========================================================

def save_registration(data, admin_id=None):
    """
    Menyimpan registrasi setelah admin menyetujui.

    Struktur kolom:
    A = telegram_id
    B = username
    C = nama
    D = broker
    E = harga (kosong)
    F = register
    G = expired (3 tahun)
    H = status ACTIVE
    I = referral (kosong)
    J = id_wallet
    K = gmail_broker

    Satu registrasi ditulis ke satu baris.
    Registrasi berikutnya ditulis ke baris di bawahnya.
    """

    try:
        sheet = connect_sheet()
        ensure_registration_headers(sheet)

        telegram_id = data.get("telegram_id", "")
        username = data.get("username", "")
        nama = data.get(
            "full_name",
            data.get("nama", ""),
        )
        broker = data.get("broker", "")
        wallet_id = data.get("wallet_id", "")
        gmail_broker = data.get("gmail_broker", "")

        register_time, expired_time = (
            calculate_registration_dates(data)
        )

        row = [
            telegram_id,       # A
            username,          # B
            nama,              # C
            broker,            # D
            "",                # E
            register_time,     # F
            expired_time,      # G
            "ACTIVE",          # H
            "",                # I
            wallet_id,         # J
            gmail_broker,      # K
        ]

        next_row = find_next_registration_row(sheet)

        # Tulis secara eksplisit ke satu baris A:K.
        sheet.update(
            range_name=f"A{next_row}:K{next_row}",
            values=[row],
            value_input_option="RAW",
        )

        logger.info(
            "[SHEET] Registrasi tersimpan pada baris %s. "
            "Telegram ID: %s | Register: %s | "
            "Expired: %s | Status: ACTIVE",
            next_row,
            telegram_id,
            register_time,
            expired_time,
        )

        return True

    except Exception:
        logger.exception(
            "[SHEET] Gagal menyimpan registrasi."
        )
        return False


# =========================================================
# SAVE MEMBER LAMA - KOMPATIBILITAS
# =========================================================

def save_member(data):
    """
    Fungsi lama dipertahankan untuk bot sebelumnya.

    Struktur A-I:
    telegram_id, username, nama, paket, harga,
    register, expired, status, referral.
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

        next_row = find_next_registration_row(sheet)

        sheet.update(
            range_name=f"A{next_row}:I{next_row}",
            values=[row],
            value_input_option="RAW",
        )

        logger.info(
            "[SHEET] Member lama berhasil disimpan pada baris %s.",
            next_row,
        )

        return True

    except Exception:
        logger.exception(
            "[SHEET] Gagal menyimpan member lama."
        )
        return False


# =========================================================
# GET EXPIRED MEMBERS
# =========================================================

def get_expired_group_members():
    """
    Memeriksa member ACTIVE yang masa berlakunya sudah habis.

    Kompatibel dengan format tanggal:
    DD-MM-YYYY
    DD-MM-YYYY HH:MM:SS
    YYYY-MM-DD
    YYYY-MM-DD HH:MM:SS

    Catatan:
    Fungsi ini mengembalikan data kedaluwarsa.
    Pengeluaran dari grup harus ditangani oleh pemanggilnya.
    """

    expired_members = []

    try:
        sheet = connect_sheet()
        rows = sheet.get_all_records()
        now = datetime.now(TIMEZONE)

        for row in rows:
            status = str(
                row.get("status", "")
            ).strip().upper()

            if status != "ACTIVE":
                continue

            expired_text = str(
                row.get("expired", "")
            ).strip()

            if not expired_text:
                continue

            expired_datetime = None

            date_formats = (
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y %H:%M",
                "%d-%m-%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
            )

            for date_format in date_formats:
                try:
                    expired_datetime = datetime.strptime(
                        expired_text,
                        date_format,
                    ).replace(tzinfo=TIMEZONE)
                    break
                except ValueError:
                    continue

            if expired_datetime is None:
                logger.warning(
                    "[EXPIRED] Format tanggal tidak dikenali: %s",
                    expired_text,
                )
                continue

            # Jika hanya tanggal yang disimpan, masa berlaku
            # berakhir pada akhir tanggal tersebut.
            if (
                len(expired_text) == 10
                and expired_datetime.date() == now.date()
            ):
                continue

            if now >= expired_datetime:
                expired_members.append({
                    "telegram_id": row.get("telegram_id", ""),
                    "username": row.get("username", ""),
                    "nama": row.get("nama", ""),
                    "paket": row.get("paket", ""),
                    "expired": expired_text,
                    "referral": row.get("referral", ""),
                    "status": status,
                })

        logger.info(
            "[EXPIRED CHECK] Ditemukan %s member kedaluwarsa.",
            len(expired_members),
        )

        return expired_members

    except Exception:
        logger.exception(
            "[SHEET] Gagal memeriksa member kedaluwarsa."
        )
        return []


# =========================================================
# UPDATE MEMBER STATUS
# =========================================================

def update_member_status(telegram_id, new_status):
    """
    Mengubah status kolom H berdasarkan Telegram ID
    pada kolom A.
    """

    try:
        sheet = connect_sheet()
        rows = sheet.get_all_records()

        for index, row in enumerate(rows, start=2):
            row_telegram_id = str(
                row.get("telegram_id", "")
            ).strip()

            if row_telegram_id == str(
                telegram_id
            ).strip():
                sheet.update_cell(
                    index,
                    8,
                    new_status,
                )

                logger.info(
                    "[SHEET] Telegram ID %s -> %s "
                    "(baris %s)",
                    telegram_id,
                    new_status,
                    index,
                )

                return True

        logger.warning(
            "[SHEET] Telegram ID %s tidak ditemukan.",
            telegram_id,
        )

        return False

    except Exception:
        logger.exception(
            "[SHEET] Gagal memperbarui status member."
        )
        return False
