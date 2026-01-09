"""
Staff Scheduling System - Main Application Factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.management import bp as management_bp
    app.register_blueprint(management_bp, url_prefix='/management')
    
    from app.tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    
    from app.board import bp as board_bp
    app.register_blueprint(board_bp, url_prefix='/board')
    
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Create tables and initialize default data
    with app.app_context():
        db.create_all()
        from app.models import init_default_data
        init_default_data()
    
    # Error handlers
    from flask import render_template
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Context processors
    @app.context_processor
    def utility_processor():
        from datetime import date
        return {
            'today': date.today(),
            'current_year': date.today().year
        }
    
    # Template filters
    @app.template_filter('dateformat')
    def dateformat_filter(value, format='%d/%m/%Y'):
        if value is None:
            return ''
        return value.strftime(format)
    
    @app.template_filter('timeformat')
    def timeformat_filter(value, format='%H:%M'):
        if value is None:
            return ''
        return value.strftime(format)
    
    return app
