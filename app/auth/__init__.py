"""
Authentication Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from datetime import datetime, timedelta
from app import db
from app.models import User, Role, Notification, LeaveType, LeaveAllocation
from app.auth.forms import LoginForm, SignupForm

bp = Blueprint('auth', __name__)

# Simple rate limiting for login attempts
login_attempts = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutes


def check_rate_limit(ip):
    """Check if IP is rate limited"""
    now = datetime.utcnow()
    if ip in login_attempts:
        attempts, lockout_until = login_attempts[ip]
        if lockout_until and now < lockout_until:
            return False, int((lockout_until - now).total_seconds())
        if lockout_until and now >= lockout_until:
            login_attempts[ip] = (0, None)
    return True, 0


def record_failed_attempt(ip):
    """Record a failed login attempt"""
    now = datetime.utcnow()
    if ip in login_attempts:
        attempts, _ = login_attempts[ip]
        attempts += 1
    else:
        attempts = 1
    
    if attempts >= MAX_ATTEMPTS:
        lockout_until = now + timedelta(seconds=LOCKOUT_TIME)
        login_attempts[ip] = (attempts, lockout_until)
    else:
        login_attempts[ip] = (attempts, None)


def clear_attempts(ip):
    """Clear login attempts on successful login"""
    if ip in login_attempts:
        del login_attempts[ip]


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Check rate limiting
    client_ip = request.remote_addr
    allowed, wait_time = check_rate_limit(client_ip)
    if not allowed:
        flash(f'Too many login attempts. Please wait {wait_time} seconds.', 'error')
        return render_template('auth/login.html', form=LoginForm())
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user is None or not user.check_password(form.password.data):
            record_failed_attempt(client_ip)
            flash('Invalid email or password', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'error')
            return redirect(url_for('auth.login'))
        
        # Successful login - clear rate limit
        clear_attempts(client_ip)
        
        login_user(user, remember=form.remember_me.data)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Check for unread notifications to show as popups
        unread_count = user.get_unread_notifications_count()
        if unread_count > 0:
            flash(f'You have {unread_count} unread notification(s)', 'info')
        
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', form=form)


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = SignupForm()
    if form.validate_on_submit():
        # Check if this is the first account
        is_first = User.query.count() == 0
        
        user = User(
            email=form.email.data.lower(),
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            is_first_account=is_first
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Assign role
        if is_first:
            # First account gets admin role automatically
            admin_role = Role.query.filter_by(name='Administrator').first()
            if admin_role:
                user.roles.append(admin_role)
            flash('Welcome! As the first user, you have been granted full administrator access.', 'success')
        else:
            # Regular users get User role
            user_role = Role.query.filter_by(name='User').first()
            if user_role:
                user.roles.append(user_role)
        
        # Create default leave allocations for the current year
        current_year = datetime.now().year
        leave_types = LeaveType.query.filter_by(is_active=True).all()
        default_allocations = {
            'Annual Leave': 25,
            'Sick Leave': 10,
            'Personal Leave': 5,
            'Unpaid Leave': 0,
            'Bereavement': 5,
            'Maternity/Paternity': 0,
        }
        
        for lt in leave_types:
            allocation = LeaveAllocation(
                user_id=user.id,
                leave_type_id=lt.id,
                year=current_year,
                allocated_days=default_allocations.get(lt.name, 0)
            )
            db.session.add(allocation)
        
        # Create welcome notification
        notification = Notification(
            user_id=user.id,
            title='Welcome to Staff Scheduler!',
            message='Your account has been created. Check out your dashboard to view your schedule and manage your time.',
            type='success',
            is_popup=True
        )
        db.session.add(notification)
        
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/signup.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

from app.auth import routes
