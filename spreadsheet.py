
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
    Kolom A-I tidak diubah.
    """

    current_headers = sheet.row_values(1)

    if len(current_headers) < 10 or not current_headers[9].strip():
        sheet.update_acell("J1", "id_wallet")

    current_headers = sheet.row_values(1)

    if len(current_headers) < 11 or not current_headers[10].strip():
        sheet.update_acell("K1", "gmail_broker")


# =========================================================
# HITUNG TANGGAL REGISTRASI DAN KEDALUWARSA
# =========================================================

def calculate_registration_dates(data):
    """
    F = tanggal registrasi, format DD-MM-YYYY HH:MM:SS
    G = tanggal kedaluwarsa, 3 tahun setelah registrasi,
        format DD-MM-YYYY

    Menggunakan tanggal registered_at dari main.py apabila ada.
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

        for date_format in (
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
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

    # Pastikan waktu mengikuti zona WIB.
    if register_datetime.tzinfo is None:
        register_datetime = register_datetime.replace(
            tzinfo=TIMEZONE
        )
    else:
        register_datetime = register_datetime.astimezone(
            TIMEZONE
        )

    # Tanggal registrasi di kolom F.
    register_text = register_datetime.strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    # Masa berlaku 3 tahun dari tanggal registrasi.
    expired_datetime = (
        register_datetime + relativedelta(years=3)
    )

    # Tanggal kedaluwarsa di kolom G.
    expired_text = expired_datetime.strftime(
        "%d-%m-%Y"
    )

    return register_text, expired_text


# =========================================================
# SAVE REGISTRATION BARU
# =========================================================

def save_registration(data, admin_id=None):
    """
    Menyimpan registrasi setelah admin menekan APPROVED.

    Struktur Google Sheets:
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

        register_time, expired_time = (
            calculate_registration_dates(data)
        )

        # Kolom F, G, H sesuai format yang diminta.
        status = "ACTIVE"

        row = [
            telegram_id,       # A: telegram_id
            username,          # B: username
            nama,              # C: nama
            broker,            # D: broker
            "",                # E: harga
            register_time,     # F: register
            expired_time,      # G: expired, +3 tahun
            status,            # H: ACTIVE
            "",                # I: referral
            wallet_id,         # J: id_wallet
            gmail_broker,      # K: gmail_broker
        ]

        logger.info(
            "Menyimpan registrasi ke Google Sheets: %s",
            {
                "telegram_id": telegram_id,
                "register": register_time,
                "expired": expired_time,
                "status": status,
            },
        )

        sheet.append_row(
            row,
            value_input_option="RAW",
        )

        logger.info(
            "[SHEET] Registrasi berhasil disimpan: %s",
            telegram_id,
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
    Fungsi lama tetap tersedia.

    Data member lama disimpan sesuai format A-I.
    Status mengikuti data yang diberikan pemanggil.
    """

    try:
        sheet = connect_sheet()

        row = [
            data.get("telegram_id", ""),  # A
            data.get("username", ""),     # B
            data.get("nama", ""),         # C
            data.get("paket", ""),        # D
            data.get("harga", ""),        # E
            data.get("register", ""),     # F
            data.get("expired", ""),      # G
            data.get("status", ""),       # H
            data.get("referral", ""),     # I
        ]

        sheet.append_row(
            row,
            value_input_option="RAW",
        )

        logger.info(
            "[SHEET] Member lama berhasil disimpan."
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
    Memeriksa member lama yang kedaluwarsa.

    Kompatibel dengan struktur lama yang memiliki kolom paket.
    Untuk registrasi baru, status ACTIVE dan tanggal expired
    tetap dapat diperiksa tanpa memerlukan kolom paket.
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

            for date_format in (
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
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
    Mengubah status kolom H.
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

                logger.info(
                    "[SHEET] Telegram ID %s -> %s",
                    telegram_id,
                    new_status,
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
