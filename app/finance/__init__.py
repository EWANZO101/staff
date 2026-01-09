"""
Finance Blueprint - Financial management module
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func, extract
from app import db
from app.models import (
    User, Expense, ExpenseCategory, Budget, FinancialReport,
    FinancialLink, Invoice, PayrollRecord, Notification
)
from app.decorators import permission_required

bp = Blueprint('finance', __name__)


# ==================== DASHBOARD ====================

@bp.route('/')
@login_required
@permission_required('finance.view')
def dashboard():
    """Financial dashboard with overview"""
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    
    # This month's expenses
    monthly_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.expense_date >= month_start,
        Expense.status.in_(['approved', 'reimbursed'])
    ).scalar() or 0
    
    # Pending expenses count
    pending_expenses = Expense.query.filter_by(status='pending').count()
    
    # Active budgets
    active_budgets = Budget.query.filter(
        Budget.start_date <= today,
        Budget.end_date >= today
    ).all()
    
    # Overdue invoices
    overdue_invoices = Invoice.query.filter(
        Invoice.status == 'pending',
        Invoice.due_date < today
    ).count()
    
    # Recent expenses
    recent_expenses = Expense.query.order_by(
        Expense.created_at.desc()
    ).limit(5).all()
    
    # Expense by category this month
    category_breakdown = db.session.query(
        ExpenseCategory.name,
        ExpenseCategory.color,
        func.sum(Expense.amount).label('total')
    ).join(Expense).filter(
        Expense.expense_date >= month_start,
        Expense.status.in_(['approved', 'reimbursed'])
    ).group_by(ExpenseCategory.id).all()
    
    # Quick links
    quick_links = FinancialLink.query.filter_by(is_active=True).order_by(
        FinancialLink.order
    ).limit(6).all()
    
    # YTD total
    ytd_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.expense_date >= year_start,
        Expense.status.in_(['approved', 'reimbursed'])
    ).scalar() or 0
    
    return render_template('finance/dashboard.html',
        monthly_expenses=monthly_expenses,
        pending_expenses=pending_expenses,
        active_budgets=active_budgets,
        overdue_invoices=overdue_invoices,
        recent_expenses=recent_expenses,
        category_breakdown=category_breakdown,
        quick_links=quick_links,
        ytd_total=ytd_total
    )


# ==================== EXPENSES ====================

@bp.route('/expenses')
@login_required
@permission_required('finance.view')
def expenses():
    """List all expenses"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    category_id = request.args.get('category', 'all')
    
    query = Expense.query
    
    # Filter by status
    if status != 'all':
        query = query.filter_by(status=status)
    
    # Filter by category
    if category_id != 'all':
        query = query.filter_by(category_id=category_id)
    
    # If user can't approve, only show their own
    if not current_user.has_permission('finance.expenses.approve'):
        query = query.filter_by(user_id=current_user.id)
    
    expenses = query.order_by(Expense.created_at.desc()).paginate(page=page, per_page=20)
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    
    # Counts
    counts = {
        'all': Expense.query.count(),
        'pending': Expense.query.filter_by(status='pending').count(),
        'approved': Expense.query.filter_by(status='approved').count(),
        'rejected': Expense.query.filter_by(status='rejected').count(),
        'reimbursed': Expense.query.filter_by(status='reimbursed').count(),
    }
    
    return render_template('finance/expenses.html',
        expenses=expenses,
        categories=categories,
        current_status=status,
        current_category=category_id,
        counts=counts
    )


@bp.route('/expenses/submit', methods=['GET', 'POST'])
@login_required
@permission_required('finance.expenses.submit')
def submit_expense():
    """Submit a new expense"""
    if request.method == 'POST':
        expense = Expense(
            user_id=current_user.id,
            category_id=request.form.get('category_id'),
            amount=Decimal(request.form.get('amount')),
            description=request.form.get('description'),
            vendor=request.form.get('vendor'),
            expense_date=datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d').date(),
            receipt_url=request.form.get('receipt_url'),
            notes=request.form.get('notes')
        )
        db.session.add(expense)
        db.session.commit()
        
        flash('Expense submitted successfully', 'success')
        return redirect(url_for('finance.expenses'))
    
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('finance/submit_expense.html', categories=categories)


@bp.route('/expenses/<int:id>')
@login_required
@permission_required('finance.view')
def view_expense(id):
    """View expense details"""
    expense = Expense.query.get_or_404(id)
    
    # Check permission
    if expense.user_id != current_user.id and not current_user.has_permission('finance.expenses.approve'):
        flash('Access denied', 'error')
        return redirect(url_for('finance.expenses'))
    
    return render_template('finance/view_expense.html', expense=expense)


