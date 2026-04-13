import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://energy:energy@localhost:5432/energy",
)

ECOFLOW_ACCESS_KEY = os.environ["ECOFLOW_ACCESS_KEY"]
ECOFLOW_SECRET_KEY = os.environ["ECOFLOW_SECRET_KEY"]
ECOFLOW_BASE_URL = os.environ.get("ECOFLOW_BASE_URL", "https://api-e.ecoflow.com")

TIMEZONE = os.environ.get("TIMEZONE", "Europe/Oslo")

# How often the daily aggregator runs (minutes)
AGGREGATOR_INTERVAL_MINUTES = int(os.environ.get("AGGREGATOR_INTERVAL_MINUTES", "15"))
