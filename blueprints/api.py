"""
API Blueprint
AJAX endpoints for notifications, dynamic updates, and data retrieval
"""

from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user
from datetime import datetime, date

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/notifications')
@login_required
def get_notifications():
    from app import Notification
    
    unread_only = request.args.get('unread', 'true') == 'true'
    limit = request.args.get('limit', 10, type=int)
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'is_popup': n.is_popup,
            'created_at': n.created_at.strftime('%d/%m/%Y %H:%M'),
            'reference_id': n.reference_id,
            'reference_type': n.reference_type
        } for n in notifications],
        'unread_count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    })


@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    from app import db, Notification
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first_or_404()
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})


@api_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    from app import db, Notification
    
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({'success': True})


@api_bp.route('/notifications/popup')
@login_required
def get_popup_notifications():
    """Get notifications that should be shown as popups"""
    from app import Notification
    
    # Check for login notifications in session
    login_notification_ids = session.pop('login_notifications', [])
    
    notifications = []
    
    if login_notification_ids:
        login_notifications = Notification.query.filter(
            Notification.id.in_(login_notification_ids)
        ).all()
        notifications.extend(login_notifications)
    
    # Also get any recent unread popup notifications
    recent_popups = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
        Notification.is_popup == True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    # Combine, removing duplicates
    seen_ids = set()
    unique_notifications = []
    for n in notifications + recent_popups:
        if n.id not in seen_ids:
            seen_ids.add(n.id)
            unique_notifications.append(n)
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'created_at': n.created_at.strftime('%d/%m/%Y %H:%M')
        } for n in unique_notifications[:5]]
    })


@api_bp.route('/notifications/dismiss/<int:notification_id>', methods=['POST'])
@login_required
def dismiss_notification(notification_id):
    from app import db, Notification
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()
    
    if notification:
        notification.is_popup = False
        notification.is_read = True
        db.session.commit()
    
    return jsonify({'success': True})


@api_bp.route('/unread-count')
@login_required
def get_unread_count():
    from app import Notification
    
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})


@api_bp.route('/schedule/<int:year>/<int:month>')
@login_required
def get_user_schedule(year, month):
    from app import Schedule, LeaveRequest
    from datetime import timedelta
    
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
    
    leave_requests = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.start_date <= month_end,
        LeaveRequest.end_date >= month_start
    ).all()
    
    return jsonify({
        'schedules': [{
            'date': s.date.strftime('%Y-%m-%d'),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M'),
            'notes': s.notes
        } for s in schedules],
        'leave': [{
            'id': l.id,
            'start_date': l.start_date.strftime('%Y-%m-%d'),
            'end_date': l.end_date.strftime('%Y-%m-%d'),
            'type': l.leave_type.name,
            'status': l.status
        } for l in leave_requests]
    })


@api_bp.route('/users')
@login_required
def get_users():
    from app import User
    
    if not current_user.has_any_permission(['manage_users', 'manage_schedules', 'manage_tasks']):
        return jsonify({'error': 'Permission denied'}), 403
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    
    return jsonify({
        'users': [{
            'id': u.id,
            'name': u.full_name,
            'email': u.email
        } for u in users]
    })


@api_bp.route('/leave-balance')
@login_required
def get_leave_balance():
    from app import LeaveAllowance
    
    year = request.args.get('year', date.today().year, type=int)
    
    allowances = LeaveAllowance.query.filter_by(
        user_id=current_user.id,
        year=year
    ).all()
    
    return jsonify({
        'balances': [{
            'type': a.leave_type.name,
            'total': a.total_days,
            'used': a.used_days,
            'remaining': a.remaining_days,
            'color': a.leave_type.color
        } for a in allowances]
    })


@api_bp.route('/dashboard-stats')
@login_required
def get_dashboard_stats():
    from app import Schedule, LeaveRequest, TaskAssignment, Notification
    from datetime import timedelta
    
    today = date.today()
    week_end = today + timedelta(days=7)
    
    # This week's shifts
    upcoming_shifts = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= today,
        Schedule.date <= week_end
    ).count()
    
    # Pending leave
    pending_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'pending'
    ).count()
    
    # Active tasks
    active_tasks = TaskAssignment.query.filter(
        TaskAssignment.user_id == current_user.id,
        TaskAssignment.status != 'completed'
    ).count()
    
    # Unread notifications
    unread = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'upcoming_shifts': upcoming_shifts,
        'pending_leave': pending_leave,
        'active_tasks': active_tasks,
        'unread_notifications': unread
    })


@api_bp.route('/board/upcoming')
@login_required
def get_upcoming_events():
    from app import BoardPost
    from datetime import timedelta
    
    today = date.today()
    next_month = today + timedelta(days=30)
    
    events = BoardPost.query.filter(
        BoardPost.is_active == True,
        BoardPost.event_date >= today,
        BoardPost.event_date <= next_month
    ).order_by(BoardPost.event_date).limit(10).all()
    
    return jsonify({
        'events': [{
            'id': e.id,
            'title': e.title,
            'date': e.event_date.strftime('%d/%m/%Y') if e.event_date else None,
            'time': e.event_time.strftime('%H:%M') if e.event_time else None,
            'type': e.post_type,
            'priority': e.priority
        } for e in events]
    })
