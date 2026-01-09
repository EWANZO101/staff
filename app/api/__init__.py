"""
API Blueprint - JSON endpoints for AJAX calls
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app import db
from app.models import (
    Notification, Schedule, Task, LeaveRequest, 
    User, BoardPost
)

bp = Blueprint('api', __name__)


# ==================== NOTIFICATIONS ====================

@bp.route('/notifications')
@login_required
def get_notifications():
    """Get user's notifications"""
    unread_only = request.args.get('unread', 'false') == 'true'
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
            'type': n.type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'related_type': n.related_type,
            'related_id': n.related_id
        } for n in notifications],
        'unread_count': current_user.get_unread_notifications_count()
    })


@bp.route('/notifications/popup')
@login_required
def get_popup_notifications():
    """Get notifications that should be shown as popups"""
    notifications = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
        Notification.is_popup == True
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark as shown (not read)
    for n in notifications:
        n.is_popup = False
    db.session.commit()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.type,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    })


@bp.route('/notifications/<int:id>/read', methods=['POST'])
@login_required
def mark_read(id):
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
    
    return jsonify({'success': True})


# ==================== SCHEDULE ====================

@bp.route('/schedule/week')
@login_required
def get_week_schedule():
    """Get current week's schedule for user"""
    user_id = request.args.get('user_id', current_user.id, type=int)
    
    # Check permission for viewing other users
    if user_id != current_user.id and not current_user.has_permission('schedule.view_all'):
        return jsonify({'error': 'Permission denied'}), 403
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=4)
    
    schedules = Schedule.query.filter(
        Schedule.user_id == user_id,
        Schedule.date >= start_of_week,
        Schedule.date <= end_of_week
    ).order_by(Schedule.date).all()
    
    return jsonify({
        'schedules': [{
            'id': s.id,
            'date': s.date.strftime('%d/%m/%Y'),
            'day_name': s.date.strftime('%A'),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M'),
            'notes': s.notes
        } for s in schedules]
    })


@bp.route('/schedule/month')
@login_required
def get_month_schedule():
    """Get month's schedule data"""
    user_id = request.args.get('user_id', current_user.id, type=int)
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)
    
    if user_id != current_user.id and not current_user.has_permission('schedule.view_all'):
        return jsonify({'error': 'Permission denied'}), 403
    
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    schedules = Schedule.query.filter(
        Schedule.user_id == user_id,
        Schedule.date >= first_day,
        Schedule.date <= last_day
    ).all()
    
    return jsonify({
        'schedules': [{
            'id': s.id,
            'date': s.date.isoformat(),
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time': s.end_time.strftime('%H:%M')
        } for s in schedules]
    })


# ==================== TASKS ====================

@bp.route('/tasks/summary')
@login_required
def tasks_summary():
    """Get task summary for dashboard"""
    tasks = Task.query.filter(
        Task.assigned_to == current_user.id,
        Task.status.in_(['pending', 'in_progress'])
    ).order_by(Task.due_date.asc().nullslast()).limit(5).all()
    
    return jsonify({
        'tasks': [{
            'id': t.id,
            'title': t.title,
            'priority': t.priority,
            'status': t.status,
            'due_date': t.due_date.strftime('%d/%m/%Y') if t.due_date else None,
            'is_overdue': t.is_overdue
        } for t in tasks],
        'pending_count': Task.query.filter_by(
            assigned_to=current_user.id, 
            status='pending'
        ).count()
    })


@bp.route('/tasks/<int:id>/status', methods=['POST'])
@login_required
def update_task_status(id):
    task = Task.query.get_or_404(id)
    
    if task.assigned_to != current_user.id and not current_user.has_permission('tasks.edit'):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    
    if new_status not in ['pending', 'in_progress', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400
    
    task.status = new_status
    if new_status == 'completed':
        task.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'status': new_status})


# ==================== LEAVE ====================

