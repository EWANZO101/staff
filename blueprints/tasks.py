"""
Tasks Blueprint
Task creation, assignment, and management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@tasks_bp.route('/')
@login_required
def index():
    from app import Task, TaskAssignment, User
    
    # Check permissions
    can_manage = current_user.has_permission('manage_tasks')
    can_view_all = current_user.has_permission('view_all_tasks')
    
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    
    if can_view_all or can_manage:
        # Show all tasks
        query = Task.query
    else:
        # Show only assigned tasks
        assigned_task_ids = [a.task_id for a in TaskAssignment.query.filter_by(user_id=current_user.id).all()]
        query = Task.query.filter(Task.id.in_(assigned_task_ids))
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if priority_filter != 'all':
        query = query.filter_by(priority=priority_filter)
    
    tasks = query.order_by(
        Task.status != 'completed',
        Task.priority.desc(),
        Task.due_date
    ).all()
    
    # Get users for assignment
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all() if can_manage else []
    
    return render_template('tasks/index.html',
        tasks=tasks,
        users=users,
        can_manage=can_manage,
        status_filter=status_filter,
        priority_filter=priority_filter
    )


@tasks_bp.route('/my')
@login_required
def my_tasks():
    from app import Task, TaskAssignment
    
    status_filter = request.args.get('status', 'active')
    
    query = TaskAssignment.query.filter_by(user_id=current_user.id)
    
    if status_filter == 'active':
        query = query.filter(TaskAssignment.status != 'completed')
    elif status_filter == 'completed':
        query = query.filter_by(status='completed')
    
    assignments = query.join(Task).order_by(Task.due_date).all()
    
    return render_template('tasks/my_tasks.html',
        assignments=assignments,
        status_filter=status_filter
    )


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    from app import db, Task, TaskAssignment, User, create_notification
    
    if not current_user.has_permission('manage_tasks'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('tasks.index'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date')
        due_time_str = request.form.get('due_time')
        assigned_users = request.form.getlist('assigned_users')
        
        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('tasks.create'))
        
        due_date = None
        due_time = None
        
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid due date format.', 'danger')
                return redirect(url_for('tasks.create'))
        
        if due_time_str:
            try:
                due_time = datetime.strptime(due_time_str, '%H:%M').time()
            except ValueError:
                pass
        
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            due_time=due_time,
            created_by=current_user.id
        )
        
        db.session.add(task)
        db.session.flush()  # Get task ID
        
        # Assign users
        for user_id in assigned_users:
            assignment = TaskAssignment(
                task_id=task.id,
                user_id=int(user_id)
            )
            db.session.add(assignment)
            
            # Notify user
            create_notification(
                user_id=int(user_id),
                title='New Task Assigned',
                message=f'You have been assigned to task: {title}',
                notification_type='task',
                reference_id=task.id,
                reference_type='task'
            )
        
        db.session.commit()
        
        flash('Task created successfully.', 'success')
        return redirect(url_for('tasks.index'))
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all()
    
    return render_template('tasks/create.html', users=users)


@tasks_bp.route('/<int:task_id>')
@login_required
def view(task_id):
    from app import Task, TaskAssignment, User
    
    task = Task.query.get_or_404(task_id)
    
    # Check access
    can_manage = current_user.has_permission('manage_tasks')
    is_assigned = TaskAssignment.query.filter_by(task_id=task_id, user_id=current_user.id).first() is not None
    
    if not can_manage and not is_assigned:
        flash('Access denied.', 'danger')
        return redirect(url_for('tasks.index'))
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name, User.first_name).all() if can_manage else []
    
    return render_template('tasks/view.html',
        task=task,
        users=users,
        can_manage=can_manage,
        is_assigned=is_assigned
    )


@tasks_bp.route('/<int:task_id>/edit', methods=['POST'])
@login_required
def edit(task_id):
    from app import db, Task, TaskAssignment, User, create_notification
    
    if not current_user.has_permission('manage_tasks'):
        return jsonify({'error': 'Permission denied'}), 403
    
    task = Task.query.get_or_404(task_id)
    
    task.title = request.form.get('title', task.title).strip()
    task.description = request.form.get('description', task.description).strip()
    task.priority = request.form.get('priority', task.priority)
    task.status = request.form.get('status', task.status)
    
    due_date_str = request.form.get('due_date')
    due_time_str = request.form.get('due_time')
    
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if due_time_str:
        try:
            task.due_time = datetime.strptime(due_time_str, '%H:%M').time()
        except ValueError:
            pass
    
    if task.status == 'completed' and not task.completed_at:
        task.completed_at = datetime.utcnow()
    
    # Update assignments
    assigned_users = request.form.getlist('assigned_users')
    current_assigned = [a.user_id for a in task.assignments.all()]
    
    # Remove old assignments
    for assignment in task.assignments.all():
        if str(assignment.user_id) not in assigned_users:
            db.session.delete(assignment)
    
    # Add new assignments
    for user_id in assigned_users:
        if int(user_id) not in current_assigned:
            assignment = TaskAssignment(
                task_id=task.id,
                user_id=int(user_id)
            )
            db.session.add(assignment)
            
            # Notify new user
            create_notification(
                user_id=int(user_id),
                title='New Task Assigned',
                message=f'You have been assigned to task: {task.title}',
                notification_type='task',
                reference_id=task.id,
                reference_type='task'
            )
    
    db.session.commit()
    
    flash('Task updated successfully.', 'success')
    return redirect(url_for('tasks.view', task_id=task_id))


@tasks_bp.route('/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_status(task_id):
    from app import db, Task, TaskAssignment
    
    task = Task.query.get_or_404(task_id)
    
    # Check if user is assigned or can manage
    is_assigned = TaskAssignment.query.filter_by(task_id=task_id, user_id=current_user.id).first() is not None
    can_manage = current_user.has_permission('manage_tasks')
    
    if not is_assigned and not can_manage:
        return jsonify({'error': 'Permission denied'}), 403
    
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
        task.status = new_status
        
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated'})
    
    return jsonify({'error': 'Invalid status'}), 400


@tasks_bp.route('/<int:task_id>/update-my-status', methods=['POST'])
@login_required
def update_my_status(task_id):
    from app import db, Task, TaskAssignment
    
    assignment = TaskAssignment.query.filter_by(
        task_id=task_id,
        user_id=current_user.id
    ).first_or_404()
    
    new_status = request.form.get('status')
    
    if new_status in ['assigned', 'in_progress', 'completed']:
        assignment.status = new_status
        
        if new_status == 'completed':
            assignment.completed_at = datetime.utcnow()
            
            # Check if all assignments are completed
            task = Task.query.get(task_id)
            all_completed = all(a.status == 'completed' for a in task.assignments.all())
            if all_completed:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated'})
    
    return jsonify({'error': 'Invalid status'}), 400


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    from app import db, Task, TaskAssignment
    
    if not current_user.has_permission('manage_tasks'):
        return jsonify({'error': 'Permission denied'}), 403
    
    task = Task.query.get_or_404(task_id)
    
    # Delete assignments first
    TaskAssignment.query.filter_by(task_id=task_id).delete()
    
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Task deleted'})
