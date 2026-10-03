import os
from pathlib import Path

CONTACT = os.environ.get("CIVIC_CONTACT", "allanmacdonald.design@gmail.com")
USER_AGENT = f"civic-leverage-tool/0.1 ({CONTACT})"
DB_PATH = Path(os.environ.get("CIVIC_DB", Path.home() / ".civic" / "cache.db"))
TOPICS_PATH = Path(__file__).with_name("topics.json")
CLASSIFIER_MODEL = os.environ.get("CIVIC_CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")
LETTER_MODEL = os.environ.get("CIVIC_LETTER_MODEL", "claude-sonnet-5-5")
SITE_URL = os.environ.get("SITE_URL", "https://mp.allan-macdonald.com").rstrip("/")
