from pathlib import Path

# Пути
BASE_DIR     = Path.home() / "consultant-data"
SESSION_PATH = BASE_DIR / "session.json"
ENV_PATH     = Path.home() / ".config" / "consultant" / ".env"

# Категории документов
CATEGORIES = {
    "kodeksy":       BASE_DIR / "kodeksy" / "converted-md",
    "hotdocs":       BASE_DIR / "converted-md",
    "federal_laws":  BASE_DIR / "federal-laws" / "converted-md",
    "gov_decrees":   BASE_DIR / "gov-decrees" / "converted-md",
    "court":         BASE_DIR / "court" / "converted-md",
}

# HTTP заголовки
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}