@bp.route('/expenses/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('finance.expenses.approve')
def approve_expense(id):
    """Approve an expense"""
    expense = Expense.query.get_or_404(id)
    expense.status = 'approved'
    expense.approved_by = current_user.id
    expense.approved_at = datetime.utcnow()
    db.session.commit()
    
    # Notify submitter
    notification = Notification(
        user_id=expense.user_id,
        title='Expense Approved',
        message=f'Your expense "${expense.amount}" for "{expense.description}" has been approved.',
        type='success',
        related_id=expense.id,
        related_type='expense'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Expense approved', 'success')
    return redirect(url_for('finance.expenses'))


@bp.route('/expenses/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('finance.expenses.approve')
def reject_expense(id):
    """Reject an expense"""
    expense = Expense.query.get_or_404(id)
    expense.status = 'rejected'
    expense.approved_by = current_user.id
    expense.approved_at = datetime.utcnow()
    expense.rejection_reason = request.form.get('reason', '')
    db.session.commit()
    
    # Notify submitter
    notification = Notification(
        user_id=expense.user_id,
        title='Expense Rejected',
        message=f'Your expense "${expense.amount}" for "{expense.description}" has been rejected.',
        type='error',
        related_id=expense.id,
        related_type='expense'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Expense rejected', 'success')
    return redirect(url_for('finance.expenses'))


@bp.route('/expenses/<int:id>/reimburse', methods=['POST'])
@login_required
@permission_required('finance.expenses.approve')
def reimburse_expense(id):
    """Mark expense as reimbursed"""
    expense = Expense.query.get_or_404(id)
    expense.status = 'reimbursed'
    expense.reimbursed_at = datetime.utcnow()
    db.session.commit()
    
    # Notify submitter
    notification = Notification(
        user_id=expense.user_id,
        title='Expense Reimbursed',
        message=f'Your expense "${expense.amount}" has been reimbursed.',
        type='success',
        related_id=expense.id,
        related_type='expense'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Expense marked as reimbursed', 'success')
    return redirect(url_for('finance.expenses'))


# ==================== BUDGETS ====================

@bp.route('/budgets')
@login_required
@permission_required('finance.budgets')
def budgets():
    """List all budgets"""
    today = date.today()
    
    active_budgets = Budget.query.filter(
        Budget.start_date <= today,
        Budget.end_date >= today
    ).all()
    
    upcoming_budgets = Budget.query.filter(
        Budget.start_date > today
    ).order_by(Budget.start_date).all()
    
    past_budgets = Budget.query.filter(
        Budget.end_date < today
    ).order_by(Budget.end_date.desc()).limit(10).all()
    
    return render_template('finance/budgets.html',
        active_budgets=active_budgets,
        upcoming_budgets=upcoming_budgets,
        past_budgets=past_budgets
    )


@bp.route('/budgets/create', methods=['GET', 'POST'])
@login_required
@permission_required('finance.budgets')
def create_budget():
    """Create a new budget"""
    if request.method == 'POST':
        budget = Budget(
            name=request.form.get('name'),
            category_id=request.form.get('category_id') or None,
            department=request.form.get('department') or None,
            amount=Decimal(request.form.get('amount')),
            period_type=request.form.get('period_type'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date(),
            notes=request.form.get('notes'),
            created_by=current_user.id
        )
        db.session.add(budget)
        db.session.commit()
        
        flash('Budget created successfully', 'success')
        return redirect(url_for('finance.budgets'))
    
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('finance/create_budget.html', categories=categories)


@bp.route('/budgets/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('finance.budgets')
def edit_budget(id):
    """Edit a budget"""
    budget = Budget.query.get_or_404(id)
    
    if request.method == 'POST':
        budget.name = request.form.get('name')
        budget.category_id = request.form.get('category_id') or None
        budget.department = request.form.get('department') or None
        budget.amount = Decimal(request.form.get('amount'))
        budget.period_type = request.form.get('period_type')
        budget.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        budget.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        budget.notes = request.form.get('notes')
        db.session.commit()
        
        flash('Budget updated successfully', 'success')
        return redirect(url_for('finance.budgets'))
    
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('finance/edit_budget.html', budget=budget, categories=categories)


@bp.route('/budgets/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('finance.budgets')
def delete_budget(id):
    """Delete a budget"""
    budget = Budget.query.get_or_404(id)
    db.session.delete(budget)
    db.session.commit()
    
    flash('Budget deleted', 'success')
    return redirect(url_for('finance.budgets'))


# ==================== INVOICES ====================

@bp.route('/invoices')
@login_required
@permission_required('finance.invoices')
def invoices():
    """List all invoices"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    
    query = Invoice.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    invoices = query.order_by(Invoice.due_date).paginate(page=page, per_page=20)
    
    # Counts
    today = date.today()
    counts = {
        'all': Invoice.query.count(),
        'pending': Invoice.query.filter_by(status='pending').count(),
        'overdue': Invoice.query.filter(Invoice.status == 'pending', Invoice.due_date < today).count(),
        'paid': Invoice.query.filter_by(status='paid').count(),
    }
    
    return render_template('finance/invoices.html',
        invoices=invoices,
        current_status=status,
        counts=counts
    )


@bp.route('/invoices/create', methods=['GET', 'POST'])
@login_required
@permission_required('finance.invoices')
def create_invoice():
    """Create a new invoice"""
    if request.method == 'POST':
        invoice = Invoice(
            invoice_number=request.form.get('invoice_number'),
            vendor=request.form.get('vendor'),
            amount=Decimal(request.form.get('amount')),
            issue_date=datetime.strptime(request.form.get('issue_date'), '%Y-%m-%d').date(),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date(),
            category_id=request.form.get('category_id') or None,
            description=request.form.get('description'),
            created_by=current_user.id
        )
        db.session.add(invoice)
        db.session.commit()
        
        flash('Invoice created successfully', 'success')
        return redirect(url_for('finance.invoices'))
    
    categories = ExpenseCategory.query.filter_by(is_active=True).all()
    return render_template('finance/create_invoice.html', categories=categories)


@bp.route('/invoices/<int:id>/pay', methods=['POST'])
@login_required
@permission_required('finance.invoices')
def pay_invoice(id):
    """Mark invoice as paid"""
    invoice = Invoice.query.get_or_404(id)
    invoice.status = 'paid'
    invoice.payment_date = date.today()
    invoice.payment_method = request.form.get('payment_method', 'bank_transfer')
    db.session.commit()
    
    flash('Invoice marked as paid', 'success')
    return redirect(url_for('finance.invoices'))


# ==================== REPORTS ====================

@bp.route('/reports')
@login_required
@permission_required('finance.reports')
def reports():
    """Financial reports"""
    # Get saved reports
    saved_reports = FinancialReport.query.order_by(
        FinancialReport.created_at.desc()
    ).limit(20).all()
    
    return render_template('finance/reports.html', saved_reports=saved_reports)


@bp.route('/reports/generate', methods=['POST'])
@login_required
@permission_required('finance.reports.generate')
def generate_report():
    """Generate a financial report"""
    report_type = request.form.get('report_type')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
    
    # Generate report data based on type
    if report_type == 'expense_summary':
        data = generate_expense_summary(start_date, end_date)
        title = f'Expense Summary: {start_date} to {end_date}'
    elif report_type == 'budget_analysis':
        data = generate_budget_analysis(start_date, end_date)
        title = f'Budget Analysis: {start_date} to {end_date}'
    elif report_type == 'category_breakdown':
        data = generate_category_breakdown(start_date, end_date)
        title = f'Category Breakdown: {start_date} to {end_date}'
    else:
        flash('Invalid report type', 'error')
        return redirect(url_for('finance.reports'))
    
    import json
    report = FinancialReport(
        title=title,
        report_type=report_type,
        period_start=start_date,
        period_end=end_date,
        data=json.dumps(data),
        generated_by=current_user.id
    )
    db.session.add(report)
    db.session.commit()
    
    flash('Report generated successfully', 'success')
    return redirect(url_for('finance.view_report', id=report.id))


def generate_expense_summary(start_date, end_date):
    """Generate expense summary data"""
    expenses = Expense.query.filter(
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date,
        Expense.status.in_(['approved', 'reimbursed'])
    ).all()
    
    total = sum(float(e.amount) for e in expenses)
    by_category = {}
    by_user = {}
    
    for e in expenses:
        cat_name = e.category.name if e.category else 'Uncategorized'
        by_category[cat_name] = by_category.get(cat_name, 0) + float(e.amount)
        
        user_name = e.submitter.full_name if e.submitter else 'Unknown'
        by_user[user_name] = by_user.get(user_name, 0) + float(e.amount)
    
    return {
        'total': total,
        'count': len(expenses),
        'by_category': by_category,
        'by_user': by_user
    }


def generate_budget_analysis(start_date, end_date):
    """Generate budget analysis data"""
    budgets = Budget.query.filter(
        Budget.start_date <= end_date,
        Budget.end_date >= start_date
    ).all()
    
    analysis = []
    for b in budgets:
        analysis.append({
            'name': b.name,
            'allocated': float(b.amount),
            'spent': float(b.spent_amount),
            'remaining': float(b.remaining_amount),
            'usage_pct': b.usage_percentage
        })
    
    return {'budgets': analysis}


def generate_category_breakdown(start_date, end_date):
    """Generate category breakdown data"""
    breakdown = db.session.query(
        ExpenseCategory.name,
        func.sum(Expense.amount).label('total'),
        func.count(Expense.id).label('count')
    ).join(Expense).filter(
        Expense.expense_date >= start_date,
        Expense.expense_date <= end_date,
        Expense.status.in_(['approved', 'reimbursed'])
    ).group_by(ExpenseCategory.id).all()
    
    return {
        'categories': [
            {'name': b[0], 'total': float(b[1]), 'count': b[2]}
            for b in breakdown
        ]
    }


@bp.route('/reports/<int:id>')
@login_required
@permission_required('finance.reports')
def view_report(id):
    """View a generated report"""
    import json
    report = FinancialReport.query.get_or_404(id)
    data = json.loads(report.data) if report.data else {}
    return render_template('finance/view_report.html', report=report, data=data)


# ==================== FINANCIAL LINKS ====================

@bp.route('/links')
@login_required
@permission_required('finance.view')
def links():
    """View financial resource links"""
    links_by_category = {}
    links = FinancialLink.query.filter_by(is_active=True).order_by(
        FinancialLink.category, FinancialLink.order
    ).all()
    
    for link in links:
        cat = link.category or 'General'
        if cat not in links_by_category:
            links_by_category[cat] = []
        links_by_category[cat].append(link)
    
    return render_template('finance/links.html', links_by_category=links_by_category)


@bp.route('/links/manage', methods=['GET', 'POST'])
@login_required
@permission_required('finance.links')
def manage_links():
    """Manage financial links"""
    if request.method == 'POST':
        link = FinancialLink(
            title=request.form.get('title'),
            url=request.form.get('url'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            icon=request.form.get('icon', 'link'),
            order=int(request.form.get('order', 0)),
            created_by=current_user.id
        )
        db.session.add(link)
        db.session.commit()
        
        flash('Link added successfully', 'success')
        return redirect(url_for('finance.manage_links'))
    
    links = FinancialLink.query.order_by(FinancialLink.category, FinancialLink.order).all()
    return render_template('finance/manage_links.html', links=links)


@bp.route('/links/<int:id>/delete', methods=['POST'])
@login_required
@permission_required('finance.links')
def delete_link(id):
    """Delete a financial link"""
    link = FinancialLink.query.get_or_404(id)
    db.session.delete(link)
    db.session.commit()
    
    flash('Link deleted', 'success')
    return redirect(url_for('finance.manage_links'))


# ==================== CATEGORIES ====================

@bp.route('/categories')
@login_required
@permission_required('finance.admin')
def categories():
    """Manage expense categories"""
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('finance/categories.html', categories=categories)


@bp.route('/categories/create', methods=['POST'])
@login_required
@permission_required('finance.admin')
def create_category():
    """Create expense category"""
    category = ExpenseCategory(
        name=request.form.get('name'),
        description=request.form.get('description'),
        color=request.form.get('color', '#3B82F6'),
        budget_limit=Decimal(request.form.get('budget_limit')) if request.form.get('budget_limit') else None
    )
    db.session.add(category)
    db.session.commit()
    
    flash('Category created', 'success')
    return redirect(url_for('finance.categories'))


@bp.route('/categories/<int:id>/toggle', methods=['POST'])
@login_required
@permission_required('finance.admin')
def toggle_category(id):
    """Toggle category active status"""
    category = ExpenseCategory.query.get_or_404(id)
    category.is_active = not category.is_active
    db.session.commit()
    
    flash(f'Category {"activated" if category.is_active else "deactivated"}', 'success')
    return redirect(url_for('finance.categories'))


# ==================== API ENDPOINTS ====================

@bp.route('/api/expense-stats')
@login_required
@permission_required('finance.view')
def api_expense_stats():
    """Get expense statistics for charts"""
    today = date.today()
    
    # Last 6 months data
    months_data = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year+1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month+1, day=1) - timedelta(days=1)
        
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.expense_date >= month_start,
            Expense.expense_date <= month_end,
            Expense.status.in_(['approved', 'reimbursed'])
        ).scalar() or 0
        
        months_data.append({
            'month': month_start.strftime('%b %Y'),
            'total': float(total)
        })
    
    return jsonify(months_data)
