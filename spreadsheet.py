
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
    Membuka Google Spreadsheet menggunakan environment
    variable GOOGLE_SERVICE_ACCOUNT.
    """

    service_account_json = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT", ""
    ).strip()

    if not service_account_json:
        raise RuntimeError(
            "Environment variable GOOGLE_SERVICE_ACCOUNT "
            "belum diatur di Railway."
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
# HEADER GOOGLE SHEETS
# =========================================================

EXPECTED_HEADERS = [
    "telegram_id",  # A
    "username",     # B
    "nama",         # C
    "broker",       # D
    "harga",        # E
    "register",     # F
    "expired",      # G
    "status",       # H
    "referral",     # I
    "id_wallet",    # J
    "gmail_broker", # K
]


def ensure_registration_headers(sheet):
    """
    Memeriksa header A-K.

    PERHATIAN:
    Fungsi ini hanya memperbarui baris 1.
    Data member mulai baris 2 tidak dihapus atau diubah.
    """

    current_headers = sheet.row_values(1)

    normalized_headers = [
        str(value).strip()
        for value in current_headers[:len(EXPECTED_HEADERS)]
    ]

    if normalized_headers == EXPECTED_HEADERS:
        logger.info(
            "[SHEET] Header A-K sudah sesuai."
        )
        return True

    logger.warning(
        "[SHEET] Header A-K tidak sesuai. "
        "Memperbarui header sesuai struktur registrasi."
    )

    sheet.update(
        range_name="A1:K1",
        values=[EXPECTED_HEADERS],
        value_input_option="RAW",
    )

    logger.info(
        "[SHEET] Header A-K berhasil diperbarui."
    )

    return True


# =========================================================
# HITUNG TANGGAL REGISTRASI DAN KEDALUWARSA
# =========================================================

def calculate_registration_dates(data):
    """
    F = register: DD-MM-YYYY HH:MM:SS
    G = expired: DD-MM-YYYY, tiga tahun setelah registrasi.

    Menggunakan registered_at atau register dari data
    jika tersedia.
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
    Menentukan baris berikutnya berdasarkan kolom A.
    Baris 1 adalah header.
    Data baru dimulai minimal dari baris 2.
    """

    column_a = sheet.col_values(1)

    return max(2, len(column_a) + 1)


# =========================================================
# SIMPAN REGISTRASI MEMBER BARU
# =========================================================

def save_registration(data, admin_id=None):
    """
    Menyimpan member setelah admin menyetujui registrasi.

    A = telegram_id
    B = username
    C = nama
    D = broker
    E = harga
    F = register
    G = expired
    H = status
    I = referral
    J = id_wallet
    K = gmail_broker

    Satu member = satu baris.
    """

    try:
        sheet = connect_sheet()

        # Memastikan header tersedia sebelum menyimpan.
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
            telegram_id,
            username,
            nama,
            broker,
            "",
            register_time,
            expired_time,
            "ACTIVE",
            "",
            wallet_id,
            gmail_broker,
        ]

        next_row = find_next_registration_row(sheet)

        sheet.update(
            range_name=f"A{next_row}:K{next_row}",
            values=[row],
            value_input_option="RAW",
        )

        logger.info(
            "[SHEET] Registrasi berhasil disimpan. "
            "Baris=%s TelegramID=%s Status=ACTIVE",
            next_row,
            telegram_id,
        )

        return True

    except Exception:
        logger.exception(
            "[SHEET] Gagal menyimpan registrasi."
        )
        return False


# =========================================================
# SIMPAN MEMBER LAMA - KOMPATIBILITAS
# =========================================================

def save_member(data):
    """
    Fungsi kompatibilitas untuk format member lama A-I.

    A = telegram_id
    B = username
    C = nama
    D = paket
    E = harga
    F = register
    G = expired
    H = status
    I = referral

    Fungsi ini tidak mengubah header.
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
            "[SHEET] Member lama disimpan pada baris %s.",
            next_row,
        )

        return True

    except Exception:
        logger.exception(
            "[SHEET] Gagal menyimpan member lama."
        )
        return False


# =========================================================
# PARSE TANGGAL KEDALUWARSA
# =========================================================

def parse_expired_date(value):
    """
    Mengubah teks tanggal kedaluwarsa menjadi datetime WIB.
    Mengembalikan None jika format tidak dikenali.
    """

    if not value:
        return None

    value = str(value).strip()

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
            parsed = datetime.strptime(
                value,
                date_format,
            )
            return parsed.replace(tzinfo=TIMEZONE)
        except ValueError:
            continue

    return None


# =========================================================
# AMBIL MEMBER YANG SUDAH KEDALUWARSA
# =========================================================

def get_expired_group_members():
    """
    Mengambil member ACTIVE yang masa berlakunya habis.
    Tidak mengeluarkan member dari grup secara langsung.
    """

    expired_members = []

    try:
        sheet = connect_sheet()

        # get_all_records memerlukan header unik dan tidak kosong.
        ensure_registration_headers(sheet)

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

            expired_datetime = parse_expired_date(
                expired_text
            )

            if expired_datetime is None:
                if expired_text:
                    logger.warning(
                        "[EXPIRED] Format tanggal tidak dikenali: %s",
                        expired_text,
                    )
                continue

            # Tanggal tanpa jam dianggap berlaku sampai
            # akhir hari tersebut.
            if len(expired_text) == 10:
                expired_datetime = expired_datetime.replace(
                    hour=23,
                    minute=59,
                    second=59,
                )

            if now > expired_datetime:
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
# UPDATE STATUS MEMBER
# =========================================================

def update_member_status(telegram_id, new_status):
    """
    Mengubah status pada kolom H berdasarkan Telegram ID
    di kolom A.
    """

    try:
        sheet = connect_sheet()

        ensure_registration_headers(sheet)

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
                    "[SHEET] Telegram ID %s diubah menjadi %s "
                    "pada baris %s.",
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
