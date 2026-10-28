from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.auth.routes import auth_bp
    from app.candidate.routes import candidate_bp
    from app.newhire.routes import newhire_bp
    from app.manager.routes import manager_bp
    from app.admin.routes import admin_bp
    from app.employee.routes import employee_bp
    from app.files.routes import files_bp
    from app.directory.routes import directory_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(candidate_bp, url_prefix='/candidate')
    app.register_blueprint(newhire_bp, url_prefix='/newhire')
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(manager_bp, url_prefix='/manager')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(files_bp)
    app.register_blueprint(directory_bp, url_prefix='/directory')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # The ingestion API (app/api/routes.py) is authenticated via a static
    # X-API-Token header, not a session cookie, so it's exempt from
    # Flask-WTF's CSRF protection (which otherwise applies to every POST).
    csrf.exempt(api_bp)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'Brilliance Engine',
            'company_name': 'Pure Technology',
        }

    return app
