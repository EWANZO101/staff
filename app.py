"""
Staff Scheduling System
A comprehensive scheduling, leave management, task assignment, and team coordination platform.
"""

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, date, timedelta
from functools import wraps
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///staff_scheduler.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# ============================================================
# DATABASE MODELS
# ============================================================

# Association tables
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_first_user = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))
    schedules = db.relationship('Schedule', backref='user', lazy='dynamic')
    leave_requests = db.relationship('LeaveRequest', backref='user', lazy='dynamic')
    leave_allowances = db.relationship('LeaveAllowance', backref='user', lazy='dynamic')
    assigned_tasks = db.relationship('TaskAssignment', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def has_permission(self, permission_name):
        """Check if user has a specific permission"""
        if self.is_first_user:
            return True
        for role in self.roles:
            for perm in role.permissions:
                if perm.name == permission_name:
                    return True
        return False
    
    def has_any_permission(self, permission_names):
        """Check if user has any of the given permissions"""
        if self.is_first_user:
            return True
        for perm_name in permission_names:
            if self.has_permission(perm_name):
                return True
        return False
    
    def get_unread_notifications(self):
        return self.notifications.filter_by(is_read=False).order_by(Notification.created_at.desc()).all()
    
    def get_login_notifications(self):
        """Get notifications created since last login"""
        if self.last_login:
            return self.notifications.filter(
                Notification.created_at > self.last_login,
                Notification.is_read == False
            ).order_by(Notification.created_at.desc()).all()
        return self.notifications.filter_by(is_read=False).order_by(Notification.created_at.desc()).all()


class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    is_system = db.Column(db.Boolean, default=False)  # System roles can't be deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    permissions = db.relationship('Permission', secondary=role_permissions, backref=db.backref('roles', lazy='dynamic'))


class Permission(db.Model):
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    category = db.Column(db.String(50))  # For grouping in UI


class Schedule(db.Model):
    __tablename__ = 'schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.String(500))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_schedule'),)


class LeaveType(db.Model):
    __tablename__ = 'leave_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    color = db.Column(db.String(20), default='blue')  # For UI display
    is_active = db.Column(db.Boolean, default=True)
    requires_approval = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LeaveAllowance(db.Model):
    __tablename__ = 'leave_allowances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_days = db.Column(db.Float, default=0)
    used_days = db.Column(db.Float, default=0)
    
    leave_type = db.relationship('LeaveType')
    
    @property
    def remaining_days(self):
        return self.total_days - self.used_days
    
    __table_args__ = (db.UniqueConstraint('user_id', 'leave_type_id', 'year', name='unique_user_leave_allowance'),)


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    leave_type = db.relationship('LeaveType')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    @property
    def days_count(self):
        delta = self.end_date - self.start_date
        return delta.days + 1


class RestrictedDay(db.Model):
    __tablename__ = 'restricted_days'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    reason = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MonthlyConfig(db.Model):
    __tablename__ = 'monthly_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    required_days = db.Column(db.Integer)
    required_hours = db.Column(db.Float)
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('year', 'month', name='unique_monthly_config'),)


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    due_date = db.Column(db.Date)
    due_time = db.Column(db.Time)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    assignments = db.relationship('TaskAssignment', backref='task', lazy='dynamic')


class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed
    
    __table_args__ = (db.UniqueConstraint('task_id', 'user_id', name='unique_task_assignment'),)


