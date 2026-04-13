import logging

import src  # noqa: F401 — loads dotenv before anything else
from src.services.bot import main

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    main()
