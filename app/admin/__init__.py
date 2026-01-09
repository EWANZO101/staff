"""
Admin Blueprint - User Management, Scheduling, Leave Approval
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from calendar import monthrange
from app import db
from app.models import (
    User, Role, Permission, Schedule, LeaveRequest, LeaveType, 
    LeaveAllocation, Notification, RestrictedDay, AuditLog
)
from app.decorators import permission_required

bp = Blueprint('admin', __name__)


# ==================== USER MANAGEMENT ====================

@bp.route('/users')
@login_required
@permission_required('users.view')
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    if search:
        query = query.filter(
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.last_name).paginate(page=page, per_page=20)
    return render_template('admin/users.html', users=users, search=search)


@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@permission_required('users.create')
def create_user():
    roles = Role.query.all()
    
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        phone = request.form.get('phone')
        department = request.form.get('department')
        role_ids = request.form.getlist('roles')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('admin.create_user'))
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            department=department
        )
        user.set_password(password)
        
        # Assign roles
        for role_id in role_ids:
            role = Role.query.get(role_id)
            if role:
                user.roles.append(role)
        
        db.session.add(user)
        db.session.flush()
        
        # Create default leave allocations
        current_year = datetime.now().year
        leave_types = LeaveType.query.filter_by(is_active=True).all()
        default_allocations = {
            'Annual Leave': 25,
            'Sick Leave': 10,
            'Personal Leave': 5,
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
            message='Your account has been created by an administrator.',
            type='success',
            is_popup=True
        )
        db.session.add(notification)
        
        # Audit log
        log = AuditLog(
            user_id=current_user.id,
            action='create_user',
            entity_type='user',
            entity_id=user.id,
            details=f'Created user: {user.email}'
        )
        db.session.add(log)
        
        db.session.commit()
        flash(f'User {user.full_name} created successfully', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/create_user.html', roles=roles)


@bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('users.edit')
def edit_user(id):
    user = User.query.get_or_404(id)
    roles = Role.query.all()
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.phone = request.form.get('phone')
        user.department = request.form.get('department')
        user.is_active = 'is_active' in request.form
        
        # Update password if provided
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
        
        # Update roles (only if not first account)
        if not user.is_first_account:
            role_ids = request.form.getlist('roles')
            user.roles = []
            for role_id in role_ids:
                role = Role.query.get(role_id)
                if role:
                    user.roles.append(role)
        
        db.session.commit()
        flash(f'User {user.full_name} updated successfully', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', user=user, roles=roles)


@bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('users.delete')
def delete_user(id):
    user = User.query.get_or_404(id)
    
    if user.is_first_account:
        flash('Cannot delete the super admin account', 'error')
        return redirect(url_for('admin.users'))
    
    if user.id == current_user.id:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin.users'))
    
    # Soft delete - deactivate instead
    user.is_active = False
    db.session.commit()
    flash(f'User {user.full_name} has been deactivated', 'success')
    return redirect(url_for('admin.users'))


# ==================== ROLE MANAGEMENT ====================

@bp.route('/roles')
@login_required
@permission_required('roles.manage')
def roles():
    roles = Role.query.all()
    return render_template('admin/roles.html', roles=roles)


@bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@permission_required('roles.manage')
def create_role():
    permissions = Permission.query.order_by(Permission.category).all()
    
    # Group permissions by category
    perm_categories = {}
    for perm in permissions:
        if perm.category not in perm_categories:
            perm_categories[perm.category] = []
        perm_categories[perm.category].append(perm)
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        permission_ids = request.form.getlist('permissions')
        
        if Role.query.filter_by(name=name).first():
            flash('Role name already exists', 'error')
            return redirect(url_for('admin.create_role'))
        
        role = Role(
            name=name,
            description=description,
            created_by=current_user.id
        )
        
        for perm_id in permission_ids:
            perm = Permission.query.get(perm_id)
            if perm:
                role.permissions.append(perm)
        
        db.session.add(role)
        db.session.commit()
        flash(f'Role "{name}" created successfully', 'success')
        return redirect(url_for('admin.roles'))
    
    return render_template('admin/create_role.html', perm_categories=perm_categories)


@bp.route('/roles/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('roles.manage')
def edit_role(id):
    role = Role.query.get_or_404(id)
    permissions = Permission.query.order_by(Permission.category).all()
    
    # Group permissions by category
    perm_categories = {}
    for perm in permissions:
        if perm.category not in perm_categories:
            perm_categories[perm.category] = []
        perm_categories[perm.category].append(perm)
    
    if request.method == 'POST':
        role.name = request.form.get('name')
        role.description = request.form.get('description')
        permission_ids = request.form.getlist('permissions')
        
        role.permissions = []
        for perm_id in permission_ids:
            perm = Permission.query.get(perm_id)
            if perm:
                role.permissions.append(perm)
        
        db.session.commit()
        flash(f'Role "{role.name}" updated successfully', 'success')
        return redirect(url_for('admin.roles'))
    
    return render_template('admin/edit_role.html', role=role, perm_categories=perm_categories)


@bp.route('/roles/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('roles.manage')
def delete_role(id):
    role = Role.query.get_or_404(id)
    
    if role.is_system:
        flash('Cannot delete system roles', 'error')
        return redirect(url_for('admin.roles'))
    
    db.session.delete(role)
    db.session.commit()
    flash(f'Role "{role.name}" deleted', 'success')
    return redirect(url_for('admin.roles'))


# ==================== SCHEDULE MANAGEMENT ====================

@bp.route('/schedules')
@bp.route('/schedules/<int:year>/<int:month>')
@login_required
@permission_required('schedule.view_all')
def schedules(year=None, month=None):
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    # Get all users
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    
    # Get all schedules for the month
    schedules = Schedule.query.filter(
        Schedule.date >= first_day,
        Schedule.date <= last_day
    ).all()
    
    # Build schedule matrix
    schedule_dict = {}
    for s in schedules:
        key = (s.user_id, s.date)
        schedule_dict[key] = s
    
    # Build calendar days (weekdays only)
    days = []
    current = first_day
    while current <= last_day:
        if current.weekday() < 5:  # Monday to Friday
            days.append(current)
        current += timedelta(days=1)
    
    # Navigation
    prev_month = first_day - timedelta(days=1)
    next_month = last_day + timedelta(days=1)
    
    return render_template('admin/schedules.html',
        users=users,
        days=days,
        schedule_dict=schedule_dict,
        year=year,
        month=month,
        month_name=first_day.strftime('%B'),
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month.year,
        next_month=next_month.month
    )


@bp.route('/schedules/assign', methods=['POST'])
@login_required
@permission_required('schedule.create')
def assign_schedule():
    user_id = request.form.get('user_id')
    date_str = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    notes = request.form.get('notes')
    
    try:
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start = datetime.strptime(start_time, '%H:%M').time()
        end = datetime.strptime(end_time, '%H:%M').time()
        
        # Check if schedule already exists
        existing = Schedule.query.filter_by(
            user_id=user_id,
            date=schedule_date
        ).first()
        
        if existing:
            existing.start_time = start
            existing.end_time = end
            existing.notes = notes
            flash('Schedule updated', 'success')
        else:
            schedule = Schedule(
                user_id=user_id,
                date=schedule_date,
                start_time=start,
                end_time=end,
                notes=notes,
                created_by=current_user.id
            )
            db.session.add(schedule)
            
            # Notify user
            user = User.query.get(user_id)
            notification = Notification(
                user_id=user_id,
                title='New Shift Assigned',
                message=f'You have been assigned a shift on {schedule_date.strftime("%d/%m/%Y")} '
                       f'from {start.strftime("%H:%M")} to {end.strftime("%H:%M")}',
                type='shift',
                is_popup=True,
                related_id=schedule.id,
                related_type='schedule'
            )
            db.session.add(notification)
            flash('Schedule assigned and user notified', 'success')
        
        db.session.commit()
        
    except ValueError as e:
        flash(f'Invalid data: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('admin.schedules'))


@bp.route('/schedules/bulk-assign', methods=['GET', 'POST'])
@login_required
@permission_required('schedule.create')
def bulk_assign_schedule():
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    
    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        days_of_week = request.form.getlist('days_of_week')  # 0=Mon, 4=Fri
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            st = datetime.strptime(start_time, '%H:%M').time()
            et = datetime.strptime(end_time, '%H:%M').time()
            selected_days = [int(d) for d in days_of_week]
            
            count = 0
            current = start
            while current <= end:
                if current.weekday() in selected_days:
                    for user_id in user_ids:
                        # Check if exists
                        existing = Schedule.query.filter_by(
                            user_id=user_id,
                            date=current
                        ).first()
                        
                        if not existing:
                            schedule = Schedule(
                                user_id=user_id,
                                date=current,
                                start_time=st,
                                end_time=et,
                                created_by=current_user.id
                            )
                            db.session.add(schedule)
                            count += 1
                            
                            # Notify user
                            notification = Notification(
                                user_id=user_id,
                                title='New Shift Assigned',
                                message=f'You have been assigned a shift on {current.strftime("%d/%m/%Y")}',
                                type='shift',
                                is_popup=True
                            )
                            db.session.add(notification)
                
                current += timedelta(days=1)
            
            db.session.commit()
            flash(f'{count} schedules created successfully', 'success')
            return redirect(url_for('admin.schedules'))
            
        except ValueError as e:
            flash(f'Invalid data: {str(e)}', 'error')
    
    return render_template('admin/bulk_assign.html', users=users)


@bp.route('/schedules/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('schedule.delete')
def delete_schedule(id):
    schedule = Schedule.query.get_or_404(id)
    db.session.delete(schedule)
    db.session.commit()
    flash('Schedule deleted', 'success')
    return redirect(request.referrer or url_for('admin.schedules'))


# ==================== LEAVE MANAGEMENT ====================

@bp.route('/leave')
@login_required
@permission_required('leave.view_all')
def leave_requests():
    status = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)
    
    query = LeaveRequest.query
    if status != 'all':
        query = query.filter_by(status=status)
    
    requests = query.order_by(LeaveRequest.created_at.desc()).paginate(page=page, per_page=20)
    
    # Count by status
    counts = {
        'pending': LeaveRequest.query.filter_by(status='pending').count(),
        'approved': LeaveRequest.query.filter_by(status='approved').count(),
        'rejected': LeaveRequest.query.filter_by(status='rejected').count()
    }
    
    return render_template('admin/leave_requests.html', 
        requests=requests, 
        current_status=status,
        counts=counts
    )


@bp.route('/leave/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('leave.approve')
def approve_leave(id):
    leave_request = LeaveRequest.query.get_or_404(id)
    notes = request.form.get('notes', '')
    
    leave_request.status = 'approved'
    leave_request.reviewed_by = current_user.id
    leave_request.reviewed_at = datetime.utcnow()
    leave_request.review_notes = notes
    
    # Update leave balance
    allocation = LeaveAllocation.query.filter_by(
        user_id=leave_request.user_id,
        leave_type_id=leave_request.leave_type_id,
        year=leave_request.start_date.year
    ).first()
    
    if allocation:
        allocation.used_days += leave_request.days_count
    
    # Notify user
    notification = Notification(
        user_id=leave_request.user_id,
        title='Leave Request Approved',
        message=f'Your {leave_request.leave_type.name} request for '
               f'{leave_request.start_date.strftime("%d/%m/%Y")} to '
               f'{leave_request.end_date.strftime("%d/%m/%Y")} has been approved.',
        type='leave',
        is_popup=True,
        related_id=leave_request.id,
        related_type='leave_request'
    )
    db.session.add(notification)
    
    db.session.commit()
    flash('Leave request approved', 'success')
    return redirect(url_for('admin.leave_requests'))


@bp.route('/leave/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('leave.approve')
def reject_leave(id):
    leave_request = LeaveRequest.query.get_or_404(id)
    notes = request.form.get('notes', '')
    
    leave_request.status = 'rejected'
    leave_request.reviewed_by = current_user.id
    leave_request.reviewed_at = datetime.utcnow()
    leave_request.review_notes = notes
    
    # Notify user
    notification = Notification(
        user_id=leave_request.user_id,
        title='Leave Request Rejected',
        message=f'Your {leave_request.leave_type.name} request for '
               f'{leave_request.start_date.strftime("%d/%m/%Y")} to '
               f'{leave_request.end_date.strftime("%d/%m/%Y")} has been rejected.'
               + (f' Reason: {notes}' if notes else ''),
        type='leave',
        is_popup=True,
        related_id=leave_request.id,
        related_type='leave_request'
    )
    db.session.add(notification)
    
    db.session.commit()
    flash('Leave request rejected', 'success')
    return redirect(url_for('admin.leave_requests'))


@bp.route('/leave/allocations')
@login_required
@permission_required('leave.allocate')
def leave_allocations():
    year = request.args.get('year', date.today().year, type=int)
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    # Get all allocations for the year
    allocations = LeaveAllocation.query.filter_by(year=year).all()
    
    # Build allocation matrix
    alloc_dict = {}
    for a in allocations:
        key = (a.user_id, a.leave_type_id)
        alloc_dict[key] = a
    
    return render_template('admin/leave_allocations.html',
        users=users,
        leave_types=leave_types,
        alloc_dict=alloc_dict,
        year=year
    )


@bp.route('/leave/allocations/update', methods=['POST'])
@login_required
@permission_required('leave.allocate')
def update_allocation():
    user_id = request.form.get('user_id', type=int)
    leave_type_id = request.form.get('leave_type_id', type=int)
    year = request.form.get('year', type=int)
    allocated_days = request.form.get('allocated_days', type=float)
    
    allocation = LeaveAllocation.query.filter_by(
        user_id=user_id,
        leave_type_id=leave_type_id,
        year=year
    ).first()
    
    if allocation:
        allocation.allocated_days = allocated_days
    else:
        allocation = LeaveAllocation(
            user_id=user_id,
            leave_type_id=leave_type_id,
            year=year,
            allocated_days=allocated_days
        )
        db.session.add(allocation)
    
    db.session.commit()
    
    return jsonify({'success': True, 'allocated': allocated_days})
