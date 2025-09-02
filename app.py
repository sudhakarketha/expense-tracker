import os
import sqlite3
import mysql.connector
from urllib.parse import urlparse
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from datetime import datetime
import hashlib
import secrets
from functools import wraps

app = Flask(__name__)
# Set a secret key for session management
app.secret_key = secrets.token_hex(16)

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Other"]
budget = 0

# Default to MySQL if DATABASE_URL is provided
USE_MYSQL = os.environ.get('DATABASE_URL') is not None

if USE_MYSQL:
    db_url = os.environ.get('DATABASE_URL')
    url = urlparse(db_url)
    db_config = {
        'host': url.hostname,
        'user': url.username,
        'password': url.password,
        'database': url.path.lstrip('/'),
        'port': url.port or 3306
    }

    def get_db_connection():
        try:
            conn = mysql.connector.connect(**db_config)
            return conn
        except mysql.connector.Error as err:
            print(f"Error connecting to MySQL database: {err}")
            # Attempt to create the database if it doesn't exist
            if err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                try:
                    # Connect without specifying database
                    temp_config = db_config.copy()
                    temp_config.pop('database')
                    conn = mysql.connector.connect(**temp_config)
                    cursor = conn.cursor()
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
                    cursor.close()
                    conn.close()
                    # Try connecting again with the database
                    return mysql.connector.connect(**db_config)
                except mysql.connector.Error as err:
                    print(f"Failed to create database: {err}")
                    raise
            raise

    def add_expense_to_db(date, amount, description, category, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (%s, %s, %s, %s, %s)",
            (date, amount, description, category, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True

    def fetch_expenses_from_db(user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if user_id:
            cursor.execute("SELECT * FROM expenses WHERE user_id = %s ORDER BY date DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
        expenses = cursor.fetchall()
        cursor.close()
        conn.close()
        for e in expenses:
            if isinstance(e['date'], str):
                e['date'] = datetime.strptime(e['date'], "%Y-%m-%d")
        return expenses
        
    def get_expense_by_id(expense_id, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if user_id:
            cursor.execute("SELECT * FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
        else:
            cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
        expense = cursor.fetchone()
        cursor.close()
        conn.close()
        if expense and isinstance(expense['date'], str):
            expense['date'] = datetime.strptime(expense['date'], "%Y-%m-%d")
        return expense
        
    def update_expense_in_db(expense_id, date, amount, description, category, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                "UPDATE expenses SET date = %s, amount = %s, description = %s, category = %s WHERE id = %s AND user_id = %s",
                (date, amount, description, category, expense_id, user_id)
            )
        else:
            cursor.execute(
                "UPDATE expenses SET date = %s, amount = %s, description = %s, category = %s WHERE id = %s",
                (date, amount, description, category, expense_id)
            )
        conn.commit()
        cursor.close()
        conn.close()
        
    def delete_expense_from_db(expense_id, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
        else:
            cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        conn.commit()
        cursor.close()
        conn.close()

else:
    DB_PATH = "expenses.db"

    def get_db_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def add_expense_to_db(date, amount, description, category, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (?, ?, ?, ?, ?)",
            (date, amount, description, category, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def fetch_expenses_from_db(user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
        rows = cursor.fetchall()
        expenses = []
        for row in rows:
            # Get column names from the cursor description
            column_names = [column[0] for column in cursor.description]
            expenses.append({
                'id': row['id'],
                'date': datetime.strptime(row['date'], "%Y-%m-%d"),
                'amount': row['amount'],
                'description': row['description'],
                'category': row['category'],
                'user_id': row['user_id'] if 'user_id' in column_names else None
            })
        cursor.close()
        conn.close()
        return expenses
        
    def get_expense_by_id(expense_id, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        else:
            cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        row = cursor.fetchone()
        expense = None
        if row:
            # Get column names from the cursor description
            column_names = [column[0] for column in cursor.description]
            expense = {
                'id': row['id'],
                'date': datetime.strptime(row['date'], "%Y-%m-%d"),
                'amount': row['amount'],
                'description': row['description'],
                'category': row['category'],
                'user_id': row['user_id'] if 'user_id' in column_names else None
            }
        cursor.close()
        conn.close()
        return expense
        
    def update_expense_in_db(expense_id, date, amount, description, category, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                "UPDATE expenses SET date = ?, amount = ?, description = ?, category = ? WHERE id = ? AND user_id = ?",
                (date, amount, description, category, expense_id, user_id)
            )
        else:
            cursor.execute(
                "UPDATE expenses SET date = ?, amount = ?, description = ?, category = ? WHERE id = ?",
                (date, amount, description, category, expense_id)
            )
        conn.commit()
        cursor.close()
        conn.close()
        
    def delete_expense_from_db(expense_id, user_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        else:
            cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        cursor.close()
        conn.close()

def create_expenses_table():
    if USE_MYSQL:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    date DATE NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    description VARCHAR(255) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    user_id INT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()
            print("Expenses table created or already exists")
        except mysql.connector.Error as err:
            print(f"Error creating expenses table: {err}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()
            print("SQLite expenses table created or already exists")
        except sqlite3.Error as e:
            print(f"Error creating SQLite expenses table: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

def create_users_table():
    if USE_MYSQL:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    budget DECIMAL(10,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("MySQL users table created or already exists")
        except mysql.connector.Error as err:
            print(f"Error creating users table: {err}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    budget REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("SQLite users table created or already exists")
        except sqlite3.Error as e:
            print(f"Error creating SQLite users table: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

# Interest table functionality has been removed

# User management functions
def register_user(username, password, email):
    """Register a new user with hashed password"""
    # Hash the password with salt
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
                (username, password_hash, email)
            )
            conn.commit()
            user_id = cursor.lastrowid
            cursor.close()
            conn.close()
            return user_id
        except Exception as e:
            print(f"Error registering user: {e}")
            return None
    else:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            conn.commit()
            user_id = cursor.lastrowid
            cursor.close()
            conn.close()
            return user_id
        except Exception as e:
            print(f"Error registering user: {e}")
            return None

def authenticate_user(username, password):
    """Authenticate a user by username and password"""
    # Hash the password for comparison
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE username = %s AND password = %s",
                (username, password_hash)
            )
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None
    else:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password_hash)
            )
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None

def get_user_by_username(username):
    """Get user by username"""
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    else:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

def get_user_by_email(email):
    """Get user by email"""
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    else:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            return user
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Function to initialize the database and create all required tables
def initialize_database():
    try:
        # Ensure users table exists before expenses table (due to foreign key)
        create_users_table()
        # Ensure expenses table exists at startup
        create_expenses_table()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

# Initialize database when app starts
initialize_database()

HTML = """
<!doctype html>
<html lang="en">
<head>
    <title>Expense Tracker Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #a8c0ff 0%, #f8fafc 100%); }
        .card { border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
        .dashboard-header { background: linear-gradient(90deg, #1976d2 0%, #64b5f6 100%); color: #fff; border-radius: 16px 16px 0 0; }
        .progress { height: 20px; }
        .category-badge { font-size: 0.9em; }
    </style>
</head>
<body>
<div class="container py-4">
    <div class="dashboard-header p-4 mb-4 d-flex justify-content-between">
        <div>
            <h2><span>💰</span> Expense Tracker</h2>
            <p>Track your daily expenses and manage your budget effectively</p>
        </div>
        <div class="user-menu">
            <div class="dropdown">
                <button class="btn btn-light dropdown-toggle" type="button" id="userMenu" data-bs-toggle="dropdown" aria-expanded="false">
                    <i class="bi bi-person-circle me-1"></i> {{ username }}
                </button>
                <ul class="dropdown-menu" aria-labelledby="userMenu">
                    <li><a class="dropdown-item" href="/logout">Logout</a></li>
                </ul>
            </div>
        </div>
    </div>
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card text-center mb-2">
                <div class="card-body">
                    <h4>₹{{ today_total }}</h4>
                    <small>TODAY'S TOTAL</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center mb-2">
                <div class="card-body">
                    <h4>₹{{ month_total }}</h4>
                    <small>MONTHLY TOTAL</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center mb-2">
                <div class="card-body">
                    <h4>₹{{ budget }}</h4>
                    <small>MONTHLY BUDGET</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-center mb-2">
                <div class="card-body">
                    <h4>₹{{ remaining }}</h4>
                    <small>REMAINING</small>
                </div>
            </div>
        </div>
    </div>
    <div class="card mb-4">
        <div class="card-header">Budget Status</div>
        <div class="card-body">
            <div class="progress mb-2">
                <div class="progress-bar bg-info" role="progressbar" style="width: {{ budget_usage }}%;" aria-valuenow="{{ budget_usage }}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div>Budget Usage: {{ budget_usage }}%</div>
            <form method="post" action="/set_budget" class="mt-2 d-flex">
                <input type="number" name="budget" class="form-control me-2" placeholder="Set Budget (₹)" required>
                <button type="submit" class="btn btn-primary">Set Budget</button>
            </form>
        </div>
    </div>
    <div class="card mb-4">
        <div class="card-header">+ Add New Expense</div>
        <div class="card-body">
            <form method="post" action="/add" class="row g-3">
                <div class="col-12 col-md-2">
                    <input type="number" step="0.01" name="amount" class="form-control" placeholder="Amount (₹)" required>
                </div>
                <div class="col-12 col-md-3">
                    <input type="text" name="description" class="form-control" placeholder="Description" required>
                </div>
                <div class="col-12 col-md-3">
                    <select name="category" class="form-select" required>
                        <option value="">Select Category</option>
                        {% for cat in categories %}
                        <option value="{{ cat }}">{{ cat }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-12 col-md-2">
                    <input type="date" name="date" class="form-control" value="{{ today_str }}" required>
                </div>
                <div class="col-12 col-md-2">
                    <button type="submit" class="btn btn-success w-100">Add Expense</button>
                </div>
            </form>
        </div>
    </div>
    <div class="card mb-4">
        <div class="card-header">🔍 Search Expenses</div>
        <div class="card-body">
            <form method="get" action="/" class="d-flex">
                <input type="text" name="search" class="form-control me-2" placeholder="Search by description or category..." value="{{ search }}">
                <button type="submit" class="btn btn-primary me-2">Search</button>
                {% if search %}
                <a href="/" class="btn btn-secondary">Cancel</a>
                {% endif %}
            </form>
        </div>
    </div>
    <div class="card mb-4">
        <div class="card-header">📋 Today's Expenses</div>
        <div class="card-body">
            <form method="get" action="/" class="d-flex mb-3">
                <input type="date" name="expense_date" class="form-control me-2" value="{{ expense_date }}">
                <button type="submit" class="btn btn-primary">Filter</button>
                {% if expense_date and expense_date != today_str %}
                <a href="/" class="btn btn-secondary ms-2">Cancel</a>
                {% endif %}
            </form>
            {% if today_expenses %}
                <ul class="list-group">
                {% for expense in today_expenses %}
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge bg-secondary category-badge">{{ expense['category'] }}</span>
                            ₹{{ expense['amount'] }} - {{ expense['description'] }}
                        </div>
                        <div class="expense-actions">
                            <a href="/edit/{{ expense['id'] }}" class="action-icon edit-icon" title="Edit">
                                <i class="bi bi-pencil-square"></i>
                            </a>
                            <form method="post" action="/delete/{{ expense['id'] }}" class="d-inline" onsubmit="return confirm('Are you sure you want to delete this expense?');">
                                <button type="submit" class="action-icon delete-icon border-0 bg-transparent p-0" title="Delete">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </form>
                        </div>
                    </li>
                {% endfor %}
                </ul>
            {% else %}
                <div class="text-center text-muted">
                    <span style="font-size:2em;">&#128452;</span>
                    <br>No expenses found for this date
                </div>
            {% endif %}
        </div>
    </div>
    <div class="card mb-4">
        <div class="card-header">📊 Monthly Summary</div>
        <div class="card-body">
            <form method="get" action="/" class="d-flex mb-3">
                <input type="month" name="month_filter" class="form-control me-2" value="{{ month_filter }}">
                <button type="submit" class="btn btn-primary">Filter</button>
                {% if month_filter and month_filter != today_month %}
                <a href="/" class="btn btn-secondary ms-2">Cancel</a>
                {% endif %}
            </form>
            <h5>{{ month_str }}</h5>
            {% if month_expenses %}
                <style>
                    .expense-actions {
                        visibility: hidden;
                    }
                    .list-group-item:hover .expense-actions {
                        visibility: visible;
                    }
                    .action-icon {
                        cursor: pointer;
                        margin-left: 8px;
                        color: #6c757d;
                    }
                    .action-icon:hover {
                        transform: scale(1.2);
                    }
                    .edit-icon {
                        color: #0d6efd;
                    }
                    .delete-icon {
                        color: #dc3545;
                    }
                </style>
                <ul class="list-group">
                {% for expense in month_expenses %}
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge bg-info category-badge">{{ expense['category'] }}</span>
                            {{ expense['date'].strftime('%Y-%m-%d') }}: ₹{{ expense['amount'] }} - {{ expense['description'] }}
                        </div>
                        <div class="expense-actions">
                            <a href="/edit/{{ expense['id'] }}" class="action-icon edit-icon" title="Edit">
                                <i class="bi bi-pencil-square"></i>
                            </a>
                            <form method="post" action="/delete/{{ expense['id'] }}" class="d-inline" onsubmit="return confirm('Are you sure you want to delete this expense?');">
                                <button type="submit" class="action-icon delete-icon border-0 bg-transparent p-0" title="Delete">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </form>
                        </div>
                    </li>
                {% endfor %}
                </ul>
                <div class="mt-2">
                    <strong>{{ month_count }} expenses</strong> • Avg: ₹{{ month_avg }} • {{ month_usage }}%
                </div>
            {% else %}
                <div class="text-muted">No expenses found for this month</div>
            {% endif %}
        </div>
    </div>
</div>

<!-- Bootstrap JS Bundle -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email')
        
        # Validate input
        if not username or not password or not email or not confirm_password:
            flash('All fields are required', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
            
        # Check if username already exists
        if get_user_by_username(username):
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
            
        # Check if email already exists
        if get_user_by_email(email):
            flash('Email already exists', 'error')
            return redirect(url_for('register'))
            
        # Register user
        user_id = register_user(username, password, email)
        if user_id:
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed', 'error')
            return redirect(url_for('register'))
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Register - Expense Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            .auth-container {
                max-width: 500px;
                margin: 50px auto;
            }
        </style>
    </head>
    <body>
        <div class="container auth-container">
            <div class="card">
                <div class="card-header">
                    <h3 class="text-center">Register</h3>
                </div>
                <div class="card-body">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                                    {{ message }}
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <form action="/register" method="post">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                        <div class="mb-3">
                            <label for="confirm_password" class="form-label">Confirm Password</label>
                            <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                        </div>
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary">Register</button>
                        </div>
                    </form>
                    <div class="mt-3 text-center">
                        <p>Already have an account? <a href="/login">Login</a></p>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Validate input
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('login'))
            
        # Authenticate user
        user = authenticate_user(username, password)
        if user:
            # Set session variables
            session['user_id'] = user['id'] if USE_MYSQL else user['id']
            session['username'] = username
            flash(f'Welcome back, {username}!', 'success')
            
            # Redirect to next page or index
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - Expense Tracker</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            .auth-container {
                max-width: 500px;
                margin: 50px auto;
            }
        </style>
    </head>
    <body>
        <div class="container auth-container">
            <div class="card">
                <div class="card-header">
                    <h3 class="text-center">Login</h3>
                </div>
                <div class="card-body">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">
                                    {{ message }}
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <form action="/login" method="post">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                        <div class="d-grid gap-2">
                            <button type="submit" class="btn btn-primary">Login</button>
                        </div>
                    </form>
                    <div class="mt-3 text-center">
                        <p>Don't have an account? <a href="/register">Register</a></p>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    ''')

@app.route('/logout')
def logout():
    # Clear session
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
@login_required
def index():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    today_month = today.strftime("%Y-%m")
    month_str = today.strftime("%B, %Y")
    search = request.args.get('search', '').lower()
    expense_date = request.args.get('expense_date', today_str)
    month_filter = request.args.get('month_filter', today_month)
    user_id = session.get('user_id')

    all_expenses = fetch_expenses_from_db(user_id)

    filtered_expenses = all_expenses
    if search:
        filtered_expenses = [
            e for e in all_expenses
            if search in e['description'].lower() or search in e['category'].lower()
        ]

    # Today's expenses filtering
    try:
        filter_date = datetime.strptime(expense_date, "%Y-%m-%d")
    except Exception:
        filter_date = today

    today_expenses = [e for e in filtered_expenses if e['date'].strftime("%Y-%m-%d") == filter_date.strftime("%Y-%m-%d")]
    today_total = sum(e['amount'] for e in today_expenses)

    # Monthly summary filtering
    try:
        filter_month = datetime.strptime(month_filter, "%Y-%m")
    except Exception:
        filter_month = today

    month_expenses = [
        e for e in filtered_expenses
        if e['date'].strftime("%Y-%m") == filter_month.strftime("%Y-%m")
    ]
    month_str = filter_month.strftime("%B, %Y")
    month_total = sum(e['amount'] for e in month_expenses)
    
    # Get user's budget from database
    user_budget = get_budget_from_db(user_id)
    remaining = user_budget - month_total
    budget_usage = round((month_total / user_budget) * 100, 2) if user_budget else 0
    month_count = len(month_expenses)
    month_avg = round(month_total / month_count, 2) if month_count else 0
    month_usage = budget_usage

    return render_template_string(
        HTML,
        today_total=f"{today_total:.2f}",
        month_total=f"{month_total:.2f}",
        budget=f"{user_budget:.2f}",
        remaining=f"{remaining:.2f}",
        budget_usage=budget_usage,
        today_str=today_str,
        month_str=month_str,
        categories=CATEGORIES,
        today_expenses=today_expenses,
        expense_date=expense_date,
        month_expenses=month_expenses,
        month_count=month_count,
        month_avg=f"{month_avg:.2f}",
        month_usage=month_usage,
        search=search,
        month_filter=month_filter,
        today_month=today_month,
        username=session.get('username')
    )

@app.route('/add', methods=['POST'])
@login_required
def add_expense():
    try:
        date = request.form['date']
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        user_id = session.get('user_id')
        add_expense_to_db(date, amount, description, category, user_id)
    except Exception as e:
        print(f"Error adding expense: {e}")
    return redirect(url_for('index'))

@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    user_id = session.get('user_id')
    expense = get_expense_by_id(expense_id, user_id)
    if not expense:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            date = request.form['date']
            amount = float(request.form['amount'])
            description = request.form['description']
            category = request.form['category']
            update_expense_in_db(expense_id, date, amount, description, category, user_id)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error updating expense: {e}")
    
    # For GET request, render the edit form
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    expense_date = expense['date'].strftime("%Y-%m-%d") if expense['date'] else today_str
    
    return render_template_string(
        '''
        <!doctype html>
        <html lang="en">
        <head>
            <title>Edit Expense</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
            <style>
                body { background: linear-gradient(135deg, #a8c0ff 0%, #f8fafc 100%); padding: 20px; }
                .card { border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
                .dashboard-header { background: linear-gradient(90deg, #1976d2 0%, #64b5f6 100%); color: #fff; border-radius: 16px 16px 0 0; }
            </style>
        </head>
        <body>
        <div class="container py-4">
            <div class="dashboard-header p-4 mb-4">
                <h2><span>✏️</span> Edit Expense</h2>
            </div>
            <div class="card mb-4">
                <div class="card-body">
                    <form method="post" action="/edit/{{ expense_id }}" class="row g-3">
                        <div class="col-12 col-md-3">
                            <label for="amount" class="form-label">Amount (₹)</label>
                            <input type="number" step="0.01" name="amount" id="amount" class="form-control" value="{{ amount }}" required>
                        </div>
                        <div class="col-12 col-md-3">
                            <label for="description" class="form-label">Description</label>
                            <input type="text" name="description" id="description" class="form-control" value="{{ description }}" required>
                        </div>
                        <div class="col-12 col-md-2">
                            <label for="category" class="form-label">Category</label>
                            <select name="category" id="category" class="form-select" required>
                                {% for cat in categories %}
                                <option value="{{ cat }}" {% if cat == current_category %}selected{% endif %}>{{ cat }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-12 col-md-2">
                            <label for="date" class="form-label">Date</label>
                            <input type="date" name="date" id="date" class="form-control" value="{{ expense_date }}" required>
                        </div>
                        <div class="col-12 mt-4">
                            <button type="submit" class="btn btn-primary">Update Expense</button>
                            <a href="/" class="btn btn-secondary ms-2">Cancel</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        </body>
        </html>
        ''',
        expense_id=expense_id,
        amount=expense['amount'],
        description=expense['description'],
        current_category=expense['category'],
        expense_date=expense_date,
        categories=CATEGORIES
    )

@app.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    try:
        user_id = session.get('user_id')
        delete_expense_from_db(expense_id, user_id)
    except Exception as e:
        print(f"Error deleting expense: {e}")
    return redirect(url_for('index'))

def get_budget_from_db(user_id=None):
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            if user_id:
                cursor.execute("SELECT budget FROM users WHERE id = %s", (user_id,))
            else:
                return 0
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result['budget'] if result and result['budget'] else 0
        except Exception as e:
            print(f"Error getting budget: {e}")
            return 0
    else:
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT budget FROM users WHERE id = ?", (user_id,))
            else:
                return 0
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result['budget'] if result else 0
        except Exception as e:
            print(f"Error getting budget: {e}")
            return 0

def update_budget_in_db(budget, user_id):
    if USE_MYSQL:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET budget = %s WHERE id = %s", (budget, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating budget: {e}")
            return False
    else:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET budget = ? WHERE id = ?", (budget, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating budget: {e}")
            return False

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    try:
        user_id = session.get('user_id')
        budget = float(request.form['budget'])
        update_budget_in_db(budget, user_id)
        flash('Budget updated successfully!', 'success')
    except Exception as e:
        print(f"Error setting budget: {e}")
        flash('Error updating budget', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)