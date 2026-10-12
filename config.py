
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(value.strip())
    for value in os.getenv("ADMIN_ID", "").split(",")
    if value.strip()
]

AI_BOT_USERNAME = "AIGOLDASSISTANT_BOT"
ADMIN_CONTACT = "@AdmAIassistantGold"
