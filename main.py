
import asyncio
import html
import json
import logging
import os

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    AI_BOT_USERNAME,
    ADMIN_CONTACT,
)

from spreadsheet import save_registration


# =========================================================
# CONFIG
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Jakarta")

DATA_FILE = Path("registrations.json")
TEMP_DATA_FILE = Path("registrations.tmp")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

registrations = {}


# =========================================================
# VALIDASI CONFIG
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN belum diatur di Railway Variables.")

if not ADMIN_IDS:
    raise RuntimeError(
        "ADMIN_ID belum diatur. Isi dengan Telegram User ID admin."
    )


# =========================================================
# WAKTU WIB
# =========================================================

def current_time():
    return datetime.now(TIMEZONE).strftime("%d-%m-%Y %H:%M:%S")


# =========================================================
# SIMPAN DAN MUAT DATA REGISTRASI
# =========================================================

def load_data():
    global registrations

    if not DATA_FILE.exists():
        registrations = {}
        return

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            loaded = json.load(file)

        registrations = loaded if isinstance(loaded, dict) else {}

    except (json.JSONDecodeError, OSError):
        logger.exception("Gagal membaca registrations.json")
        registrations = {}


def save_data():
    try:
        with TEMP_DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                registrations,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(TEMP_DATA_FILE, DATA_FILE)

    except OSError:
        logger.exception("Gagal menyimpan data registrasi.")
        raise


# =========================================================
# HELPER
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def get_registration(user_id):
    return registrations.get(str(user_id))


def review_keyboard(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ APPROVED",
                    callback_data=f"reg:approve:{user_id}",
                ),
                InlineKeyboardButton(
                    text="❌ TOLAK",
                    callback_data=f"reg:reject:{user_id}",
                ),
            ]
        ]
    )


def safe_html(value):
    return html.escape(str(value or "-"))


# =========================================================
# MIDDLEWARE: ABAIKAN SEMUA PESAN GRUP
# =========================================================

class IgnoreGroupMessagesMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        chat = getattr(event, "chat", None)

        if chat and chat.type in ("group", "supergroup"):
            return None

        return await handler(event, data)


dp.message.middleware(IgnoreGroupMessagesMiddleware())


# =========================================================
# /START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    user_key = str(user_id)

    existing = registrations.get(user_key)

    # User sudah disetujui
    if existing and existing.get("status") == "APPROVED":
        await message.answer(
            "✅ Registrasi kamu sudah disetujui.\n\n"
            f"Silakan buka bot AI Pribadi kamu: @{AI_BOT_USERNAME}\n\n"
            f"Ketik /start di @{AI_BOT_USERNAME} untuk memulai."
        )
        return

    # Registrasi sedang menunggu admin
    if existing and existing.get("status") == "WAITING_ADMIN":
        await message.answer(
            "⏳ Registrasi kamu sedang diperiksa oleh admin.\n\n"
            "Mohon tunggu persetujuan admin. "
            "Kamu akan menerima notifikasi melalui bot ini."
        )
        return

    # Registrasi baru atau mengulang registrasi yang ditolak
    registrations[user_key] = {
        "telegram_id": user_id,
        "username": message.from_user.username or "",
        "full_name": message.from_user.full_name or "",
        "status": "WAITING_WALLET",
        "created_at": current_time(),
    }

    save_data()

    await message.answer(
        "👋 SELAMAT DATANG DI REGISTRASI AI ASSISTANT\n\n"
        "Silakan isi data registrasi secara berurutan.\n\n"
        "🆔 Langkah 1 dari 4\n"
        "Masukkan ID Wallet kamu:"
    )


# =========================================================
# VALIDASI DAN INPUT TEKS
# =========================================================

