import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _fix_database_url(url):
    """Normalize any Render Postgres URL to the installed psycopg2 driver.

    Render hands out postgres:// (or postgresql://). Newer SQLAlchemy resolves a
    bare postgresql:// to the psycopg (v3) DBAPI, which isn't installed and crashes
    at engine creation with "No module named 'psycopg'". We pin psycopg2 explicitly
    so it uses psycopg2-binary from requirements.txt. SQLite URLs pass through.
    """
    if not url:
        return url
    for prefix in ('postgresql+psycopg://', 'postgresql+psycopg2://',
                   'postgresql://', 'postgres://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg2://' + url[len(prefix):]
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'brilliance-engine-dev-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = _fix_database_url(os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "brilliance.db")}'
    ))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    # Phase 4 — Time Tracking ingestion API. Static token checked via the
    # X-API-Token header on POST /api/v1/time-entries. Override in production
    # via the TIMETRACK_API_TOKEN environment variable.
    TIMETRACK_API_TOKEN = os.environ.get('TIMETRACK_API_TOKEN', 'brilliance-timetrack-dev-token')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
