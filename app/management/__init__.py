"""
Management Blueprint - System Configuration, Restricted Days, Requirements
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from calendar import monthrange
from app import db
from app.models import (
    RestrictedDay, MonthlyRequirement, LeaveType, 
    AuditLog, User, Schedule, LeaveRequest
)
from app.decorators import permission_required

bp = Blueprint('management', __name__)


# ==================== RESTRICTED DAYS ====================

@bp.route('/restricted-days')
@login_required
@permission_required('management.restricted')
def restricted_days():
    year = request.args.get('year', date.today().year, type=int)
    
    days = RestrictedDay.query.filter(
        db.extract('year', RestrictedDay.date) == year
    ).order_by(RestrictedDay.date).all()
    
    return render_template('management/restricted_days.html', 
        days=days, 
        year=year
    )


@bp.route('/restricted-days/add', methods=['POST'])
@login_required
@permission_required('management.restricted')
def add_restricted_day():
    date_str = request.form.get('date')
    reason = request.form.get('reason')
    
    try:
        restricted_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if already exists
        existing = RestrictedDay.query.filter_by(date=restricted_date).first()
        if existing:
            flash('This date is already marked as restricted', 'warning')
            return redirect(url_for('management.restricted_days'))
        
        day = RestrictedDay(
            date=restricted_date,
            reason=reason,
            created_by=current_user.id
        )
        db.session.add(day)
        db.session.commit()
        
        flash(f'Restricted day added: {restricted_date.strftime("%d/%m/%Y")}', 'success')
        
    except ValueError:
        flash('Invalid date format', 'error')
    
    return redirect(url_for('management.restricted_days'))


@bp.route('/restricted-days/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('management.restricted')
def delete_restricted_day(id):
    day = RestrictedDay.query.get_or_404(id)
    db.session.delete(day)
    db.session.commit()
    flash('Restricted day removed', 'success')
    return redirect(url_for('management.restricted_days'))


# ==================== MONTHLY REQUIREMENTS ====================

@bp.route('/requirements')
@login_required
@permission_required('management.requirements')
def requirements():
    year = request.args.get('year', date.today().year, type=int)
    
    # Get all requirements for the year
    reqs = MonthlyRequirement.query.filter_by(year=year).all()
    req_dict = {r.month: r for r in reqs}
    
    # Build month list
    months = []
    for m in range(1, 13):
        months.append({
            'number': m,
            'name': date(year, m, 1).strftime('%B'),
            'requirement': req_dict.get(m)
        })
    
    return render_template('management/requirements.html',
        months=months,
        year=year
    )


@bp.route('/requirements/update', methods=['POST'])
@login_required
@permission_required('management.requirements')
def update_requirement():
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    required_hours = request.form.get('required_hours', type=float)
    required_days = request.form.get('required_days', type=int)
    notes = request.form.get('notes')
    
    req = MonthlyRequirement.query.filter_by(year=year, month=month).first()
    
    if req:
        req.required_hours = required_hours
        req.required_days = required_days
        req.notes = notes
    else:
        req = MonthlyRequirement(
            year=year,
            month=month,
            required_hours=required_hours,
            required_days=required_days,
            notes=notes,
            created_by=current_user.id
        )
        db.session.add(req)
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    
    flash('Monthly requirement updated', 'success')
    return redirect(url_for('management.requirements', year=year))


# ==================== LEAVE TYPES ====================

@bp.route('/leave-types')
@login_required
@permission_required('management.settings')
def leave_types():
    types = LeaveType.query.all()
    return render_template('management/leave_types.html', types=types)


@bp.route('/leave-types/add', methods=['POST'])
@login_required
@permission_required('management.settings')
def add_leave_type():
    name = request.form.get('name')
    description = request.form.get('description')
    is_paid = 'is_paid' in request.form
    color = request.form.get('color', '#3B82F6')
    
    if LeaveType.query.filter_by(name=name).first():
        flash('Leave type with this name already exists', 'error')
        return redirect(url_for('management.leave_types'))
    
    lt = LeaveType(
        name=name,
        description=description,
        is_paid=is_paid,
        color=color
    )
    db.session.add(lt)
    db.session.commit()
    
    flash(f'Leave type "{name}" added', 'success')
    return redirect(url_for('management.leave_types'))


@bp.route('/leave-types/<int:id>/edit', methods=['POST'])
@login_required
@permission_required('management.settings')
def edit_leave_type(id):
    lt = LeaveType.query.get_or_404(id)
    
    lt.name = request.form.get('name')
    lt.description = request.form.get('description')
    lt.is_paid = 'is_paid' in request.form
    lt.color = request.form.get('color', lt.color)
    lt.is_active = 'is_active' in request.form
    
    db.session.commit()
    flash(f'Leave type "{lt.name}" updated', 'success')
    return redirect(url_for('management.leave_types'))


@bp.route('/leave-types/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('management.settings')
def delete_leave_type(id):
    lt = LeaveType.query.get_or_404(id)
    
    # Check if in use
    if lt.allocations or lt.requests:
        lt.is_active = False
        flash(f'Leave type "{lt.name}" has been deactivated (in use)', 'warning')
    else:
        db.session.delete(lt)
        flash(f'Leave type "{lt.name}" deleted', 'success')
    
    db.session.commit()
    return redirect(url_for('management.leave_types'))


# ==================== REPORTS ====================

@bp.route('/reports')
@login_required
@permission_required('management.reports')
def reports():
    return render_template('management/reports.html')


@bp.route('/reports/attendance')
@login_required
@permission_required('management.reports')
def attendance_report():
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)
    
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    
    report_data = []
    for user in users:
        # Count scheduled days
        scheduled = Schedule.query.filter(
            Schedule.user_id == user.id,
            Schedule.date >= first_day,
            Schedule.date <= last_day
        ).count()
        
        # Count approved leave days
        leave_days = 0
        leaves = LeaveRequest.query.filter(
            LeaveRequest.user_id == user.id,
            LeaveRequest.status == 'approved',
            LeaveRequest.start_date <= last_day,
            LeaveRequest.end_date >= first_day
        ).all()
        
        for leave in leaves:
            start = max(leave.start_date, first_day)
            end = min(leave.end_date, last_day)
            current = start
            while current <= end:
                if current.weekday() < 5:
                    leave_days += 1
                current = current + timedelta(days=1)
        
        report_data.append({
            'user': user,
            'scheduled_days': scheduled,
            'leave_days': leave_days
        })
    
    # Get monthly requirement
    requirement = MonthlyRequirement.query.filter_by(year=year, month=month).first()
    
    return render_template('management/attendance_report.html',
        report_data=report_data,
        year=year,
        month=month,
        month_name=first_day.strftime('%B'),
        requirement=requirement
    )


@bp.route('/reports/leave-summary')
@login_required
@permission_required('management.reports')
def leave_summary_report():
    year = request.args.get('year', date.today().year, type=int)
    
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()
    leave_types = LeaveType.query.filter_by(is_active=True).all()
    
    from app.models import LeaveAllocation
    
    report_data = []
    for user in users:
        user_data = {'user': user, 'allocations': {}}
        for lt in leave_types:
            alloc = LeaveAllocation.query.filter_by(
                user_id=user.id,
                leave_type_id=lt.id,
                year=year
            ).first()
            user_data['allocations'][lt.id] = alloc
        report_data.append(user_data)
    
    return render_template('management/leave_summary_report.html',
        report_data=report_data,
        leave_types=leave_types,
        year=year
    )


# ==================== AUDIT LOG ====================

@bp.route('/audit-log')
@login_required
@permission_required('management.settings')
def audit_log():
    page = request.args.get('page', 1, type=int)
    
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50
    )
    
    return render_template('management/audit_log.html', logs=logs)


# Import timedelta for the report
from datetime import timedelta