@dp.message(F.text)
async def registration_text_handler(message: Message):
    if not message.from_user:
        return

    text = (message.text or "").strip()

    # Abaikan command selain /start
    if text.startswith("/"):
        return

    user_id = message.from_user.id
    data = get_registration(user_id)

    if not data:
        return

    status = data.get("status")

    # -----------------------------------------------------
    # LANGKAH 1: ID WALLET
    # -----------------------------------------------------

    if status == "WAITING_WALLET":
        if len(text) < 3 or len(text) > 150:
            await message.answer(
                "❌ ID Wallet tidak valid.\n\n"
                "Silakan masukkan ID Wallet yang benar:"
            )
            return

        data["wallet_id"] = text
        data["status"] = "WAITING_BROKER"
        save_data()

        await message.answer(
            "✅ ID Wallet berhasil dicatat.\n\n"
            "🏦 Langkah 2 dari 4\n"
            "Broker yang digunakan:"
        )
        return

    # -----------------------------------------------------
    # LANGKAH 2: BROKER
    # -----------------------------------------------------

    if status == "WAITING_BROKER":
        if len(text) < 2 or len(text) > 100:
            await message.answer(
                "❌ Nama broker tidak valid.\n\n"
                "Silakan masukkan nama broker yang kamu gunakan:"
            )
            return

        data["broker"] = text
        data["status"] = "WAITING_GMAIL"
        save_data()

        await message.answer(
            "✅ Broker berhasil dicatat.\n\n"
            "📧 Langkah 3 dari 4\n"
            "Masukkan Gmail Broker:"
        )
        return

    # -----------------------------------------------------
    # LANGKAH 3: GMAIL BROKER
    # -----------------------------------------------------

    if status == "WAITING_GMAIL":
        import re

        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.match(email_pattern, text):
            await message.answer(
                "❌ Format Gmail/email tidak valid.\n\n"
                "Silakan masukkan Gmail Broker yang benar:"
            )
            return

        data["gmail_broker"] = text
        data["status"] = "WAITING_PHOTO"
        save_data()

        await message.answer(
            "✅ Gmail Broker berhasil dicatat.\n\n"
            "📸 Langkah 4 dari 4\n"
            "Sekarang kirim foto profil akun MT5 terbaru "
            "yang memperlihatkan saldo akun kamu.\n\n"
            "PENTING:\n"
            "• Pastikan profil dan saldo terlihat jelas.\n"
            "• Kirim sebagai foto langsung di Telegram.\n"
            "• Jangan kirim sebagai dokumen/file."
        )
        return

    # -----------------------------------------------------
    # MENUNGGU FOTO
    # -----------------------------------------------------

    if status == "WAITING_PHOTO":
        await message.answer(
            "📸 Registrasi hampir selesai.\n\n"
            "Silakan kirim foto profil akun MT5 terbaru "
            "yang terlihat saldonya."
        )
        return

    if status == "WAITING_ADMIN":
        await message.answer(
            "⏳ Data kamu sudah dikirim ke admin.\n"
            "Mohon tunggu hasil pemeriksaan."
        )


# =========================================================
# TERIMA FOTO MT5
# =========================================================

@dp.message(F.photo)
async def registration_photo_handler(message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    data = get_registration(user_id)

    if not data:
        await message.answer(
            "Silakan ketik /start terlebih dahulu untuk registrasi."
        )
        return

    if data.get("status") != "WAITING_PHOTO":
        if data.get("status") == "WAITING_ADMIN":
            await message.answer(
                "⏳ Foto kamu sudah dikirim ke admin untuk diperiksa."
            )
        elif data.get("status") == "APPROVED":
            await message.answer(
                "✅ Registrasi kamu sudah disetujui."
            )
        else:
            await message.answer(
                "Silakan selesaikan pengisian data terlebih dahulu "
                "sesuai arahan bot."
            )
        return

    required_fields = ("wallet_id", "broker", "gmail_broker")

    if any(not data.get(field) for field in required_fields):
        await message.answer(
            "❌ Data registrasi belum lengkap.\n\n"
            "Silakan ketik /start untuk memulai kembali."
        )
        return

    photo_file_id = message.photo[-1].file_id

    data["photo_file_id"] = photo_file_id
    data["status"] = "WAITING_ADMIN"
    data["registered_at"] = current_time()
    data["submitted_at"] = current_time()

    save_data()

    username = (
        f"@{data['username']}"
        if data.get("username")
        else "(tidak ada username)"
    )

    caption = (
        "🆕 <b>REGISTRASI AI ASSISTANT BARU</b>\n\n"
        f"👤 Nama: {safe_html(data.get('full_name'))}\n"
        f"🔗 Username: {safe_html(username)}\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n\n"
        f"💳 ID Wallet: <code>{safe_html(data.get('wallet_id'))}</code>\n"
        f"🏦 Broker: {safe_html(data.get('broker'))}\n"
        f"📧 Gmail Broker: {safe_html(data.get('gmail_broker'))}\n"
        f"🕒 Waktu: {safe_html(data.get('registered_at'))}\n\n"
        "Periksa foto profil MT5 dan saldo sebelum memilih keputusan."
    )

    sent_count = 0

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=review_keyboard(user_id),
            )
            sent_count += 1

        except Exception:
            logger.exception(
                "Gagal mengirim registrasi ke admin ID %s",
                admin_id,
            )

    if sent_count == 0:
        data["status"] = "WAITING_PHOTO"
        data.pop("photo_file_id", None)
        save_data()

        await message.answer(
            "⚠️ Foto belum berhasil diteruskan ke admin.\n\n"
            "Silakan coba kirim ulang foto MT5 kamu beberapa saat lagi."
        )
        return

    await message.answer(
        "✅ REGISTRASI BERHASIL DIKIRIM\n\n"
        "Data dan foto profil MT5 kamu sudah diteruskan "
        "kepada admin untuk diperiksa.\n\n"
        "⏳ Status: Menunggu persetujuan admin.\n"
        "Kamu akan menerima notifikasi setelah keputusan dibuat."
    )


