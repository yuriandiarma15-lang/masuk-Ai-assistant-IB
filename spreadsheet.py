import os
import json

import gspread

from datetime import datetime

from google.oauth2.service_account import Credentials


# ==========================================
# GOOGLE SHEET CONFIG
# ==========================================

SPREADSHEET_ID = "1J3_Go0MdiNaDxVl6EuA00hJMsamB35Gjq0eHEg96ZMw"

SHEET_NAME = "Members"


SCOPES = [

    "https://www.googleapis.com/auth/spreadsheets",

    "https://www.googleapis.com/auth/drive"

]


# ==========================================
# GOOGLE SERVICE ACCOUNT
# ==========================================

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT"]
)


creds = Credentials.from_service_account_info(

    service_account_info,

    scopes=SCOPES

)


client = gspread.authorize(
    creds
)


spreadsheet = client.open_by_key(
    SPREADSHEET_ID
)


sheet = spreadsheet.worksheet(
    SHEET_NAME
)


# ==========================================
# SAVE MEMBER
# ==========================================

def save_member(data):

    try:

        print(
            "=== DATA KE GOOGLE SHEET ==="
        )

        print(data)

        sheet.append_row([

            data.get(
                "telegram_id",
                ""
            ),

            data.get(
                "username",
                ""
            ),

            data.get(
                "nama",
                ""
            ),

            data.get(
                "paket",
                ""
            ),

            data.get(
                "harga",
                ""
            ),

            data.get(
                "register",
                ""
            ),

            data.get(
                "expired",
                ""
            ),

            data.get(
                "status",
                ""
            ),

            data.get(
                "referral",
                ""
            )

        ])

        print(
            "STATUS:"
        )

        print(
            "SUCCESS"
        )

        print(
            "RESPON GOOGLE SHEET:"
        )

        print(
            "Member berhasil disimpan"
        )

        return True

    except Exception as e:

        print(
            "Google Sheet Error:"
        )

        print(e)

        return False


# ==========================================
# GET EXPIRED GROUP MEMBERS
# ==========================================

def get_expired_group_members():

    expired_members = []

    try:

        rows = sheet.get_all_records()

        now = datetime.now()

        for row in rows:

            package = str(
                row.get(
                    "paket",
                    ""
                )
            ).strip().lower()

            status = str(
                row.get(
                    "status",
                    ""
                )
            ).strip().upper()

            # ==================================
            # ONLY GROUP PACKAGES
            # ==================================

            if package not in (
                "2 bulan",
                "3 bulan"
            ):
                continue

            # ==================================
            # ALREADY EXPIRED
            # ==================================

            if status == "EXPIRED":
                continue

            expired_text = str(
                row.get(
                    "expired",
                    ""
                )
            ).strip()

            if not expired_text:
                continue

            expired_at = None

            # ==================================
            # NEW DATETIME FORMAT
            # ==================================

            try:

                expired_at = datetime.strptime(
                    expired_text,
                    "%d-%m-%Y %H:%M:%S"
                )

            except ValueError:

                # ==================================
                # OLD DATE FORMAT
                # ==================================

                try:

                    expired_at = datetime.strptime(
                        expired_text,
                        "%d-%m-%Y"
                    )

                except ValueError:

                    print(
                        f"[EXPIRED] "
                        f"Format tidak dikenali: "
                        f"{expired_text}"
                    )

                    continue

            # ==================================
            # CHECK EXPIRY
            # ==================================

            if now >= expired_at:

                expired_members.append({

                    "telegram_id": row.get(
                        "telegram_id",
                        ""
                    ),

                    "username": row.get(
                        "username",
                        ""
                    ),

                    "nama": row.get(
                        "nama",
                        ""
                    ),

                    "paket": row.get(
                        "paket",
                        ""
                    ),

                    "expired": expired_text,

                    "referral": row.get(
                        "referral",
                        ""
                    ),

                    "status": status

                })

        print(
            f"[EXPIRED CHECK] "
            f"Ditemukan "
            f"{len(expired_members)} "
            f"member expired."
        )

        return expired_members

    except Exception as e:

        print(
            "Get expired members error:"
        )

        print(e)

        return []


# ==========================================
# UPDATE MEMBER STATUS
# ==========================================

def update_member_status(
    telegram_id,
    new_status
):

    try:

        rows = sheet.get_all_records()

        for index, row in enumerate(
            rows,
            start=2
        ):

            row_telegram_id = str(
                row.get(
                    "telegram_id",
                    ""
                )
            ).strip()

            if row_telegram_id == str(
                telegram_id
            ).strip():

                # STATUS = KOLOM H
                sheet.update_cell(
                    index,
                    8,
                    new_status
                )

                print(
                    f"[SHEET] "
                    f"{telegram_id} "
                    f"-> {new_status}"
                )

                return True

        print(
            f"[SHEET] "
            f"Telegram ID "
            f"{telegram_id} "
            f"tidak ditemukan."
        )

        return False

    except Exception as e:

        print(
            "Update member status error:"
        )

        print(e)

        return False
