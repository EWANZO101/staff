"""
Tasks Blueprint - Task Assignment and Management
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models import Task, User, Notification
from app.decorators import permission_required

bp = Blueprint('tasks', __name__)


@bp.route('/')
@login_required
def index():
    """View tasks - shows own tasks for regular users, all for admins"""
    status = request.args.get('status', 'all')
    priority = request.args.get('priority', 'all')
    page = request.args.get('page', 1, type=int)
    
    # Check if user can view all tasks
    if current_user.has_permission('tasks.view_all'):
        query = Task.query
        view_all = True
    else:
        query = Task.query.filter_by(assigned_to=current_user.id)
        view_all = False
    
    # Apply filters
    if status != 'all':
        query = query.filter_by(status=status)
    if priority != 'all':
        query = query.filter_by(priority=priority)
    
    tasks = query.order_by(
        Task.priority.desc(),
        db.case((Task.due_date.is_(None), 1), else_=0),
        Task.due_date.asc(),
        Task.created_at.desc()
    ).paginate(page=page, per_page=20)
    
    # Count by status
    base_query = Task.query if view_all else Task.query.filter_by(assigned_to=current_user.id)
    counts = {
        'all': base_query.count(),
        'pending': base_query.filter_by(status='pending').count(),
        'in_progress': base_query.filter_by(status='in_progress').count(),
        'completed': base_query.filter_by(status='completed').count()
    }
    
    return render_template('tasks/index.html',
        tasks=tasks,
        current_status=status,
        current_priority=priority,
        counts=counts,
        view_all=view_all
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('tasks.create')
def create():
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        assigned_to = request.form.get('assigned_to')
        due_date = request.form.get('due_date')
        due_time = request.form.get('due_time')
        priority = request.form.get('priority', 'medium')
        category = request.form.get('category')
        
        task = Task(
            title=title,
            description=description,
            assigned_to=assigned_to if assigned_to else None,
            assigned_by=current_user.id,
            priority=priority,
            category=category
        )
        
        if due_date:
            task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        if due_time:
            task.due_time = datetime.strptime(due_time, '%H:%M').time()
        
        db.session.add(task)
        db.session.flush()
        
        # Notify assignee
        if assigned_to:
            notification = Notification(
                user_id=assigned_to,
                title='New Task Assigned',
                message=f'You have been assigned a new task: {title}',
                type='task',
                is_popup=True,
                related_id=task.id,
                related_type='task'
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('Task created successfully', 'success')
        return redirect(url_for('tasks.index'))
    
    return render_template('tasks/create.html', users=users)


@bp.route('/<int:id>')
@login_required
def view(id):
    task = Task.query.get_or_404(id)
    
    # Check permission
    if not current_user.has_permission('tasks.view_all'):
        if task.assigned_to != current_user.id:
            flash('You do not have permission to view this task', 'error')
            return redirect(url_for('tasks.index'))
    
    return render_template('tasks/view.html', task=task)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('tasks.edit')
def edit(id):
    task = Task.query.get_or_404(id)
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    
    if request.method == 'POST':
        old_assignee = task.assigned_to
        
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        task.assigned_to = request.form.get('assigned_to') or None
        task.priority = request.form.get('priority', 'medium')
        task.category = request.form.get('category')
        task.status = request.form.get('status', task.status)
        
        due_date = request.form.get('due_date')
        due_time = request.form.get('due_time')
        
        task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        task.due_time = datetime.strptime(due_time, '%H:%M').time() if due_time else None
        
        if task.status == 'completed' and not task.completed_at:
            task.completed_at = datetime.utcnow()
        
        # Notify if assignee changed
        if task.assigned_to and task.assigned_to != old_assignee:
            notification = Notification(
                user_id=task.assigned_to,
                title='Task Assigned to You',
                message=f'You have been assigned the task: {task.title}',
                type='task',
                is_popup=True,
                related_id=task.id,
                related_type='task'
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('Task updated successfully', 'success')
        return redirect(url_for('tasks.view', id=task.id))
    
    return render_template('tasks/edit.html', task=task, users=users)


@bp.route('/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    task = Task.query.get_or_404(id)
    
    # Check permission - assignee can update their own task status
    if task.assigned_to != current_user.id and not current_user.has_permission('tasks.edit'):
        return jsonify({'error': 'Permission denied'}), 403
    
    new_status = request.form.get('status')
    if new_status not in ['pending', 'in_progress', 'completed', 'cancelled']:
        return jsonify({'error': 'Invalid status'}), 400
    
    task.status = new_status
    if new_status == 'completed':
        task.completed_at = datetime.utcnow()
    
    # Notify assigner if completed
    if new_status == 'completed' and task.assigned_by:
        notification = Notification(
            user_id=task.assigned_by,
            title='Task Completed',
            message=f'Task "{task.title}" has been marked as completed by {current_user.full_name}',
            type='task',
            is_popup=True,
            related_id=task.id,
            related_type='task'
        )
        db.session.add(notification)
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': new_status})
    
    flash(f'Task status updated to {new_status}', 'success')
    return redirect(url_for('tasks.view', id=task.id))


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('tasks.delete')
def delete(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted', 'success')
    return redirect(url_for('tasks.index'))


@bp.route('/my-tasks')
@login_required
def my_tasks():
    """Quick view of current user's tasks"""
    status = request.args.get('status', 'active')
    
    query = Task.query.filter_by(assigned_to=current_user.id)
    
    if status == 'active':
        query = query.filter(Task.status.in_(['pending', 'in_progress']))
    elif status != 'all':
        query = query.filter_by(status=status)
    
    tasks = query.order_by(
        Task.priority.desc(),
        db.case((Task.due_date.is_(None), 1), else_=0),
        Task.due_date.asc()
    ).all()
    
    return render_template('tasks/my_tasks.html', tasks=tasks, current_status=status)
