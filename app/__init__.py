"""
Staff Scheduling System - Main Application Factory
"""
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
    
    # CSRF error handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        return render_template('errors/csrf_error.html'), 400
    
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
    csrf.exempt(api_bp)  # Exempt API routes - they use login_required
    
    from app.finance import bp as finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # Initialize default data
        from app.models import Permission, Role, LeaveType
        
        # Create permissions if they don't exist
        permissions_data = [
            # User Management
            ('users.view', 'View Users', 'users'),
            ('users.create', 'Create Users', 'users'),
            ('users.edit', 'Edit Users', 'users'),
            ('users.delete', 'Delete Users', 'users'),
            # Role Management
            ('roles.manage', 'Manage Roles', 'roles'),
            # Schedule Management
            ('schedule.view_all', 'View All Schedules', 'schedule'),
            ('schedule.create', 'Create Schedules', 'schedule'),
            ('schedule.edit', 'Edit Schedules', 'schedule'),
            ('schedule.delete', 'Delete Schedules', 'schedule'),
            # Leave Management
            ('leave.view_all', 'View All Leave Requests', 'leave'),
            ('leave.approve', 'Approve Leave Requests', 'leave'),
            ('leave.allocate', 'Manage Leave Allocations', 'leave'),
            # Task Management
            ('tasks.view_all', 'View All Tasks', 'tasks'),
            ('tasks.create', 'Create Tasks', 'tasks'),
            ('tasks.edit', 'Edit Tasks', 'tasks'),
            ('tasks.delete', 'Delete Tasks', 'tasks'),
            ('tasks.assign', 'Assign Tasks', 'tasks'),
            # Board Management
            ('board.create', 'Create Board Posts', 'board'),
            ('board.edit', 'Edit Board Posts', 'board'),
            ('board.delete', 'Delete Board Posts', 'board'),
            ('board.pin', 'Pin Board Posts', 'board'),
            # Management Settings
            ('management.restricted', 'Manage Restricted Days', 'management'),
            ('management.requirements', 'Manage Requirements', 'management'),
            ('management.settings', 'System Settings', 'management'),
            ('management.reports', 'View Reports', 'management'),
            # Finance
            ('finance.view', 'View Finance', 'finance'),
            ('finance.expenses.submit', 'Submit Expenses', 'finance'),
            ('finance.expenses.approve', 'Approve Expenses', 'finance'),
            ('finance.budgets', 'Manage Budgets', 'finance'),
            ('finance.reports', 'View Financial Reports', 'finance'),
            ('finance.reports.generate', 'Generate Reports', 'finance'),
            ('finance.invoices', 'Manage Invoices', 'finance'),
            ('finance.payroll.view', 'View Payroll', 'finance'),
            ('finance.payroll.manage', 'Manage Payroll', 'finance'),
            ('finance.links', 'Manage Financial Links', 'finance'),
            ('finance.admin', 'Finance Admin', 'finance'),
        ]
        
        for code, name, category in permissions_data:
            if not Permission.query.filter_by(code=code).first():
                perm = Permission(code=code, name=name, category=category)
                db.session.add(perm)
        
        # Create default roles
        if not Role.query.filter_by(name='Administrator').first():
            admin_role = Role(name='Administrator', description='Full system access', is_system=True)
            all_perms = Permission.query.all()
            admin_role.permissions = all_perms
            db.session.add(admin_role)
        
        if not Role.query.filter_by(name='User').first():
            user_role = Role(name='User', description='Standard user access', is_system=True)
            db.session.add(user_role)
        
        # Create default leave types
        leave_types_data = [
            ('Annual Leave', '#10B981', True, True),
            ('Sick Leave', '#EF4444', True, False),
            ('Personal Leave', '#8B5CF6', True, True),
            ('Unpaid Leave', '#6B7280', False, True),
            ('Bereavement', '#1F2937', True, False),
            ('Maternity/Paternity', '#EC4899', True, True),
        ]
        
        for name, color, is_paid, requires_approval in leave_types_data:
            if not LeaveType.query.filter_by(name=name).first():
                lt = LeaveType(
                    name=name, 
                    color=color, 
                    is_paid=is_paid, 
                    requires_approval=requires_approval
                )
                db.session.add(lt)
        
        db.session.commit()
    
    # Error handlers
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
        from datetime import date, datetime, timedelta
        from app.models import SiteSettings
        return {
            'today': date.today(),
            'now': datetime.now(),
            'timedelta': timedelta,
            'current_year': date.today().year,
            'site_name': SiteSettings.get('site_name', 'Mystic Shores'),
            'site_subtitle': SiteSettings.get('site_subtitle', 'Roleplay'),
            'module_finance': SiteSettings.get('module_finance_enabled', 'true') == 'true',
            'module_tasks': SiteSettings.get('module_tasks_enabled', 'true') == 'true',
            'module_board': SiteSettings.get('module_board_enabled', 'true') == 'true',
            'module_leave': SiteSettings.get('module_leave_enabled', 'true') == 'true',
            'module_schedule': SiteSettings.get('module_schedule_enabled', 'true') == 'true',
            'module_notifications': SiteSettings.get('module_notifications_enabled', 'true') == 'true',
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