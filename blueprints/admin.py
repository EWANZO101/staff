"""
Admin Blueprint
User management, schedule assignment, leave approval, and admin functions
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Check if user has any admin permissions"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))
        
        admin_perms = ['manage_users', 'manage_schedules', 'approve_leave', 'manage_roles']
        if not current_user.has_any_permission(admin_perms):
            flash('Admin access required.', 'danger')
            return redirect(url_for('user.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@login_required
@admin_required
def index():
    from app import User, LeaveRequest, Schedule, Task
    
    today = date.today()
    
    # Stats
    total_users = User.query.filter_by(is_active=True).count()
    pending_leave = LeaveRequest.query.filter_by(status='pending').count()
    today_schedules = Schedule.query.filter_by(date=today).count()
    pending_tasks = Task.query.filter_by(status='pending').count()
    
    # Recent leave requests
    recent_leave = LeaveRequest.query.filter_by(status='pending').order_by(
        LeaveRequest.created_at.desc()
    ).limit(5).all()
    
    # Today's scheduled staff
    todays_staff = Schedule.query.filter_by(date=today).all()
    
    return render_template('admin/index.html',
        total_users=total_users,
        pending_leave=pending_leave,
        today_schedules=today_schedules,
        pending_tasks=pending_tasks,
        recent_leave=recent_leave,
        todays_staff=todays_staff,
        today=today
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    from app import User, Role
    
    users = User.query.order_by(User.last_name, User.first_name).all()
    roles = Role.query.all()
    
    return render_template('admin/users.html', users=users, roles=roles)


@admin_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    from app import db, User, bcrypt, permission_required
    
    if not current_user.has_permission('manage_users'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.users'))
    
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    
    if User.query.filter_by(email=email).first():
        flash('Email already exists.', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User(
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
        first_name=first_name,
        last_name=last_name
    )
    
    db.session.add(user)
    db.session.commit()
    
    flash(f'User {user.full_name} created successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
def edit_user(user_id):
    from app import db, User, Role
    
    if not current_user.has_permission('manage_users'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    
    user.first_name = request.form.get('first_name', user.first_name).strip()
    user.last_name = request.form.get('last_name', user.last_name).strip()
    user.email = request.form.get('email', user.email).strip().lower()
    user.is_active = request.form.get('is_active') == 'on'
    
    # Update roles
    if current_user.has_permission('manage_roles'):
        role_ids = request.form.getlist('roles')
        user.roles = []
        for role_id in role_ids:
            role = Role.query.get(role_id)
            if role:
                user.roles.append(role)
    
    db.session.commit()
    flash(f'User {user.full_name} updated.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    from app import db, User
    
    if not current_user.has_permission('manage_users'):
        return jsonify({'error': 'Permission denied'}), 403
    
    user = User.query.get_or_404(user_id)
    
    if user.is_first_user:
        return jsonify({'error': 'Cannot deactivate the primary admin'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': user.is_active,
        'message': f'User {"activated" if user.is_active else "deactivated"}'
    })


# ============================================================
# ROLE MANAGEMENT
# ============================================================

@admin_bp.route('/roles')
@login_required
def roles():
    from app import Role, Permission
    
    if not current_user.has_permission('manage_roles'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.index'))
    
    roles = Role.query.all()
    permissions = Permission.query.order_by(Permission.category, Permission.name).all()
    
    # Group permissions by category
    perm_categories = {}
    for perm in permissions:
        if perm.category not in perm_categories:
            perm_categories[perm.category] = []
        perm_categories[perm.category].append(perm)
    
    return render_template('admin/roles.html', roles=roles, perm_categories=perm_categories)


@admin_bp.route('/roles/add', methods=['POST'])
@login_required
def add_role():
    from app import db, Role, Permission
    
    if not current_user.has_permission('manage_roles'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.roles'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    permission_ids = request.form.getlist('permissions')
    
    if Role.query.filter_by(name=name).first():
        flash('Role name already exists.', 'danger')
        return redirect(url_for('admin.roles'))
    
    role = Role(name=name, description=description)
    
    for perm_id in permission_ids:
        perm = Permission.query.get(perm_id)
        if perm:
            role.permissions.append(perm)
    
    db.session.add(role)
    db.session.commit()
    
    flash(f'Role "{name}" created.', 'success')
    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/<int:role_id>/edit', methods=['POST'])
@login_required
def edit_role(role_id):
    from app import db, Role, Permission
    
    if not current_user.has_permission('manage_roles'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.roles'))
    
    role = Role.query.get_or_404(role_id)
    
    if role.is_system and not current_user.is_first_user:
        flash('Cannot modify system roles.', 'danger')
        return redirect(url_for('admin.roles'))
    
    role.name = request.form.get('name', role.name).strip()
    role.description = request.form.get('description', role.description).strip()
    
    # Update permissions
    permission_ids = request.form.getlist('permissions')
    role.permissions = []
    for perm_id in permission_ids:
        perm = Permission.query.get(perm_id)
        if perm:
            role.permissions.append(perm)
    
    db.session.commit()
    flash(f'Role "{role.name}" updated.', 'success')
    return redirect(url_for('admin.roles'))


@admin_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@login_required
def delete_role(role_id):
    from app import db, Role
    
    if not current_user.has_permission('manage_roles'):
        return jsonify({'error': 'Permission denied'}), 403
    
    role = Role.query.get_or_404(role_id)
    
    if role.is_system:
        return jsonify({'error': 'Cannot delete system roles'}), 400
    
    db.session.delete(role)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Role "{role.name}" deleted'})


# ============================================================
# SCHEDULE MANAGEMENT
# ============================================================

@admin_bp.route('/schedules')
@admin_bp.route('/schedules/<int:year>/<int:month>')
@login_required
@admin_required
def schedules(year=None, month=None):
    from app import User, Schedule, RestrictedDay
    
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    # Get all active users
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    
    # Calendar setup
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    # Get month boundaries
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    
    # Get all schedules for month
    schedules = Schedule.query.filter(
        Schedule.date >= month_start,
        Schedule.date <= month_end
    ).all()
    
    # Build schedule dictionary: {user_id: {date: schedule}}
    schedule_dict = {}
    for s in schedules:
        if s.user_id not in schedule_dict:
            schedule_dict[s.user_id] = {}
        schedule_dict[s.user_id][s.date] = s
    
    # Get restricted days
    restricted = RestrictedDay.query.filter(
        RestrictedDay.date >= month_start,
        RestrictedDay.date <= month_end
    ).all()
    restricted_dict = {r.date: r for r in restricted}
    
    # Navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    
    month_name = calendar.month_name[month]
    
    # Get weekdays in this month
    weekdays = []
    current_date = month_start
    while current_date <= month_end:
        if current_date.weekday() < 5:  # Mon-Fri
            weekdays.append(current_date)
        current_date += timedelta(days=1)
    
    return render_template('admin/schedules.html',
        users=users,
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        weekdays=weekdays,
        schedule_dict=schedule_dict,
        restricted_dict=restricted_dict,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )


@admin_bp.route('/schedules/assign', methods=['POST'])
@login_required
def assign_schedule():
    from app import db, Schedule, User, create_notification
    
    if not current_user.has_permission('manage_schedules'):
        return jsonify({'error': 'Permission denied'}), 403
    
    user_id = request.form.get('user_id')
    date_str = request.form.get('date')
    start_time_str = request.form.get('start_time', '09:00')
    end_time_str = request.form.get('end_time', '17:00')
    notes = request.form.get('notes', '')
    
    try:
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date or time format'}), 400
    
    # Check if schedule exists
    existing = Schedule.query.filter_by(user_id=user_id, date=schedule_date).first()
    
    if existing:
        existing.start_time = start_time
        existing.end_time = end_time
        existing.notes = notes
        message = 'Schedule updated'
    else:
        schedule = Schedule(
            user_id=user_id,
            date=schedule_date,
            start_time=start_time,
            end_time=end_time,
            notes=notes,
            created_by=current_user.id
        )
        db.session.add(schedule)
        message = 'Schedule assigned'
        
        # Notify user
        user = User.query.get(user_id)
        create_notification(
            user_id=user_id,
            title='New Shift Assigned',
            message=f'You have been scheduled to work on {schedule_date.strftime("%d/%m/%Y")} from {start_time_str} to {end_time_str}',
            notification_type='shift',
            reference_type='schedule'
        )
    
    db.session.commit()
    return jsonify({'success': True, 'message': message})


@admin_bp.route('/schedules/remove', methods=['POST'])
@login_required
def remove_schedule():
    from app import db, Schedule
    
    if not current_user.has_permission('manage_schedules'):
        return jsonify({'error': 'Permission denied'}), 403
    
    user_id = request.form.get('user_id')
    date_str = request.form.get('date')
    
    try:
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400
    
    schedule = Schedule.query.filter_by(user_id=user_id, date=schedule_date).first()
    
    if schedule:
        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Schedule removed'})
    
    return jsonify({'error': 'Schedule not found'}), 404


@admin_bp.route('/schedules/bulk', methods=['POST'])
@login_required
def bulk_schedule():
    from app import db, Schedule, User, create_notification
    
    if not current_user.has_permission('manage_schedules'):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    dates = data.get('dates', [])
    start_time_str = data.get('start_time', '09:00')
    end_time_str = data.get('end_time', '17:00')
    
    try:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid time format'}), 400
    
    created = 0
    for date_str in dates:
        try:
            schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            continue
        
        existing = Schedule.query.filter_by(user_id=user_id, date=schedule_date).first()
        if not existing:
            schedule = Schedule(
                user_id=user_id,
                date=schedule_date,
                start_time=start_time,
                end_time=end_time,
                created_by=current_user.id
            )
            db.session.add(schedule)
            created += 1
    
    db.session.commit()
    
    if created > 0:
        user = User.query.get(user_id)
        create_notification(
            user_id=user_id,
            title='New Shifts Assigned',
            message=f'You have been assigned {created} new shift(s)',
            notification_type='shift',
            reference_type='schedule'
        )
    
    return jsonify({'success': True, 'message': f'{created} schedules created'})


# ============================================================
# LEAVE MANAGEMENT
# ============================================================

@admin_bp.route('/leave')
@login_required
@admin_required
def leave():
    from app import LeaveRequest, LeaveType
    
    status_filter = request.args.get('status', 'pending')
    
    query = LeaveRequest.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    leave_requests = query.order_by(LeaveRequest.created_at.desc()).all()
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    return render_template('admin/leave.html',
        leave_requests=leave_requests,
        leave_types=leave_types,
        status_filter=status_filter
    )


@admin_bp.route('/leave/<int:leave_id>/approve', methods=['POST'])
@login_required
def approve_leave(leave_id):
    from app import db, LeaveRequest, LeaveAllowance, create_notification
    
    if not current_user.has_permission('approve_leave'):
        return jsonify({'error': 'Permission denied'}), 403
    
    leave_request = LeaveRequest.query.get_or_404(leave_id)
    notes = request.form.get('notes', '')
    
    leave_request.status = 'approved'
    leave_request.reviewed_by = current_user.id
    leave_request.reviewed_at = datetime.utcnow()
    leave_request.review_notes = notes
    
    # Update leave allowance
    allowance = LeaveAllowance.query.filter_by(
        user_id=leave_request.user_id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year
    ).first()
    
    if allowance:
        allowance.used_days += leave_request.days_count
    
    db.session.commit()
    
    # Notify user
    create_notification(
        user_id=leave_request.user_id,
        title='Leave Request Approved',
        message=f'Your {leave_request.leave_type.name} request from {leave_request.start_date.strftime("%d/%m/%Y")} to {leave_request.end_date.strftime("%d/%m/%Y")} has been approved.',
        notification_type='leave',
        reference_id=leave_request.id,
        reference_type='leave_request'
    )
    
    return jsonify({'success': True, 'message': 'Leave approved'})


@admin_bp.route('/leave/<int:leave_id>/reject', methods=['POST'])
@login_required
def reject_leave(leave_id):
    from app import db, LeaveRequest, create_notification
    
    if not current_user.has_permission('approve_leave'):
        return jsonify({'error': 'Permission denied'}), 403
    
    leave_request = LeaveRequest.query.get_or_404(leave_id)
    notes = request.form.get('notes', '')
    
    leave_request.status = 'rejected'
    leave_request.reviewed_by = current_user.id
    leave_request.reviewed_at = datetime.utcnow()
    leave_request.review_notes = notes
    
    db.session.commit()
    
    # Notify user
    create_notification(
        user_id=leave_request.user_id,
        title='Leave Request Rejected',
        message=f'Your {leave_request.leave_type.name} request from {leave_request.start_date.strftime("%d/%m/%Y")} to {leave_request.end_date.strftime("%d/%m/%Y")} has been rejected. Reason: {notes}',
        notification_type='leave',
        reference_id=leave_request.id,
        reference_type='leave_request'
    )
    
    return jsonify({'success': True, 'message': 'Leave rejected'})


@admin_bp.route('/leave/allowances')
@login_required
@admin_required
def leave_allowances():
    from app import User, LeaveType, LeaveAllowance
    
    if not current_user.has_permission('manage_leave_allowances'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin.index'))
    
    year = request.args.get('year', date.today().year, type=int)
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    # Get all allowances for the year
    allowances = LeaveAllowance.query.filter_by(year=year).all()
    allowance_dict = {}
    for a in allowances:
        if a.user_id not in allowance_dict:
            allowance_dict[a.user_id] = {}
        allowance_dict[a.user_id][a.leave_type_id] = a
    
    return render_template('admin/leave_allowances.html',
        users=users,
        leave_types=leave_types,
        allowance_dict=allowance_dict,
        year=year
    )


@admin_bp.route('/leave/allowances/set', methods=['POST'])
@login_required
def set_leave_allowance():
    from app import db, LeaveAllowance
    
    if not current_user.has_permission('manage_leave_allowances'):
        return jsonify({'error': 'Permission denied'}), 403
    
    user_id = request.form.get('user_id', type=int)
    leave_type_id = request.form.get('leave_type_id', type=int)
    year = request.form.get('year', type=int)
    total_days = request.form.get('total_days', type=float)
    
    allowance = LeaveAllowance.query.filter_by(
        user_id=user_id,
        leave_type_id=leave_type_id,
        year=year
    ).first()
    
    if allowance:
        allowance.total_days = total_days
    else:
        allowance = LeaveAllowance(
            user_id=user_id,
            leave_type_id=leave_type_id,
            year=year,
            total_days=total_days
        )
        db.session.add(allowance)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Allowance updated'})
