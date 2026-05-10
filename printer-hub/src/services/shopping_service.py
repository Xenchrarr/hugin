import requests

from src.config import HUGIN_CORE_URL
from src.services.print_service import PrintService


class ShoppingService:
    def __init__(self):
        self.print_service = PrintService()

    def fetch_and_print(self) -> dict:
        url = f"{HUGIN_CORE_URL}/api/shopping/list"
        response = requests.get(url, timeout=(5, 10))

        if response.status_code != 200:
            raise Exception(f"Failed to fetch shopping list: {response.status_code}")

        content = response.json().get("content", "")
        items = [line for line in content.splitlines() if line.strip()]

        if not items:
            raise Exception("Shopping list is empty")

        self.print_service.print_content(lines=items, title="Shopping List")

        return {"status": "printed", "items": len(items)}
