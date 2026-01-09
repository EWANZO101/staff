"""
Database Models for Staff Scheduling System
"""
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


# Association tables for many-to-many relationships
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    is_first_account = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, backref=db.backref('users', lazy='dynamic'))
    schedules = db.relationship('Schedule', backref='user', lazy='dynamic', foreign_keys='Schedule.user_id')
    leave_allocations = db.relationship('LeaveAllocation', backref='user', lazy='dynamic')
    leave_requests = db.relationship('LeaveRequest', backref='user', lazy='dynamic', foreign_keys='LeaveRequest.user_id')
    unavailability = db.relationship('Unavailability', backref='user', lazy='dynamic')
    tasks_assigned = db.relationship('Task', backref='assignee', lazy='dynamic', foreign_keys='Task.assigned_to')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission"""
        if self.is_first_account:
            return True  # Super admin has all permissions
        for role in self.roles:
            for perm in role.permissions:
                if perm.code == permission_code:
                    return True
        return False
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        if self.is_first_account:
            return True
        return any(role.name == role_name for role in self.roles)
    
    def get_unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()
    
    def get_recent_notifications(self, limit=10):
        return self.notifications.order_by(Notification.created_at.desc()).limit(limit).all()


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    is_system = db.Column(db.Boolean, default=False)  # System roles can't be deleted
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    permissions = db.relationship('Permission', secondary=role_permissions, 
                                  backref=db.backref('roles', lazy='dynamic'))


class Permission(db.Model):
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    category = db.Column(db.String(64))  # e.g., 'scheduling', 'leave', 'admin', 'tasks'


class Schedule(db.Model):
    __tablename__ = 'schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    
    __table_args__ = (
        db.Index('idx_schedule_user_date', 'user_id', 'date'),
    )


class RestrictedDay(db.Model):
    __tablename__ = 'restricted_days'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)
    reason = db.Column(db.String(256), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', foreign_keys=[created_by])


class LeaveType(db.Model):
    __tablename__ = 'leave_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    is_paid = db.Column(db.Boolean, default=True)
    color = db.Column(db.String(7), default='#3B82F6')  # Hex color for UI
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LeaveAllocation(db.Model):
    __tablename__ = 'leave_allocations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    allocated_days = db.Column(db.Float, default=0)
    allocated_hours = db.Column(db.Float, default=0)
    used_days = db.Column(db.Float, default=0)
    used_hours = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    leave_type = db.relationship('LeaveType')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'leave_type_id', 'year', name='unique_user_leave_year'),
    )
    
    @property
    def remaining_days(self):
        return self.allocated_days - self.used_days
    
    @property
    def remaining_hours(self):
        return self.allocated_hours - self.used_hours


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    leave_type = db.relationship('LeaveType')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    @property
    def days_count(self):
        """Calculate number of working days (Mon-Fri) in the leave period"""
        days = 0
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days += 1
            current = date(current.year, current.month, current.day + 1) if current.day < 28 else \
                      date(current.year, current.month + 1, 1) if current.month < 12 else \
                      date(current.year + 1, 1, 1)
        return days


class Unavailability(db.Model):
    __tablename__ = 'unavailability'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_unavailability'),
    )


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    due_date = db.Column(db.Date)
    due_time = db.Column(db.Time)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    assigner = db.relationship('User', foreign_keys=[assigned_by])
    
    @property
    def is_overdue(self):
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return date.today() > self.due_date
        return False


class BoardPost(db.Model):
    __tablename__ = 'board_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(50), default='announcement')  # announcement, event, task_needed, operational
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    event_date = db.Column(db.Date)
    event_time = db.Column(db.Time)
    is_pinned = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    author = db.relationship('User', foreign_keys=[created_by])
    
    @property
    def is_expired(self):
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False


class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, error, shift, leave, task
    is_read = db.Column(db.Boolean, default=False)
    is_popup = db.Column(db.Boolean, default=True)  # Show as popup on next page load
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    related_id = db.Column(db.Integer)  # ID of related object (schedule, task, etc.)
    related_type = db.Column(db.String(50))  # Type of related object
    
    __table_args__ = (
        db.Index('idx_notification_user_unread', 'user_id', 'is_read'),
    )


class MonthlyRequirement(db.Model):
    __tablename__ = 'monthly_requirements'
    
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    required_hours = db.Column(db.Float)
    required_days = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='unique_year_month'),
    )


class AuditLog(db.Model):
    """Audit trail for important actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')


