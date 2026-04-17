from . import session, SMS_BOT_URL


def check_sms_bot_health():
    url = f"{SMS_BOT_URL}/api/sms/health"
    response = session.get(url, timeout=5)
    if response.status_code == 200:
        return True
    else:
        return False