# =========================================================
# ADMIN APPROVE / REJECT
# =========================================================

@dp.callback_query(F.data.startswith("reg:"))
async def registration_review_handler(callback: CallbackQuery):
    if not callback.from_user:
        await callback.answer("Admin tidak valid.", show_alert=True)
        return

    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer(
            "Kamu tidak memiliki izin untuk memproses registrasi ini.",
            show_alert=True,
        )
        return

    try:
        _, action, user_id_text = callback.data.split(":", 2)
        user_id = int(user_id_text)
    except (ValueError, AttributeError):
        await callback.answer("Data tombol tidak valid.", show_alert=True)
        return

    data = get_registration(user_id)

    if not data:
        await callback.answer(
            "Data registrasi tidak ditemukan.",
            show_alert=True,
        )
        return

    if data.get("status") != "WAITING_ADMIN":
        await callback.answer(
            f"Registrasi sudah diproses atau statusnya "
            f"{data.get('status', 'TIDAK DIKETAHUI')}.",
            show_alert=True,
        )
        return

    # -----------------------------------------------------
    # APPROVED
    # -----------------------------------------------------

    if action == "approve":
        data["status"] = "APPROVING"
        save_data()

        await callback.answer("Sedang menyimpan registrasi...")

        # Simpan ke Google Sheets tanpa memblokir event loop.
        try:
            success = await asyncio.to_thread(
                save_registration,
                data,
                admin_id,
            )
        except Exception:
            logger.exception("Terjadi kesalahan saat menyimpan ke Sheet.")
            success = False

        if not success:
            data["status"] = "WAITING_ADMIN"
            save_data()

            try:
                await callback.message.answer(
                    "⚠️ Gagal menyimpan data ke Google Spreadsheet.\n"
                    "Silakan periksa konfigurasi Google Sheets lalu "
                    "tekan APPROVED kembali."
                )
            except Exception:
                logger.exception("Gagal mengirim pemberitahuan error ke admin.")

            return

        data["status"] = "APPROVED"
        data["approved_by"] = admin_id
        data["approved_at"] = current_time()
        save_data()

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 <b>REGISTRASI KAMU BERHASIL DISETUJUI!</b>\n\n"
                    "Data kamu sudah berhasil dicatat.\n\n"
                    "Silakan buka bot AI Pribadi kamu:\n"
                    f"👉 @{AI_BOT_USERNAME}\n\n"
                    f"Ketik /start di @{AI_BOT_USERNAME} "
                    "untuk memulai."
                ),
                parse_mode="HTML",
            )
            user_notified = True

        except Exception:
            user_notified = False
            logger.exception(
                "Registrasi disetujui, tetapi notifikasi user gagal."
            )

        try:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        confirmation = (
            "✅ REGISTRASI DISETUJUI\n\n"
            f"Telegram ID: {user_id}\n"
            f"Broker: {data.get('broker', '-')}\n"
            "Data berhasil disimpan ke Google Spreadsheet."
        )

        if not user_notified:
            confirmation += (
                "\n\n⚠️ Bot gagal mengirim DM ke user. "
                "Pastikan user sudah membuka bot registrasi "
                "dan menekan /start."
            )

        await callback.message.answer(confirmation)
        return

    # -----------------------------------------------------
    # REJECT
    # -----------------------------------------------------

    if action == "reject":
        data["status"] = "REJECTED"
        data["rejected_by"] = admin_id
        data["rejected_at"] = current_time()
        save_data()

        await callback.answer("Registrasi ditolak.")

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ <b>REGISTRASI KAMU BELUM BERHASIL</b>\n\n"
                    "Registrasi kamu belum berhasil.\n"
                    "Silakan hubungi admin kami:\n"
                    f"👉 {ADMIN_CONTACT}"
                ),
                parse_mode="HTML",
            )
            user_notified = True

        except Exception:
            user_notified = False
            logger.exception(
                "Gagal mengirim notifikasi penolakan kepada user."
            )

        try:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        confirmation = (
            "❌ REGISTRASI DITOLAK\n\n"
            f"Telegram ID: {user_id}\n"
            f"Broker: {data.get('broker', '-')}\n"
            "Status sudah diperbarui."
        )

        if not user_notified:
            confirmation += (
                "\n\n⚠️ Bot tidak dapat mengirim DM kepada user."
            )

        await callback.message.answer(confirmation)
        return

    await callback.answer("Aksi tidak dikenali.", show_alert=True)


# =========================================================
# START BOT
# =========================================================

async def main():
    load_data()

    logger.info("Bot registrasi sedang dijalankan.")
    logger.info("Jumlah admin: %s", len(ADMIN_IDS))

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
