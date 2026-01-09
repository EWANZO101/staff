"""
Board Blueprint
Public bulletin board for announcements, events, and operations info
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta

board_bp = Blueprint('board', __name__, url_prefix='/board')


@board_bp.route('/')
@login_required
def index():
    from app import BoardPost
    
    post_type_filter = request.args.get('type', 'all')
    
    query = BoardPost.query.filter_by(is_active=True)
    
    if post_type_filter != 'all':
        query = query.filter_by(post_type=post_type_filter)
    
    # Remove expired posts from view
    query = query.filter(
        (BoardPost.expires_at.is_(None)) | (BoardPost.expires_at > datetime.utcnow())
    )
    
    posts = query.order_by(
        BoardPost.is_pinned.desc(),
        BoardPost.priority.desc(),
        BoardPost.created_at.desc()
    ).all()
    
    can_manage = current_user.has_permission('manage_board')
    
    return render_template('board/index.html',
        posts=posts,
        can_manage=can_manage,
        post_type_filter=post_type_filter,
        today=date.today()
    )


@board_bp.route('/calendar')
@board_bp.route('/calendar/<int:year>/<int:month>')
@login_required
def calendar_view(year=None, month=None):
    from app import BoardPost
    import calendar as cal_module
    
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    # Get month boundaries
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    
    # Calendar setup
    cal = cal_module.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    # Get events for this month
    events = BoardPost.query.filter(
        BoardPost.is_active == True,
        BoardPost.event_date >= month_start,
        BoardPost.event_date <= month_end
    ).all()
    
    event_dict = {}
    for event in events:
        if event.event_date not in event_dict:
            event_dict[event.event_date] = []
        event_dict[event.event_date].append(event)
    
    # Navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    
    month_name = cal_module.month_name[month]
    
    can_manage = current_user.has_permission('manage_board')
    
    return render_template('board/calendar.html',
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        event_dict=event_dict,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        can_manage=can_manage
    )


@board_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    from app import db, BoardPost
    
    if not current_user.has_permission('manage_board'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('board.index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        post_type = request.form.get('post_type', 'announcement')
        priority = request.form.get('priority', 'normal')
        event_date_str = request.form.get('event_date')
        event_time_str = request.form.get('event_time')
        expires_at_str = request.form.get('expires_at')
        is_pinned = request.form.get('is_pinned') == 'on'
        
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('board.create'))
        
        event_date = None
        event_time = None
        expires_at = None
        
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        if event_time_str:
            try:
                event_time = datetime.strptime(event_time_str, '%H:%M').time()
            except ValueError:
                pass
        
        if expires_at_str:
            try:
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        post = BoardPost(
            title=title,
            content=content,
            post_type=post_type,
            priority=priority,
            event_date=event_date,
            event_time=event_time,
            expires_at=expires_at,
            is_pinned=is_pinned,
            created_by=current_user.id
        )
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully.', 'success')
        return redirect(url_for('board.index'))
    
    return render_template('board/create.html')


@board_bp.route('/<int:post_id>')
@login_required
def view(post_id):
    from app import BoardPost
    
    post = BoardPost.query.get_or_404(post_id)
    can_manage = current_user.has_permission('manage_board')
    
    return render_template('board/view.html', post=post, can_manage=can_manage)


@board_bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    from app import db, BoardPost
    
    if not current_user.has_permission('manage_board'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('board.index'))
    
    post = BoardPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        post.title = request.form.get('title', post.title).strip()
        post.content = request.form.get('content', post.content).strip()
        post.post_type = request.form.get('post_type', post.post_type)
        post.priority = request.form.get('priority', post.priority)
        post.is_pinned = request.form.get('is_pinned') == 'on'
        post.is_active = request.form.get('is_active') == 'on'
        
        event_date_str = request.form.get('event_date')
        event_time_str = request.form.get('event_time')
        expires_at_str = request.form.get('expires_at')
        
        if event_date_str:
            try:
                post.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            post.event_date = None
        
        if event_time_str:
            try:
                post.event_time = datetime.strptime(event_time_str, '%H:%M').time()
            except ValueError:
                pass
        else:
            post.event_time = None
        
        if expires_at_str:
            try:
                post.expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        else:
            post.expires_at = None
        
        db.session.commit()
        
        flash('Post updated successfully.', 'success')
        return redirect(url_for('board.view', post_id=post_id))
    
    return render_template('board/edit.html', post=post)


@board_bp.route('/<int:post_id>/toggle-pin', methods=['POST'])
@login_required
def toggle_pin(post_id):
    from app import db, BoardPost
    
    if not current_user.has_permission('manage_board'):
        return jsonify({'error': 'Permission denied'}), 403
    
    post = BoardPost.query.get_or_404(post_id)
    post.is_pinned = not post.is_pinned
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_pinned': post.is_pinned,
        'message': f'Post {"pinned" if post.is_pinned else "unpinned"}'
    })


@board_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    from app import db, BoardPost
    
    if not current_user.has_permission('manage_board'):
        return jsonify({'error': 'Permission denied'}), 403
    
    post = BoardPost.query.get_or_404(post_id)
    
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Post deleted'})
