"""
Authentication Blueprint
Handles login, signup, logout, and password management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))
    
    if request.method == 'POST':
        from app import db, User, bcrypt
        
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html')
            
            # Store last login for notifications
            previous_login = user.last_login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(user, remember=remember)
            
            # Check for login notifications
            login_notifications = user.get_login_notifications()
            if login_notifications:
                # Store notification IDs in session for popup display
                from flask import session
                session['login_notifications'] = [n.id for n in login_notifications[:5]]
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('user.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))
    
    if request.method == 'POST':
        from app import db, User, bcrypt, Role, Permission
        
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        
        # Validation
        errors = []
        
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not first_name or not last_name:
            errors.append('Please enter your full name.')
        
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/signup.html')
        
        # Check if this is the first user
        is_first = User.query.count() == 0
        
        # Create user
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            first_name=first_name,
            last_name=last_name,
            is_first_user=is_first
        )
        
        db.session.add(user)
        db.session.commit()
        
        if is_first:
            # Create Super Admin role with all permissions
            super_admin = Role(name='Super Admin', description='Full system access', is_system=True)
            db.session.add(super_admin)
            db.session.commit()
            
            # Assign all permissions to Super Admin
            all_permissions = Permission.query.all()
            for perm in all_permissions:
                super_admin.permissions.append(perm)
            
            # Assign Super Admin role to first user
            user.roles.append(super_admin)
            db.session.commit()
            
            flash('Welcome! As the first user, you have been granted Super Admin access with full permissions.', 'success')
        else:
            flash('Account created successfully! Please log in.', 'success')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/signup.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