class BoardPost(db.Model):
    __tablename__ = 'board_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    post_type = db.Column(db.String(30), default='announcement')  # announcement, event, task, operations
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    event_date = db.Column(db.Date)
    event_time = db.Column(db.Time)
    is_pinned = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    creator = db.relationship('User', foreign_keys=[created_by])


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500))
    notification_type = db.Column(db.String(30))  # shift, leave, task, board, system
    reference_id = db.Column(db.Integer)  # ID of related item
    reference_type = db.Column(db.String(30))  # schedule, leave_request, task, board_post
    is_read = db.Column(db.Boolean, default=False)
    is_popup = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def permission_required(permission_name):
    """Decorator to require a specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if not current_user.has_permission(permission_name):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('user.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def any_permission_required(permission_names):
    """Decorator to require any of the given permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if not current_user.has_any_permission(permission_names):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('user.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def create_notification(user_id, title, message, notification_type, reference_id=None, reference_type=None, is_popup=True):
    """Create a notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        reference_id=reference_id,
        reference_type=reference_type,
        is_popup=is_popup
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def init_permissions():
    """Initialize default permissions"""
    permissions = [
        # User Management
        ('manage_users', 'Create, edit, and delete users', 'Users'),
        ('view_all_users', 'View all user profiles', 'Users'),
        ('manage_roles', 'Create and assign roles', 'Users'),
        
        # Schedule Management
        ('manage_schedules', 'Assign and edit schedules', 'Schedules'),
        ('view_all_schedules', 'View all user schedules', 'Schedules'),
        
        # Leave Management
        ('approve_leave', 'Approve or reject leave requests', 'Leave'),
        ('manage_leave_types', 'Create and edit leave types', 'Leave'),
        ('manage_leave_allowances', 'Set user leave allowances', 'Leave'),
        ('view_all_leave', 'View all leave requests', 'Leave'),
        
        # System Configuration
        ('manage_restricted_days', 'Set restricted days', 'System'),
        ('manage_monthly_config', 'Configure monthly requirements', 'System'),
        
        # Tasks
        ('manage_tasks', 'Create and assign tasks', 'Tasks'),
        ('view_all_tasks', 'View all tasks', 'Tasks'),
        
        # Board
        ('manage_board', 'Create and edit board posts', 'Board'),
    ]
    
    for name, description, category in permissions:
        if not Permission.query.filter_by(name=name).first():
            perm = Permission(name=name, description=description, category=category)
            db.session.add(perm)
    
    db.session.commit()


def init_leave_types():
    """Initialize default leave types"""
    leave_types = [
        ('Annual Leave', 'Paid vacation days', 'green'),
        ('Sick Leave', 'Leave for illness or medical appointments', 'red'),
        ('Personal Leave', 'Personal matters and emergencies', 'yellow'),
        ('Unpaid Leave', 'Leave without pay', 'gray'),
        ('Compassionate Leave', 'Bereavement or family emergencies', 'purple'),
    ]
    
    for name, description, color in leave_types:
        if not LeaveType.query.filter_by(name=name).first():
            leave_type = LeaveType(name=name, description=description, color=color)
            db.session.add(leave_type)
    
    db.session.commit()


# ============================================================
# BLUEPRINTS REGISTRATION
# ============================================================

from blueprints.auth import auth_bp
from blueprints.user import user_bp
from blueprints.admin import admin_bp
from blueprints.management import management_bp
from blueprints.tasks import tasks_bp
from blueprints.board import board_bp
from blueprints.api import api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(management_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(board_bp)
app.register_blueprint(api_bp)


# ============================================================
# MAIN ROUTES
# ============================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))
    return redirect(url_for('auth.login'))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


# ============================================================
# CONTEXT PROCESSORS
# ============================================================

@app.context_processor
def utility_processor():
    def format_date(date_obj):
        if date_obj:
            return date_obj.strftime('%d/%m/%Y')
        return ''
    
    def format_time(time_obj):
        if time_obj:
            return time_obj.strftime('%H:%M')
        return ''
    
    def format_datetime(dt_obj):
        if dt_obj:
            return dt_obj.strftime('%d/%m/%Y %H:%M')
        return ''
    
    return dict(
        format_date=format_date,
        format_time=format_time,
        format_datetime=format_datetime,
        now=datetime.utcnow()
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Initialize the database with tables and default data"""
    with app.app_context():
        db.create_all()
        init_permissions()
        init_leave_types()
        print("Database initialized successfully!")


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
