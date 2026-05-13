from src.api.hugin_core import CORE_API_URL, session


def get_shopping_list() -> list[str]:
    response = session.get(f"{CORE_API_URL}/api/shopping/list", timeout=10)
    response.raise_for_status()
    content = response.json().get("content", "")
    return [line for line in content.splitlines() if line.strip()]
