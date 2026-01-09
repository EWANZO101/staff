"""
Application Configuration
"""
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-change-in-production'
    
    # Database configuration
    # Default: SQLite for development
    # Production: Set DATABASE_URL environment variable
    # Example MySQL: mysql+pymysql://user:password@localhost/staff_scheduler
    # Example PostgreSQL: postgresql://user:password@localhost/staff_scheduler
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'staff_scheduler.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # Leave types default allocation (days per year)
    DEFAULT_ANNUAL_LEAVE = 25
    DEFAULT_SICK_LEAVE = 10
    DEFAULT_PERSONAL_LEAVE = 5
    
    # Date and time formats
    DATE_FORMAT = '%d/%m/%Y'
    TIME_FORMAT = '%H:%M'
    DATETIME_FORMAT = '%d/%m/%Y %H:%M'


class DevelopmentConfig(Config):
    DEBUG = True
    # Use SQLite for easier development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