@bp.route('/leave/balance')
@login_required
def leave_balance():
    """Get user's leave balance"""
    from app.models import LeaveAllocation
    
    year = request.args.get('year', date.today().year, type=int)
    
    allocations = LeaveAllocation.query.filter(
        LeaveAllocation.user_id == current_user.id,
        LeaveAllocation.year == year
    ).all()
    
    return jsonify({
        'allocations': [{
            'leave_type': a.leave_type.name,
            'allocated': a.allocated_days,
            'used': a.used_days,
            'remaining': a.remaining_days,
            'color': a.leave_type.color
        } for a in allocations]
    })


@bp.route('/leave/pending-count')
@login_required
def pending_leave_count():
    """Get count of pending leave requests (for admin badge)"""
    if not current_user.has_permission('leave.approve'):
        return jsonify({'count': 0})
    
    count = LeaveRequest.query.filter_by(status='pending').count()
    return jsonify({'count': count})


# ==================== USERS ====================

@bp.route('/users/search')
@login_required
def search_users():
    """Search users for autocomplete"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if len(query) < 2:
        return jsonify({'users': []})
    
    users = User.query.filter(
        User.is_active == True,
        (User.first_name.ilike(f'%{query}%')) |
        (User.last_name.ilike(f'%{query}%')) |
        (User.email.ilike(f'%{query}%'))
    ).limit(limit).all()
    
    return jsonify({
        'users': [{
            'id': u.id,
            'name': u.full_name,
            'email': u.email,
            'department': u.department
        } for u in users]
    })


# ==================== BOARD ====================

@bp.route('/board/recent')
@login_required
def recent_posts():
    """Get recent board posts"""
    limit = request.args.get('limit', 5, type=int)
    
    posts = BoardPost.query.filter(
        BoardPost.is_active == True,
        (BoardPost.expires_at == None) | (BoardPost.expires_at > datetime.utcnow())
    ).order_by(
        BoardPost.is_pinned.desc(),
        BoardPost.created_at.desc()
    ).limit(limit).all()
    
    return jsonify({
        'posts': [{
            'id': p.id,
            'title': p.title,
            'type': p.post_type,
            'priority': p.priority,
            'is_pinned': p.is_pinned,
            'created_at': p.created_at.isoformat(),
            'author': p.author.full_name if p.author else 'System'
        } for p in posts]
    })


@bp.route('/board/events/upcoming')
@login_required
def upcoming_events():
    """Get upcoming events"""
    limit = request.args.get('limit', 5, type=int)
    
    events = BoardPost.query.filter(
        BoardPost.is_active == True,
        BoardPost.post_type == 'event',
        BoardPost.event_date >= date.today()
    ).order_by(BoardPost.event_date).limit(limit).all()
    
    return jsonify({
        'events': [{
            'id': e.id,
            'title': e.title,
            'date': e.event_date.strftime('%d/%m/%Y'),
            'time': e.event_time.strftime('%H:%M') if e.event_time else None,
            'priority': e.priority
        } for e in events]
    })


# ==================== DASHBOARD STATS ====================

@bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    """Get dashboard statistics"""
    today = date.today()
    
    # User's upcoming shifts this week
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    shifts_this_week = Schedule.query.filter(
        Schedule.user_id == current_user.id,
        Schedule.date >= today,
        Schedule.date <= end_of_week
    ).count()
    
    # Pending tasks
    pending_tasks = Task.query.filter(
        Task.assigned_to == current_user.id,
        Task.status.in_(['pending', 'in_progress'])
    ).count()
    
    # Pending leave requests
    pending_leave = LeaveRequest.query.filter(
        LeaveRequest.user_id == current_user.id,
        LeaveRequest.status == 'pending'
    ).count()
    
    # Unread notifications
    unread_notifications = current_user.get_unread_notifications_count()
    
    return jsonify({
        'shifts_this_week': shifts_this_week,
        'pending_tasks': pending_tasks,
        'pending_leave': pending_leave,
        'unread_notifications': unread_notifications
    })
