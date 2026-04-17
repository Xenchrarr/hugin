from . import session, TELEGRAM_BOT_URL


def check_telegram_bot_health():
    url = f"{TELEGRAM_BOT_URL}/api/telegram/health"
    response = session.get(url, timeout=5)
    if response.status_code == 200:
        return True
    else:
        return False
