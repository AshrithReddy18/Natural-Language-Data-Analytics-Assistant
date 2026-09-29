from sqlalchemy.engine import URL, make_url


def normalize_db_url(url: str | URL) -> URL:
    """Use the psycopg (v3) driver for plain postgresql:// URLs; SQLAlchemy defaults to psycopg2,
    which is not a dependency."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed
