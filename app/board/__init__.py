"""
Board Blueprint - Public Board for Announcements and Events
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models import BoardPost, Notification, User
from app.decorators import permission_required

bp = Blueprint('board', __name__)

POST_TYPES = [
    ('announcement', 'Announcement', '📢'),
    ('event', 'Event', '📅'),
    ('task_needed', 'Help Needed', '🙋'),
    ('operational', 'Operational Info', '⚙️'),
    ('reminder', 'Reminder', '🔔'),
    ('celebration', 'Celebration', '🎉')
]

PRIORITIES = [
    ('low', 'Low', 'text-gray-400'),
    ('normal', 'Normal', 'text-blue-400'),
    ('high', 'High', 'text-yellow-400'),
    ('urgent', 'Urgent', 'text-red-400')
]


@bp.route('/')
@login_required
@permission_required('board.view')
def index():
    post_type = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = BoardPost.query.filter_by(is_active=True)
    
    # Filter expired posts
    query = query.filter(
        (BoardPost.expires_at == None) | (BoardPost.expires_at > datetime.utcnow())
    )
    
    if post_type != 'all':
        query = query.filter_by(post_type=post_type)
    
    posts = query.order_by(
        BoardPost.is_pinned.desc(),
        BoardPost.priority.desc(),
        BoardPost.created_at.desc()
    ).paginate(page=page, per_page=15)
    
    # Get upcoming events
    upcoming_events = BoardPost.query.filter(
        BoardPost.is_active == True,
        BoardPost.post_type == 'event',
        BoardPost.event_date >= date.today()
    ).order_by(BoardPost.event_date).limit(5).all()
    
    return render_template('board/index.html',
        posts=posts,
        post_types=POST_TYPES,
        current_type=post_type,
        upcoming_events=upcoming_events
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('board.create')
def create():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        post_type = request.form.get('post_type', 'announcement')
        priority = request.form.get('priority', 'normal')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        expires_at = request.form.get('expires_at')
        is_pinned = 'is_pinned' in request.form
        notify_all = 'notify_all' in request.form
        
        post = BoardPost(
            title=title,
            content=content,
            post_type=post_type,
            priority=priority,
            is_pinned=is_pinned,
            created_by=current_user.id
        )
        
        if event_date:
            post.event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
        if event_time:
            post.event_time = datetime.strptime(event_time, '%H:%M').time()
        if expires_at:
            post.expires_at = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M')
        
        db.session.add(post)
        db.session.flush()
        
        # Notify all users if requested
        if notify_all:
            users = User.query.filter_by(is_active=True).all()
            type_label = dict((t[0], t[1]) for t in POST_TYPES).get(post_type, 'Post')
            
            for user in users:
                if user.id != current_user.id:
                    notification = Notification(
                        user_id=user.id,
                        title=f'New {type_label}: {title}',
                        message=content[:200] + '...' if len(content) > 200 else content,
                        type='info',
                        is_popup=priority in ['high', 'urgent'],
                        related_id=post.id,
                        related_type='board_post'
                    )
                    db.session.add(notification)
        
        db.session.commit()
        flash('Post created successfully', 'success')
        return redirect(url_for('board.index'))
    
    return render_template('board/create.html', 
        post_types=POST_TYPES,
        priorities=PRIORITIES
    )


@bp.route('/<int:id>')
@login_required
@permission_required('board.view')
def view(id):
    post = BoardPost.query.get_or_404(id)
    return render_template('board/view.html', post=post, post_types=POST_TYPES)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('board.edit')
def edit(id):
    post = BoardPost.query.get_or_404(id)
    
    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        post.post_type = request.form.get('post_type', 'announcement')
        post.priority = request.form.get('priority', 'normal')
        post.is_pinned = 'is_pinned' in request.form
        post.is_active = 'is_active' in request.form
        
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')
        expires_at = request.form.get('expires_at')
        
        post.event_date = datetime.strptime(event_date, '%Y-%m-%d').date() if event_date else None
        post.event_time = datetime.strptime(event_time, '%H:%M').time() if event_time else None
        post.expires_at = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M') if expires_at else None
        
        db.session.commit()
        flash('Post updated successfully', 'success')
        return redirect(url_for('board.view', id=post.id))
    
    return render_template('board/edit.html', 
        post=post,
        post_types=POST_TYPES,
        priorities=PRIORITIES
    )


@bp.route('/<int:id>/pin', methods=['POST'])
@login_required
@permission_required('board.pin')
def toggle_pin(id):
    post = BoardPost.query.get_or_404(id)
    post.is_pinned = not post.is_pinned
    db.session.commit()
    
    status = 'pinned' if post.is_pinned else 'unpinned'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'pinned': post.is_pinned})
    
    flash(f'Post {status}', 'success')
    return redirect(url_for('board.index'))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('board.delete')
def delete(id):
    post = BoardPost.query.get_or_404(id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted', 'success')
    return redirect(url_for('board.index'))


@bp.route('/events')
@login_required
@permission_required('board.view')
def events():
    """Calendar view of events"""
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)
    
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    events = BoardPost.query.filter(
        BoardPost.is_active == True,
        BoardPost.post_type == 'event',
        BoardPost.event_date >= first_day,
        BoardPost.event_date <= last_day
    ).order_by(BoardPost.event_date).all()
    
    # Group by date
    events_by_date = {}
    for event in events:
        if event.event_date not in events_by_date:
            events_by_date[event.event_date] = []
        events_by_date[event.event_date].append(event)
    
    # Build calendar
    from datetime import timedelta
    
    weeks = []
    current_week = []
    
    # Add empty days for start of month
    for i in range(first_day.weekday()):
        current_week.append(None)
    
    current = first_day
    while current <= last_day:
        day_data = {
            'date': current,
            'day': current.day,
            'is_today': current == date.today(),
            'events': events_by_date.get(current, [])
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
    
    # Navigation
    prev_month = first_day - timedelta(days=1)
    next_month = last_day + timedelta(days=1)
    
    return render_template('board/events.html',
        weeks=weeks,
        year=year,
        month=month,
        month_name=first_day.strftime('%B'),
        prev_year=prev_month.year,
        prev_month=prev_month.month,
        next_year=next_month.year,
        next_month=next_month.month
    )
