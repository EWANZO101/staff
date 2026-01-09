"""
Management Blueprint
System configuration, monthly requirements, restricted days, leave types
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import calendar

management_bp = Blueprint('management', __name__, url_prefix='/management')

def management_required(f):
    """Check if user has management permissions"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))
        
        mgmt_perms = ['manage_monthly_config', 'manage_restricted_days', 'manage_leave_types']
        if not current_user.has_any_permission(mgmt_perms):
            flash('Management access required.', 'danger')
            return redirect(url_for('user.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@management_bp.route('/')
@login_required
@management_required
def index():
    from app import MonthlyConfig, RestrictedDay, LeaveType
    
    today = date.today()
    current_year = today.year
    
    # Get monthly configs for current year
    monthly_configs = MonthlyConfig.query.filter_by(year=current_year).order_by(MonthlyConfig.month).all()
    config_dict = {c.month: c for c in monthly_configs}
    
    # Get upcoming restricted days
    restricted_days = RestrictedDay.query.filter(
        RestrictedDay.date >= today
    ).order_by(RestrictedDay.date).limit(10).all()
    
    # Leave types
    leave_types = LeaveType.query.all()
    
    return render_template('management/index.html',
        config_dict=config_dict,
        restricted_days=restricted_days,
        leave_types=leave_types,
        current_year=current_year,
        months=list(range(1, 13))
    )


# ============================================================
# MONTHLY CONFIGURATION
# ============================================================

@management_bp.route('/monthly')
@management_bp.route('/monthly/<int:year>')
@login_required
@management_required
def monthly_config(year=None):
    from app import MonthlyConfig
    
    if year is None:
        year = date.today().year
    
    configs = MonthlyConfig.query.filter_by(year=year).order_by(MonthlyConfig.month).all()
    config_dict = {c.month: c for c in configs}
    
    return render_template('management/monthly_config.html',
        config_dict=config_dict,
        year=year,
        months=list(range(1, 13)),
        prev_year=year - 1,
        next_year=year + 1
    )


@management_bp.route('/monthly/set', methods=['POST'])
@login_required
def set_monthly_config():
    from app import db, MonthlyConfig
    
    if not current_user.has_permission('manage_monthly_config'):
        return jsonify({'error': 'Permission denied'}), 403
    
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    required_days = request.form.get('required_days', type=int)
    required_hours = request.form.get('required_hours', type=float)
    notes = request.form.get('notes', '').strip()
    
    config = MonthlyConfig.query.filter_by(year=year, month=month).first()
    
    if config:
        config.required_days = required_days
        config.required_hours = required_hours
        config.notes = notes
    else:
        config = MonthlyConfig(
            year=year,
            month=month,
            required_days=required_days,
            required_hours=required_hours,
            notes=notes
        )
        db.session.add(config)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Configuration saved'})


# ============================================================
# RESTRICTED DAYS
# ============================================================

@management_bp.route('/restricted')
@management_bp.route('/restricted/<int:year>/<int:month>')
@login_required
@management_required
def restricted_days(year=None, month=None):
    from app import RestrictedDay
    
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
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    # Get restricted days for month
    restricted = RestrictedDay.query.filter(
        RestrictedDay.date >= month_start,
        RestrictedDay.date <= month_end
    ).all()
    restricted_dict = {r.date: r for r in restricted}
    
    # All restricted days for listing
    all_restricted = RestrictedDay.query.order_by(RestrictedDay.date).all()
    
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
    
    return render_template('management/restricted_days.html',
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        restricted_dict=restricted_dict,
        all_restricted=all_restricted,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month
    )


@management_bp.route('/restricted/add', methods=['POST'])
@login_required
def add_restricted_day():
    from app import db, RestrictedDay
    
    if not current_user.has_permission('manage_restricted_days'):
        return jsonify({'error': 'Permission denied'}), 403
    
    date_str = request.form.get('date')
    reason = request.form.get('reason', '').strip()
    
    try:
        restricted_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400
    
    existing = RestrictedDay.query.filter_by(date=restricted_date).first()
    if existing:
        return jsonify({'error': 'Date is already restricted'}), 400
    
    restricted = RestrictedDay(
        date=restricted_date,
        reason=reason,
        created_by=current_user.id
    )
    
    db.session.add(restricted)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Restricted day added'})


@management_bp.route('/restricted/<int:restricted_id>/remove', methods=['POST'])
@login_required
def remove_restricted_day(restricted_id):
    from app import db, RestrictedDay
    
    if not current_user.has_permission('manage_restricted_days'):
        return jsonify({'error': 'Permission denied'}), 403
    
    restricted = RestrictedDay.query.get_or_404(restricted_id)
    
    db.session.delete(restricted)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Restricted day removed'})


# ============================================================
# LEAVE TYPES
# ============================================================

@management_bp.route('/leave-types')
@login_required
@management_required
def leave_types():
    from app import LeaveType
    
    if not current_user.has_permission('manage_leave_types'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('management.index'))
    
    leave_types = LeaveType.query.order_by(LeaveType.name).all()
    
    return render_template('management/leave_types.html', leave_types=leave_types)


@management_bp.route('/leave-types/add', methods=['POST'])
@login_required
def add_leave_type():
    from app import db, LeaveType
    
    if not current_user.has_permission('manage_leave_types'):
        return jsonify({'error': 'Permission denied'}), 403
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    color = request.form.get('color', 'blue')
    requires_approval = request.form.get('requires_approval') == 'on'
    
    if LeaveType.query.filter_by(name=name).first():
        flash('Leave type already exists.', 'danger')
        return redirect(url_for('management.leave_types'))
    
    leave_type = LeaveType(
        name=name,
        description=description,
        color=color,
        requires_approval=requires_approval
    )
    
    db.session.add(leave_type)
    db.session.commit()
    
    flash(f'Leave type "{name}" created.', 'success')
    return redirect(url_for('management.leave_types'))


@management_bp.route('/leave-types/<int:type_id>/edit', methods=['POST'])
@login_required
def edit_leave_type(type_id):
    from app import db, LeaveType
    
    if not current_user.has_permission('manage_leave_types'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('management.leave_types'))
    
    leave_type = LeaveType.query.get_or_404(type_id)
    
    leave_type.name = request.form.get('name', leave_type.name).strip()
    leave_type.description = request.form.get('description', leave_type.description).strip()
    leave_type.color = request.form.get('color', leave_type.color)
    leave_type.requires_approval = request.form.get('requires_approval') == 'on'
    leave_type.is_active = request.form.get('is_active') == 'on'
    
    db.session.commit()
    
    flash(f'Leave type "{leave_type.name}" updated.', 'success')
    return redirect(url_for('management.leave_types'))


@management_bp.route('/leave-types/<int:type_id>/toggle', methods=['POST'])
@login_required
def toggle_leave_type(type_id):
    from app import db, LeaveType
    
    if not current_user.has_permission('manage_leave_types'):
        return jsonify({'error': 'Permission denied'}), 403
    
    leave_type = LeaveType.query.get_or_404(type_id)
    leave_type.is_active = not leave_type.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': leave_type.is_active,
        'message': f'Leave type {"activated" if leave_type.is_active else "deactivated"}'
    })
