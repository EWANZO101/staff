"""
Main Blueprint - User Dashboard and Schedule Views
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from calendar import monthrange
from app import db
from app.models import (
    Schedule, LeaveRequest, LeaveType, LeaveAllocation, 
    Unavailability, Notification, RestrictedDay, Task, BoardPost
)
from app.decorators import permission_required

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    # Get this week's schedule
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=4)  # Monday to Friday
    
    weekly_schedule = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= start_of_week,
        Schedule.date <= end_of_week
    ).order_by(Schedule.date).all()
    
    # Get pending leave requests
    pending_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'pending'
    ).all()
    
    # Get approved upcoming leave
    upcoming_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date >= today
    ).order_by(LeaveRequest.start_date).limit(5).all()
    
    # Get leave balance
    leave_allocations = LeaveAllocation.query.filter(
        LeaveAllocation.user_id == current_user.id,
        LeaveAllocation.year == current_year
    ).all()
    
    # Get assigned tasks
    pending_tasks = Task.query.filter(
        Task.assigned_to == current_user.id,
        Task.status.in_(['pending', 'in_progress'])
    ).order_by(Task.due_date).limit(5).all()
    
    # Get recent board posts
    recent_posts = BoardPost.query.filter(
        BoardPost.is_active == True
    ).order_by(BoardPost.is_pinned.desc(), BoardPost.created_at.desc()).limit(3).all()
    
    # Get unread notifications for popup
    unread_notifications = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
        Notification.is_popup == True
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark popup notifications as shown (but not read)
    for notif in unread_notifications:
        notif.is_popup = False
    db.session.commit()
    
    return render_template('main/dashboard.html',
        weekly_schedule=weekly_schedule,
        pending_leave=pending_leave,
        upcoming_leave=upcoming_leave,
        leave_allocations=leave_allocations,
        pending_tasks=pending_tasks,
        recent_posts=recent_posts,
        popup_notifications=unread_notifications,
        today=today
    )


@bp.route('/schedule')
@bp.route('/schedule/<int:year>/<int:month>')
@login_required
def schedule(year=None, month=None):
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    # Calculate first and last day of month
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    # Get all schedules for the month
    schedules = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= first_day,
        Schedule.date <= last_day
    ).all()
    
    # Get leave requests for the month
    leave_requests = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= last_day,
        LeaveRequest.end_date >= first_day
    ).all()
    
    # Get unavailability for the month
    unavailable_days = Unavailability.query.filter(
        Unavailability.user_id == current_user.id,
        Unavailability.date >= first_day,
        Unavailability.date <= last_day
    ).all()
    
    # Get restricted days
    restricted_days = RestrictedDay.query.filter(
        RestrictedDay.date >= first_day,
        RestrictedDay.date <= last_day
    ).all()
    
    # Build calendar data
    calendar_data = build_calendar_month(year, month, schedules, leave_requests, 
                                         unavailable_days, restricted_days)
    
    # Navigation
    prev_month = first_day - timedelta(days=1)
    next_month = last_day + timedelta(days=1)
    
    return render_template('main/schedule.html',
        calendar_data=calendar_data,
        year=year,
        month=month,
        month_name=first_day.strftime('%B'),
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month.year,
        next_month=next_month.month,
        today=today
    )


@bp.route('/leave')
@login_required
def leave():
    current_year = date.today().year
    
    # Get leave allocations
    allocations = LeaveAllocation.query.filter(
        LeaveAllocation.user_id == current_user.id,
        LeaveAllocation.year == current_year
    ).all()
    
    # Get all leave requests
    leave_requests = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id
    ).order_by(LeaveRequest.created_at.desc()).all()
    
    # Get leave types
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    return render_template('main/leave.html',
        allocations=allocations,
        leave_requests=leave_requests,
        leave_types=leave_types,
        current_year=current_year
    )


@bp.route('/leave/request', methods=['GET', 'POST'])
@login_required
def request_leave():
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        leave_type_id = request.form.get('leave_type_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')
        
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end < start:
                flash('End date cannot be before start date', 'error')
                return redirect(url_for('main.request_leave'))
            
            # Check for restricted days
            restricted = RestrictedDay.query.filter(
                RestrictedDay.date >= start,
                RestrictedDay.date <= end
            ).first()
            
            if restricted:
                flash(f'Your request includes a restricted day ({restricted.date.strftime("%d/%m/%Y")}). '
                      f'Reason: {restricted.reason}. This request will need special approval.', 'warning')
            
            leave_request = LeaveRequest(
                user_id=current_user.id,
                leave_type_id=leave_type_id,
                start_date=start,
                end_date=end,
                reason=reason
            )
            db.session.add(leave_request)
            db.session.commit()
            
            flash('Leave request submitted successfully', 'success')
            return redirect(url_for('main.leave'))
            
        except ValueError:
            flash('Invalid date format', 'error')
            return redirect(url_for('main.request_leave'))
    
    return render_template('main/request_leave.html', leave_types=leave_types)


@bp.route('/unavailability', methods=['GET', 'POST'])
@login_required
def unavailability():
    if request.method == 'POST':
        date_str = request.form.get('date')
        reason = request.form.get('reason')
        
        try:
            unavail_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Check if already exists
            existing = Unavailability.query.filter_by(
                user_id=current_user.id,
                date=unavail_date
            ).first()
            
            if existing:
                flash('You have already marked this day as unavailable', 'warning')
            else:
                unavail = Unavailability(
                    user_id=current_user.id,
                    date=unavail_date,
                    reason=reason
                )
                db.session.add(unavail)
                db.session.commit()
                flash('Unavailability recorded', 'success')
                
        except ValueError:
            flash('Invalid date format', 'error')
    
    # Get all unavailability records
    unavailable_days = Unavailability.query.filter(
        Unavailability.user_id == current_user.id
    ).order_by(Unavailability.date.desc()).all()
    
    return render_template('main/unavailability.html', unavailable_days=unavailable_days)


@bp.route('/unavailability/delete/<int:id>', methods=['POST'])
@login_required
def delete_unavailability(id):
    unavail = Unavailability.query.get_or_404(id)
    if unavail.user_id != current_user.id:
        flash('Unauthorized action', 'error')
        return redirect(url_for('main.unavailability'))
    
    db.session.delete(unavail)
    db.session.commit()
    flash('Unavailability record deleted', 'success')
    return redirect(url_for('main.unavailability'))


@bp.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('main/notifications.html', notifications=notifications)


@bp.route('/notifications/read/<int:id>', methods=['POST'])
@login_required
def mark_notification_read(id):
    notification = Notification.query.get_or_404(id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read', 'success')
    return redirect(url_for('main.notifications'))


def build_calendar_month(year, month, schedules, leave_requests, unavailable_days, restricted_days):
    """Build calendar data structure for a month"""
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    # Create lookup dictionaries
    schedule_dict = {s.date: s for s in schedules}
    unavail_dict = {u.date: u for u in unavailable_days}
    restricted_dict = {r.date: r for r in restricted_days}
    
    # Build leave date set
    leave_dates = {}
    for lr in leave_requests:
        current = lr.start_date
        while current <= lr.end_date:
            if current.month == month and current.year == year:
                leave_dates[current] = lr
            current += timedelta(days=1)
    
    # Build weeks
    weeks = []
    current_week = []
    
    # Add empty days for start of month
    for i in range(first_day.weekday()):
        current_week.append(None)
    
    # Add days of month
    current = first_day
    while current <= last_day:
        day_data = {
            'date': current,
            'day': current.day,
            'is_weekend': current.weekday() >= 5,
            'is_today': current == date.today(),
            'schedule': schedule_dict.get(current),
            'leave': leave_dates.get(current),
            'unavailable': unavail_dict.get(current),
            'restricted': restricted_dict.get(current)
        }
        current_week.append(day_data)
        
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        
        current += timedelta(days=1)
    
    # Add empty days for end of month
    while len(current_week) > 0 and len(current_week) < 7:
        current_week.append(None)
    if current_week:
        weeks.append(current_week)
    
    return weeks
