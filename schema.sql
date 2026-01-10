CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	first_name VARCHAR(64) NOT NULL, 
	last_name VARCHAR(64) NOT NULL, 
	phone VARCHAR(20), 
	department VARCHAR(100), 
	is_active BOOLEAN, 
	is_first_account BOOLEAN, 
	created_at DATETIME, 
	last_login DATETIME, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE TABLE permissions (
	id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	description VARCHAR(256), 
	category VARCHAR(64), 
	PRIMARY KEY (id), 
	UNIQUE (code)
);
CREATE TABLE leave_types (
	id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(256), 
	is_paid BOOLEAN, 
	color VARCHAR(7), 
	is_active BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE TABLE expense_categories (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	color VARCHAR(7), 
	is_active BOOLEAN, 
	budget_limit NUMERIC(12, 2), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);
CREATE TABLE roles (
	id INTEGER NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	description VARCHAR(256), 
	is_system BOOLEAN, 
	created_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE schedules (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	start_time TIME NOT NULL, 
	end_time TIME NOT NULL, 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE INDEX idx_schedule_user_date ON schedules (user_id, date);
CREATE INDEX ix_schedules_date ON schedules (date);
CREATE TABLE restricted_days (
	id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	reason VARCHAR(256) NOT NULL, 
	created_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE UNIQUE INDEX ix_restricted_days_date ON restricted_days (date);
CREATE TABLE leave_allocations (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	allocated_days FLOAT, 
	allocated_hours FLOAT, 
	used_days FLOAT, 
	used_hours FLOAT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_user_leave_year UNIQUE (user_id, leave_type_id, year), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id)
);
CREATE TABLE leave_requests (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	leave_type_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	reason TEXT, 
	status VARCHAR(20), 
	reviewed_by INTEGER, 
	reviewed_at DATETIME, 
	review_notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(leave_type_id) REFERENCES leave_types (id), 
	FOREIGN KEY(reviewed_by) REFERENCES users (id)
);
CREATE TABLE unavailability (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	reason TEXT NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_user_unavailability UNIQUE (user_id, date), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE tasks (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	assigned_to INTEGER, 
	assigned_by INTEGER, 
	due_date DATE, 
	due_time TIME, 
	priority VARCHAR(20), 
	status VARCHAR(20), 
	category VARCHAR(100), 
	created_at DATETIME, 
	updated_at DATETIME, 
	completed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(assigned_by) REFERENCES users (id)
);
CREATE TABLE board_posts (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	post_type VARCHAR(50), 
	priority VARCHAR(20), 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	expires_at DATETIME, 
	event_date DATE, 
	event_time TIME, 
	is_pinned BOOLEAN, 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	message TEXT NOT NULL, 
	type VARCHAR(50), 
	is_read BOOLEAN, 
	is_popup BOOLEAN, 
	created_at DATETIME, 
	related_id INTEGER, 
	related_type VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX idx_notification_user_unread ON notifications (user_id, is_read);
CREATE TABLE monthly_requirements (
	id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	required_hours FLOAT, 
	required_days INTEGER, 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT unique_year_month UNIQUE (year, month), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE audit_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(50), 
	entity_id INTEGER, 
	details TEXT, 
	ip_address VARCHAR(45), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE expenses (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(3), 
	description VARCHAR(500) NOT NULL, 
	vendor VARCHAR(200), 
	receipt_url VARCHAR(500), 
	expense_date DATE NOT NULL, 
	status VARCHAR(20), 
	approved_by INTEGER, 
	approved_at DATETIME, 
	rejection_reason VARCHAR(500), 
	reimbursed_at DATETIME, 
	notes TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);
CREATE INDEX idx_expense_status ON expenses (status);
CREATE INDEX idx_expense_user_date ON expenses (user_id, expense_date);
CREATE TABLE budgets (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	category_id INTEGER, 
	department VARCHAR(100), 
	amount NUMERIC(12, 2) NOT NULL, 
	period_type VARCHAR(20), 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE financial_reports (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	report_type VARCHAR(50) NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	data TEXT, 
	file_url VARCHAR(500), 
	generated_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(generated_by) REFERENCES users (id)
);
CREATE TABLE financial_links (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	url VARCHAR(500) NOT NULL, 
	description VARCHAR(500), 
	category VARCHAR(100), 
	icon VARCHAR(50), 
	is_active BOOLEAN, 
	"order" INTEGER, 
	created_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE invoices (
	id INTEGER NOT NULL, 
	invoice_number VARCHAR(50) NOT NULL, 
	vendor VARCHAR(200) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(3), 
	issue_date DATE NOT NULL, 
	due_date DATE NOT NULL, 
	status VARCHAR(20), 
	payment_date DATE, 
	payment_method VARCHAR(50), 
	category_id INTEGER, 
	description TEXT, 
	attachment_url VARCHAR(500), 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (invoice_number), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE payroll_records (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	base_salary NUMERIC(12, 2) NOT NULL, 
	overtime_hours NUMERIC(6, 2), 
	overtime_rate NUMERIC(8, 2), 
	bonuses NUMERIC(12, 2), 
	deductions NUMERIC(12, 2), 
	tax_amount NUMERIC(12, 2), 
	net_pay NUMERIC(12, 2) NOT NULL, 
	status VARCHAR(20), 
	payment_date DATE, 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE role_permissions (
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	PRIMARY KEY (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id), 
	FOREIGN KEY(permission_id) REFERENCES permissions (id)
);
CREATE TABLE user_roles (
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	PRIMARY KEY (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);
CREATE TABLE subscriptions (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description VARCHAR(500), 
	vendor VARCHAR(200), 
	amount NUMERIC(12, 2) NOT NULL, 
	currency VARCHAR(3), 
	billing_cycle VARCHAR(20), 
	category_id INTEGER, 
	start_date DATE NOT NULL, 
	next_billing_date DATE, 
	end_date DATE, 
	is_active BOOLEAN, 
	auto_renew BOOLEAN, 
	payment_method VARCHAR(100), 
	account_info VARCHAR(200), 
	website_url VARCHAR(500), 
	notes TEXT, 
	created_by INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);
CREATE TABLE site_settings (
	id INTEGER NOT NULL, 
	"key" VARCHAR(100) NOT NULL, 
	value TEXT, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE ("key")
);
