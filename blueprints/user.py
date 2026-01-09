"""
User Blueprint
Dashboard, schedule viewing, leave requests, and user-facing features
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/dashboard')
@login_required
def dashboard():
    from app import db, Schedule, LeaveRequest, LeaveAllowance, Task, TaskAssignment, Notification, BoardPost
    
    today = date.today()
    current_month_start = today.replace(day=1)
    
    # Get next month's last day for schedule range
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    
    # This week's schedule
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    weekly_schedule = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= week_start,
        Schedule.date <= week_end
    ).order_by(Schedule.date).all()
    
    # Upcoming schedules (next 14 days)
    upcoming_schedules = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= today,
        Schedule.date <= today + timedelta(days=14)
    ).order_by(Schedule.date).all()
    
    # Pending leave requests
    pending_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'pending'
    ).order_by(LeaveRequest.created_at.desc()).all()
    
    # Approved upcoming leave
    approved_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'approved',
        LeaveRequest.end_date >= today
    ).order_by(LeaveRequest.start_date).all()
    
    # Leave balances
    current_year = today.year
    leave_balances = LeaveAllowance.query.filter_by(
        user_id=current_user.id,
        year=current_year
    ).all()
    
    # My tasks
    my_tasks = TaskAssignment.query.filter(
        TaskAssignment.user_id == current_user.id,
        TaskAssignment.status != 'completed'
    ).join(Task).order_by(Task.due_date).limit(5).all()
    
    # Recent board posts
    board_posts = BoardPost.query.filter(
        BoardPost.is_active == True
    ).order_by(BoardPost.is_pinned.desc(), BoardPost.created_at.desc()).limit(5).all()
    
    # Unread notifications count
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return render_template('user/dashboard.html',
        weekly_schedule=weekly_schedule,
        upcoming_schedules=upcoming_schedules,
        pending_leave=pending_leave,
        approved_leave=approved_leave,
        leave_balances=leave_balances,
        my_tasks=my_tasks,
        board_posts=board_posts,
        unread_count=unread_count,
        today=today,
        week_start=week_start,
        week_end=week_end
    )


@user_bp.route('/schedule')
@user_bp.route('/schedule/<int:year>/<int:month>')
@login_required
def schedule(year=None, month=None):
    from app import Schedule, LeaveRequest, RestrictedDay
    
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    # Get calendar data
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(year, month)
    
    # Get schedules for this month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    
    schedules = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= month_start,
        Schedule.date <= month_end
    ).all()
    schedule_dict = {s.date: s for s in schedules}
    
    # Get leave for this month
    leave_requests = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.start_date <= month_end,
        LeaveRequest.end_date >= month_start
    ).all()
    
    leave_dict = {}
    for leave in leave_requests:
        current_date = max(leave.start_date, month_start)
        end_date = min(leave.end_date, month_end)
        while current_date <= end_date:
            leave_dict[current_date] = leave
            current_date += timedelta(days=1)
    
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
    
    return render_template('user/schedule.html',
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        schedule_dict=schedule_dict,
        leave_dict=leave_dict,
        restricted_dict=restricted_dict,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )


@user_bp.route('/leave')
@login_required
def leave():
    from app import LeaveRequest, LeaveAllowance, LeaveType
    
    today = date.today()
    current_year = today.year
    
    # Get all leave requests
    leave_requests = LeaveRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(LeaveRequest.created_at.desc()).all()
    
    # Get leave balances
    leave_balances = LeaveAllowance.query.filter_by(
        user_id=current_user.id,
        year=current_year
    ).all()
    
    # Get leave types for request form
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    return render_template('user/leave.html',
        leave_requests=leave_requests,
        leave_balances=leave_balances,
        leave_types=leave_types,
        current_year=current_year,
        today=today
    )


@user_bp.route('/leave/request', methods=['POST'])
@login_required
def request_leave():
    from app import db, LeaveRequest, LeaveType, LeaveAllowance, RestrictedDay, create_notification, User
    
    leave_type_id = request.form.get('leave_type_id')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    reason = request.form.get('reason', '').strip()
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date format.', 'danger')
        return redirect(url_for('user.leave'))
    
    if end_date < start_date:
        flash('End date cannot be before start date.', 'danger')
        return redirect(url_for('user.leave'))
    
    leave_type = LeaveType.query.get(leave_type_id)
    if not leave_type or not leave_type.is_active:
        flash('Invalid leave type.', 'danger')
        return redirect(url_for('user.leave'))
    
    # Check for restricted days
    current_date = start_date
    restricted_days = []
    while current_date <= end_date:
        restricted = RestrictedDay.query.filter_by(date=current_date).first()
        if restricted:
            restricted_days.append(current_date)
        current_date += timedelta(days=1)
    
    # Calculate days requested (excluding weekends)
    days_requested = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            days_requested += 1
        current_date += timedelta(days=1)
    
    # Check leave balance
    current_year = start_date.year
    allowance = LeaveAllowance.query.filter_by(
        user_id=current_user.id,
        leave_type_id=leave_type_id,
        year=current_year
    ).first()
    
    if allowance and days_requested > allowance.remaining_days:
        flash(f'Insufficient leave balance. You have {allowance.remaining_days} days remaining.', 'warning')
    
    # Create leave request
    leave_request = LeaveRequest(
        user_id=current_user.id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason
    )
    
    if restricted_days:
        leave_request.reason += f" [Contains restricted days: {', '.join(d.strftime('%d/%m/%Y') for d in restricted_days)}]"
    
    db.session.add(leave_request)
    db.session.commit()
    
    # Notify admins
    admins = User.query.filter(User.is_first_user == True).all()
    for admin in admins:
        create_notification(
            user_id=admin.id,
            title='New Leave Request',
            message=f'{current_user.full_name} requested {leave_type.name} from {start_date.strftime("%d/%m/%Y")} to {end_date.strftime("%d/%m/%Y")}',
            notification_type='leave',
            reference_id=leave_request.id,
            reference_type='leave_request'
        )
    
    flash('Leave request submitted successfully.', 'success')
    return redirect(url_for('user.leave'))


@user_bp.route('/leave/cancel/<int:leave_id>', methods=['POST'])
@login_required
def cancel_leave(leave_id):
    from app import db, LeaveRequest
    
    leave_request = LeaveRequest.query.get_or_404(leave_id)
    
    if leave_request.user_id != current_user.id:
        flash('You can only cancel your own leave requests.', 'danger')
        return redirect(url_for('user.leave'))
    
    if leave_request.status != 'pending':
        flash('Only pending requests can be cancelled.', 'warning')
        return redirect(url_for('user.leave'))
    
    db.session.delete(leave_request)
    db.session.commit()
    
    flash('Leave request cancelled.', 'success')
    return redirect(url_for('user.leave'))


@user_bp.route('/notifications')
@login_required
def notifications():
    from app import Notification
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    return render_template('user/notifications.html', notifications=notifications)


@user_bp.route('/profile')
@login_required
def profile():
    from app import LeaveAllowance
    
    current_year = date.today().year
    leave_balances = LeaveAllowance.query.filter_by(
        user_id=current_user.id,
        year=current_year
    ).all()
    
    return render_template('user/profile.html', leave_balances=leave_balances)


@user_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    from app import db, bcrypt
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if first_name:
        current_user.first_name = first_name
    if last_name:
        current_user.last_name = last_name
    
    # Password change
    if new_password:
        if not bcrypt.check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('user.profile'))
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters.', 'danger')
            return redirect(url_for('user.profile'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('user.profile'))
        
        current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        flash('Password updated successfully.', 'success')
    
    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('user.profile'))
