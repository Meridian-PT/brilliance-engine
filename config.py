import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _fix_database_url(url):
    """Fix Render's postgres:// prefix to postgresql:// for SQLAlchemy 2.x."""
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'brilliance-engine-dev-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = _fix_database_url(os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "brilliance.db")}'
    ))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