def init_default_data():
    """Initialize default roles, permissions, and leave types"""
    
    # Check if data already exists
    if Permission.query.first():
        return
    
    # Default permissions
    permissions_data = [
        # Scheduling permissions
        ('View Own Schedule', 'schedule.view_own', 'View own work schedule', 'scheduling'),
        ('View All Schedules', 'schedule.view_all', 'View all user schedules', 'scheduling'),
        ('Create Schedule', 'schedule.create', 'Create/assign schedules', 'scheduling'),
        ('Edit Schedule', 'schedule.edit', 'Edit schedules', 'scheduling'),
        ('Delete Schedule', 'schedule.delete', 'Delete schedules', 'scheduling'),
        
        # Leave permissions
        ('Request Leave', 'leave.request', 'Submit leave requests', 'leave'),
        ('View Own Leave', 'leave.view_own', 'View own leave balance and requests', 'leave'),
        ('View All Leave', 'leave.view_all', 'View all leave requests', 'leave'),
        ('Approve Leave', 'leave.approve', 'Approve/reject leave requests', 'leave'),
        ('Manage Allocations', 'leave.allocate', 'Manage leave allocations', 'leave'),
        
        # User management
        ('View Users', 'users.view', 'View user list', 'admin'),
        ('Create Users', 'users.create', 'Create new users', 'admin'),
        ('Edit Users', 'users.edit', 'Edit user details', 'admin'),
        ('Delete Users', 'users.delete', 'Delete users', 'admin'),
        ('Manage Roles', 'roles.manage', 'Create and manage roles', 'admin'),
        
        # Task permissions
        ('View Own Tasks', 'tasks.view_own', 'View tasks assigned to self', 'tasks'),
        ('View All Tasks', 'tasks.view_all', 'View all tasks', 'tasks'),
        ('Create Tasks', 'tasks.create', 'Create and assign tasks', 'tasks'),
        ('Edit Tasks', 'tasks.edit', 'Edit tasks', 'tasks'),
        ('Delete Tasks', 'tasks.delete', 'Delete tasks', 'tasks'),
        
        # Board permissions
        ('View Board', 'board.view', 'View public board', 'board'),
        ('Create Posts', 'board.create', 'Create board posts', 'board'),
        ('Edit Posts', 'board.edit', 'Edit board posts', 'board'),
        ('Delete Posts', 'board.delete', 'Delete board posts', 'board'),
        ('Pin Posts', 'board.pin', 'Pin/unpin board posts', 'board'),
        
        # Management permissions
        ('Manage Restricted Days', 'management.restricted', 'Manage restricted days', 'management'),
        ('Manage Requirements', 'management.requirements', 'Set monthly requirements', 'management'),
        ('View Reports', 'management.reports', 'View system reports', 'management'),
        ('System Settings', 'management.settings', 'Manage system settings', 'management'),
    ]
    
    permissions = {}
    for name, code, desc, category in permissions_data:
        perm = Permission(name=name, code=code, description=desc, category=category)
        db.session.add(perm)
        permissions[code] = perm
    
    # Default roles
    admin_role = Role(
        name='Administrator',
        description='Full system access',
        is_system=True
    )
    admin_role.permissions = list(permissions.values())
    db.session.add(admin_role)
    
    manager_role = Role(
        name='Manager',
        description='Manage schedules, leave, and tasks',
        is_system=True
    )
    manager_perms = [
        'schedule.view_own', 'schedule.view_all', 'schedule.create', 'schedule.edit',
        'leave.request', 'leave.view_own', 'leave.view_all', 'leave.approve',
        'users.view', 'tasks.view_own', 'tasks.view_all', 'tasks.create', 'tasks.edit',
        'board.view', 'board.create', 'board.edit', 'board.pin',
        'management.restricted', 'management.requirements', 'management.reports'
    ]
    manager_role.permissions = [permissions[p] for p in manager_perms]
    db.session.add(manager_role)
    
    user_role = Role(
        name='User',
        description='Basic user access',
        is_system=True
    )
    user_perms = [
        'schedule.view_own', 'leave.request', 'leave.view_own',
        'tasks.view_own', 'board.view'
    ]
    user_role.permissions = [permissions[p] for p in user_perms]
    db.session.add(user_role)
    
    # Default leave types
    leave_types = [
        ('Annual Leave', 'Paid annual vacation days', True, '#10B981'),
        ('Sick Leave', 'Paid sick days', True, '#EF4444'),
        ('Personal Leave', 'Personal time off', True, '#8B5CF6'),
        ('Unpaid Leave', 'Unpaid time off', False, '#6B7280'),
        ('Bereavement', 'Compassionate leave', True, '#1F2937'),
        ('Maternity/Paternity', 'Parental leave', True, '#EC4899'),
    ]
    
    for name, desc, is_paid, color in leave_types:
        lt = LeaveType(name=name, description=desc, is_paid=is_paid, color=color)
        db.session.add(lt)
    
    db.session.commit()
