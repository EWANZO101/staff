# Staff Scheduling System

A comprehensive staff scheduling and management application built with Flask. Features dark theme UI, role-based permissions, leave management, task assignments, and a public announcement board.

## Features

### User Management
- **Role-Based Access Control**: Granular permissions system with custom roles
- **First User = Super Admin**: First registered account automatically becomes administrator
- **User Profiles**: Personal information management and password changes
- **Active/Inactive Status**: Easily manage staff availability

### Scheduling
- **Interactive Calendar**: Monthly calendar view with drag-and-drop capability
- **Bulk Assignment**: Assign multiple users to dates efficiently
- **Conflict Detection**: Automatic checks against leave requests
- **Restricted Days**: Mark special dates requiring approval

### Leave Management
- **Multiple Leave Types**: Annual, Sick, Personal, Unpaid, Compassionate (customizable)
- **Leave Allocations**: Set annual allowances per user per leave type
- **Approval Workflow**: Request, approve, or reject with notes
- **Balance Tracking**: Real-time tracking of used and remaining days
- **Calendar Integration**: View leave on schedule calendar

### Task Management
- **Task Creation**: Create tasks with priority levels and due dates
- **Multi-User Assignment**: Assign tasks to one or multiple staff members
- **Status Tracking**: Individual and overall task completion status
- **Notifications**: Automatic notifications on task assignment

### Public Board
- **Announcements**: Post company-wide announcements
- **Events**: Schedule and display upcoming events
- **Operations Info**: Share operational information
- **Pin & Prioritize**: Highlight important posts
- **Auto-Expiration**: Set expiry dates for time-sensitive posts

### Notifications
- **In-App Notifications**: Real-time notification system
- **Login Alerts**: See what happened since your last visit
- **Popup Notifications**: Important alerts displayed on login
- **Notification Types**: Shifts, leave, tasks, board posts, system

### Reports
- **Attendance Report**: Monthly scheduled days and leave by employee
- **Leave Summary**: Leave allocations and usage overview
- **Audit Log**: Track system changes and user actions

## Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- (Optional) MySQL or PostgreSQL for production

### Quick Start

1. **Clone or download the project**
   ```bash
   cd staff_scheduler
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set a secure SECRET_KEY
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

6. **Open in browser**
   ```
   http://localhost:5000
   ```

7. **Create your first account**
   - Go to Sign Up
   - First account automatically becomes Super Admin

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Session encryption key | Random (set in production!) |
| `DATABASE_URL` | Database connection string | SQLite file |
| `FLASK_ENV` | Environment mode | development |
| `FLASK_DEBUG` | Debug mode | 1 |

### Database Options

**SQLite (Development)**
```
DATABASE_URL=sqlite:///staff_scheduler.db
```

**MySQL (Production)**
```bash
pip install PyMySQL
DATABASE_URL=mysql+pymysql://user:password@localhost/staff_scheduler
```

**PostgreSQL (Production)**
```bash
pip install psycopg2-binary
DATABASE_URL=postgresql://user:password@localhost/staff_scheduler
```

## Default Permissions

| Permission | Description |
|------------|-------------|
| `users.view` | View user list |
| `users.create` | Create new users |
| `users.edit` | Edit user details |
| `users.delete` | Deactivate users |
| `roles.manage` | Manage roles and permissions |
| `schedules.view` | View all schedules |
| `schedules.manage` | Create/edit schedules |
| `leave.view` | View leave requests |
| `leave.approve` | Approve/reject leave |
| `leave.allocate` | Set leave allocations |
| `tasks.view` | View all tasks |
| `tasks.manage` | Create/manage tasks |
| `board.view` | View public board |
| `board.manage` | Create/manage posts |
| `management.restricted` | Manage restricted days |
| `management.requirements` | Set monthly requirements |
| `management.settings` | System settings |
| `management.reports` | View reports |

## Default Leave Types

| Type | Description | Color |
|------|-------------|-------|
| Annual Leave | Paid holiday allowance | Blue |
| Sick Leave | Medical absence | Red |
| Personal Leave | Personal time off | Green |
| Unpaid Leave | Leave without pay | Gray |
| Compassionate Leave | Bereavement/family emergency | Purple |

## Project Structure

```
staff_scheduler/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models.py             # Database models
│   ├── decorators.py         # Permission decorators
│   ├── auth/                 # Authentication blueprint
│   ├── main/                 # Main user features
│   ├── admin/                # Admin management
│   ├── management/           # System configuration
│   ├── tasks/                # Task management
│   ├── board/                # Public board
│   ├── api/                  # API endpoints
│   └── templates/            # HTML templates
├── config.py                 # Configuration classes
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
└── README.md                # This file
```

## Production Deployment

### Using Gunicorn

1. Install Gunicorn:
   ```bash
   pip install gunicorn
   ```

2. Run:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 run:app
   ```

### Security Checklist

- [ ] Set a strong `SECRET_KEY`
- [ ] Use HTTPS in production
- [ ] Configure proper database credentials
- [ ] Set `FLASK_ENV=production`
- [ ] Disable debug mode
- [ ] Configure CORS if needed
- [ ] Set up regular database backups

## Scaling Notes

- **5-50 users**: SQLite works fine
- **50-500 users**: Consider MySQL/PostgreSQL
- **500+ users**: Use PostgreSQL with connection pooling
- **1000+ users**: Consider caching (Redis), load balancing

## Troubleshooting

### Common Issues

**Database connection error**
- Check DATABASE_URL format
- Ensure database server is running
- Verify credentials

**Permission denied errors**
- Ensure user has required role/permissions
- Check if first user was created properly

**Session expired frequently**
- Increase PERMANENT_SESSION_LIFETIME in config
- Check SECRET_KEY is consistent

## License

This project is proprietary software. All rights reserved.

## Support

For issues or feature requests, contact your system administrator.
