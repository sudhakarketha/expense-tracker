# Import necessary libraries
import os
import sys
import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
# Import dateutil parser for flexible date parsing
from dateutil import parser

# Custom JSON encoder to handle Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(CustomJSONEncoder, self).default(obj)

# Try to import MySQL connector, but don't fail if it's not available
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Parse DATABASE_URL if provided (Clever Cloud format)
if DATABASE_URL:
    # Parse the database URL
    try:
        print(f"Attempting to parse DATABASE_URL: {DATABASE_URL[:10]}...")
        
        # Handle the exact Clever Cloud MySQL URL format from the environment variable
        if DATABASE_URL.startswith('mysql://u9thvqovg:wCakTLfiBIvZcJGuZgWrab3l6kultvvcl5akzxtfg-mysql'):
            print("Detected exact Clever Cloud MySQL URL format from environment variable")
            # Extract the specific parts from the known format
            MYSQL_USER = 'u9thvqovg'
            MYSQL_PASSWORD = 'wCakTLfiBIvZcJGuZgWrab3l6kultvvcl5akzxtfg'
            MYSQL_HOST = 'cl5akzxtfg-mysql.services.clever-cloud.com'
            MYSQL_PORT = 3306
            MYSQL_DATABASE = 'b3l6kultvvcl5akzxtfg'
            USE_MYSQL = True
            print(f"Using predefined Clever Cloud MySQL connection parameters: host={MYSQL_HOST}, user={MYSQL_USER}, database={MYSQL_DATABASE}")
        # Handle Clever Cloud MySQL URL format with triple slash
        elif DATABASE_URL.startswith('mysql:///'):
            # Special case for Clever Cloud format with triple slash
            # Format: mysql:///u9thvqovg:wCakTLfiBIvZcJGuZgWrab3l6kultvvcl5akzxtfg@cl5akzxtfg-mysql.services.clever-cloud.com:3306/b3l6kultvvcl5akzxtfg
            print("Detected Clever Cloud triple-slash MySQL URL format")
            url_without_prefix = DATABASE_URL[9:]  # Skip 'mysql:///' prefix
            
            # Extract credentials and host info
            if '@' in url_without_prefix:
                credentials, host_info = url_without_prefix.split('@', 1)
                
                # Extract username and password
                if ':' in credentials:
                    MYSQL_USER, MYSQL_PASSWORD = credentials.split(':', 1)
                    
                    # Extract host, port, and database
                    if ':' in host_info and '/' in host_info:
                        host_port, MYSQL_DATABASE = host_info.rsplit('/', 1)
                        MYSQL_HOST, port_str = host_port.rsplit(':', 1)
                        MYSQL_PORT = int(port_str)
                        USE_MYSQL = True
                        print(f"Parsed Clever Cloud MySQL URL: host={MYSQL_HOST}, user={MYSQL_USER}, database={MYSQL_DATABASE}")
                    else:
                        print("Failed to parse host, port, and database from Clever Cloud URL")
                else:
                    print("Failed to parse username and password from Clever Cloud URL")
            else:
                print("Failed to parse credentials and host info from Clever Cloud URL")
        elif DATABASE_URL.startswith('mysql:'):
            import re
            # Try standard format first: mysql://user:password@host:port/database
            pattern = r'mysql://([^:]+):([^@]+)@([^:/]+)(?::([0-9]+))?/(.+)'
            match = re.match(pattern, DATABASE_URL)
            
            if match:
                MYSQL_USER = match.group(1)
                MYSQL_PASSWORD = match.group(2)
                MYSQL_HOST = match.group(3)
                MYSQL_PORT = int(match.group(4) or 3306)
                MYSQL_DATABASE = match.group(5)
                USE_MYSQL = True
                print(f"Parsed MySQL connection from DATABASE_URL: host={MYSQL_HOST}, user={MYSQL_USER}, database={MYSQL_DATABASE}")
            else:
                # Try alternative format that might be used by Clever Cloud
                # Format might be like: mysql://u9thvqovg:wCakTLfiBIvZcJGuZgWrab3l6kultvvcl5akzxtfg-mysql.services.clever-cloud.com:3306/b3l6kultvvcl5akzxtfg
                print("Standard MySQL URL pattern didn't match, trying alternative parsing...")
                
                # Extract username and the rest
                parts = DATABASE_URL[8:].split(':', 1)  # Skip 'mysql://' prefix
                if len(parts) == 2:
                    username = parts[0]
                    rest = parts[1]
                    
                    # Extract password and the rest
                    parts = rest.split('@', 1)
                    if len(parts) == 2:
                        password = parts[0]
                        host_port_db = parts[1]
                        
                        # Extract host, port, and database
                        host_parts = host_port_db.split(':', 1)
                        if len(host_parts) == 2:
                            host = host_parts[0]
                            port_db = host_parts[1]
                            
                            # Extract port and database
                            port_db_parts = port_db.split('/', 1)
                            if len(port_db_parts) == 2:
                                port = int(port_db_parts[0])
                                database = port_db_parts[1]
                                
                                MYSQL_USER = username
                                MYSQL_PASSWORD = password
                                MYSQL_HOST = host
                                MYSQL_PORT = port
                                MYSQL_DATABASE = database
                                USE_MYSQL = True
                                print(f"Parsed MySQL connection using alternative method: host={MYSQL_HOST}, user={MYSQL_USER}, database={MYSQL_DATABASE}")
                            else:
                                print("Failed to parse port and database")
                        else:
                            print("Failed to parse host and port")
                    else:
                        print("Failed to parse password and host")
                else:
                    print("Failed to parse username")
                    
                if not USE_MYSQL:
                    print("Failed to parse DATABASE_URL with alternative method, falling back to default configuration")
                    USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 't')
                    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
                    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
                    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
                    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'expense_tracker')
        else:
            print(f"Unsupported database type in DATABASE_URL: {DATABASE_URL.split(':', 1)[0]}")
            USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 't')
            MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
            MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
            MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
            MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'expense_tracker')
    except Exception as e:
        print(f"Error parsing DATABASE_URL: {e}")
        USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 't')
        MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
        MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
        MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
        MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'expense_tracker')
else:
    USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() in ('true', '1', 't')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'expense_tracker')

SQLITE_DATABASE = os.environ.get('SQLITE_DATABASE', 'expenses.db')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
app.json_encoder = CustomJSONEncoder

# Database connection function
def get_db_connection():
    if USE_MYSQL and MYSQL_AVAILABLE:
        try:
            # Use MYSQL_PORT if defined, otherwise default to 3306
            port = getattr(sys.modules[__name__], 'MYSQL_PORT', 3306)
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                port=port
            )
            print(f"Successfully connected to MySQL database: {MYSQL_HOST}:{port}/{MYSQL_DATABASE}")
            return conn
        except mysql.connector.Error as err:
            print(f"MySQL Connection Error: {err}")
            # Fall back to SQLite if MySQL connection fails
            print("Falling back to SQLite...")
    
    # Use SQLite as fallback or primary option
    conn = sqlite3.connect(SQLITE_DATABASE)
    return conn

# Database initialization function
def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if USE_MYSQL and MYSQL_AVAILABLE:
            # Create users table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE
            )
            ''')
            # Create expenses table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                description VARCHAR(255) NOT NULL,
                category VARCHAR(100),
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')
        else:
            # SQLite version
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE
            )
            ''')
            print("SQLite users table created or already exists")
            
            # Drop and recreate expenses table to ensure correct schema
            cursor.execute("DROP TABLE IF EXISTS expenses")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')
            print("SQLite expenses table created or already exists")
        
        conn.commit()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
        raise

def add_expense_to_db(date, amount, description, category, user_id=None):
    print(f"Adding expense: {date}, {amount}, {description}, {category}, {user_id}")
    # Ensure date is in the correct format
    try:
        # If date is already a string in YYYY-MM-DD format, this will work
        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        date_str = date
    except (ValueError, TypeError):
        # If date is in another format or is a datetime object
        try:
            if isinstance(date, datetime):
                date_str = date.strftime('%Y-%m-%d')
            else:
                # Try to parse with dateutil
                parsed_date = parser.parse(str(date))
                date_str = parsed_date.strftime('%Y-%m-%d')
        except:
            # If all else fails, use today's date
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
    
    print(f"Normalized date for storage: {date_str}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        try:
            if USE_MYSQL and MYSQL_AVAILABLE:
                cursor.execute(
                    "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (%s, %s, %s, %s, %s)",
                    (date_str, amount, description, category, user_id)
                )
                # Get the last inserted ID in MySQL
                cursor.execute("SELECT LAST_INSERT_ID()")
                last_id = cursor.fetchone()[0]
            else:
                # SQLite uses ? placeholders instead of %s
                cursor.execute(
                    "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (?, ?, ?, ?, ?)",
                    (date_str, amount, description, category, user_id)
                )
                # Get the last inserted ID in SQLite
                last_id = cursor.lastrowid
        except Exception as err:
            # Check if this is an 'Unknown column' error for user_id
            if "no such column: user_id" in str(err) or "Unknown column 'user_id'" in str(err):
                print("Detected missing user_id column in add_expense_to_db, attempting to fix schema...")
                # Trigger migration to fix the schema
                migrate_database()
                # Try again with a new connection
                conn.close()
                conn = get_db_connection()
                cursor = conn.cursor()
                # Try again after migration
                if USE_MYSQL and MYSQL_AVAILABLE:
                    cursor.execute(
                        "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (%s, %s, %s, %s, %s)",
                        (date_str, amount, description, category, user_id)
                    )
                    # Get the last inserted ID in MySQL
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    last_id = cursor.fetchone()[0]
                else:
                    cursor.execute(
                        "INSERT INTO expenses (date, amount, description, category, user_id) VALUES (?, ?, ?, ?, ?)",
                        (date_str, amount, description, category, user_id)
                    )
                    # Get the last inserted ID in SQLite
                    last_id = cursor.lastrowid
            else:
                raise
        conn.commit()
        print(f"Expense added with ID: {last_id}")
        return last_id
    except Exception as err:
        print(f"Error adding expense: {err}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()

def fetch_expenses_from_db(user_id=None):
    conn = get_db_connection()
    try:
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor = conn.cursor(dictionary=True)
            if user_id:
                cursor.execute("SELECT * FROM expenses WHERE user_id = %s ORDER BY date DESC", (user_id,))
            else:
                cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
            expenses = cursor.fetchall()
            valid_expenses = []
            for e in expenses:
                if isinstance(e['date'], str):
                    e['date'] = datetime.strptime(e['date'], "%Y-%m-%d")
                # Ensure id is present and valid
                if 'id' not in e or e['id'] is None:
                    print(f"Warning: MySQL expense missing id: {e}")
                else:
                    valid_expenses.append(e)
            expenses = valid_expenses
        else:
            # SQLite doesn't have dictionary cursor, so we need to handle it differently
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,))
            else:
                cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
            rows = cursor.fetchall()
            expenses = []
            for row in rows:
                e = dict(row)
                if isinstance(e['date'], str):
                    e['date'] = datetime.strptime(e['date'], "%Y-%m-%d")
                # Ensure id is present and valid
                if 'id' not in e or e['id'] is None:
                    print(f"Warning: SQLite expense missing id: {e}")
                else:
                    expenses.append(e)
        return expenses
    except Exception as err:
        print(f"Error fetching expenses: {err}")
        # Check if this is an 'Unknown column' error
        if "no such column: user_id" in str(err) or "Unknown column 'user_id'" in str(err):
            print("Detected missing user_id column, attempting to fix schema...")
            # Trigger migration to fix the schema
            migrate_database()
            # Try again with a new connection
            conn.close()
            conn = get_db_connection()
            try:
                if USE_MYSQL and MYSQL_AVAILABLE:
                    cursor = conn.cursor(dictionary=True)
                else:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                # Try without user_id filter as fallback
                cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
                expenses = cursor.fetchall()
                for e in expenses:
                    if isinstance(e['date'], str):
                        e['date'] = datetime.strptime(e['date'], "%Y-%m-%d")
                return expenses
            except Exception as inner_err:
                print(f"Error in second attempt to fetch expenses: {inner_err}")
                return []
        return []
    finally:
        cursor.close()
        conn.close()

def update_expense_in_db(id, date, amount, description, category, user_id=None):
    # Ensure date is in the correct format
    try:
        # If date is already a string in YYYY-MM-DD format, this will work
        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        date_str = date
    except (ValueError, TypeError):
        # If date is in another format or is a datetime object
        try:
            if isinstance(date, datetime):
                date_str = date.strftime('%Y-%m-%d')
            else:
                # Try to parse with dateutil
                parsed_date = parser.parse(str(date))
                date_str = parsed_date.strftime('%Y-%m-%d')
        except:
            # If all else fails, use today's date
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
    
    print(f"Normalized date for update: {date_str}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        try:
            if USE_MYSQL and MYSQL_AVAILABLE:
                cursor.execute(
                    "UPDATE expenses SET date = %s, amount = %s, description = %s, category = %s, user_id = %s WHERE id = %s",
                    (date_str, amount, description, category, user_id, id)
                )
            else:
                # SQLite uses ? placeholders
                cursor.execute(
                    "UPDATE expenses SET date = ?, amount = ?, description = ?, category = ?, user_id = ? WHERE id = ?",
                    (date_str, amount, description, category, user_id, id)
                )
        except Exception as err:
            # Check if this is an 'Unknown column' error for user_id
            if "no such column: user_id" in str(err) or "Unknown column 'user_id'" in str(err):
                print("Detected missing user_id column in update_expense_in_db, attempting to fix schema...")
                # Trigger migration to fix the schema
                migrate_database()
                # Try again with a new connection
                conn.close()
                conn = get_db_connection()
                cursor = conn.cursor()
                # Try again after migration
                if USE_MYSQL and MYSQL_AVAILABLE:
                    cursor.execute(
                        "UPDATE expenses SET date = %s, amount = %s, description = %s, category = %s, user_id = %s WHERE id = %s",
                        (date_str, amount, description, category, user_id, id)
                    )
                else:
                    cursor.execute(
                        "UPDATE expenses SET date = ?, amount = ?, description = ?, category = ?, user_id = ? WHERE id = ?",
                        (date_str, amount, description, category, user_id, id)
                    )
            else:
                raise
        conn.commit()
        return True
    except Exception as err:
        print(f"Error updating expense: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def delete_expense_from_db(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute("DELETE FROM expenses WHERE id = %s", (id,))
        else:
            # SQLite uses ? placeholders
            cursor.execute("DELETE FROM expenses WHERE id = ?", (id,))
        conn.commit()
        return True
    except Exception as err:
        print(f"Error deleting expense: {err}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def migrate_database():
    """Migrate database schema to add user_id column if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_MYSQL and MYSQL_AVAILABLE:
            # Check if user_id column exists
            try:
                cursor.execute("SELECT user_id FROM expenses LIMIT 1")
                # If no error, column exists
                return
            except mysql.connector.Error:
                # Column doesn't exist, add it
                cursor.execute("ALTER TABLE expenses ADD COLUMN user_id INT")
                cursor.execute("ALTER TABLE expenses ADD FOREIGN KEY (user_id) REFERENCES users(id)")
        else:
            # SQLite version
            # Check if user_id column exists
            cursor.execute("PRAGMA table_info(expenses)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]  # Column name is at index 1
            
            if 'user_id' not in column_names:
                # Column doesn't exist, add it
                cursor.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER REFERENCES users(id)")
        
        conn.commit()
        print("Database migration completed successfully")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def verify_database_connection():
    """Verify that the database connection is working"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try a simple query
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute("SELECT 1")
        else:
            cursor.execute("SELECT 1")
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        print("Database connection verified successfully")
        return result is not None
    except Exception as e:
        print(f"Database connection verification failed: {e}")
        return False

def validate_database_schema():
    """Validate that the database schema is correct"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables exist
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            
            if 'expenses' not in table_names or 'users' not in table_names:
                print("Missing required tables")
                return False
            
            # Check expenses table schema
            cursor.execute("DESCRIBE expenses")
            columns = cursor.fetchall()
            column_names = [column[0] for column in columns]
            
            required_columns = ['id', 'date', 'amount', 'description', 'category']
            for col in required_columns:
                if col not in column_names:
                    print(f"Missing required column: {col}")
                    return False
        else:
            # SQLite version
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            
            if 'expenses' not in table_names or 'users' not in table_names:
                print("Missing required tables")
                return False
            
            # Check expenses table schema
            cursor.execute("PRAGMA table_info(expenses)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]  # Column name is at index 1
            
            required_columns = ['id', 'date', 'amount', 'description', 'category']
            for col in required_columns:
                if col not in column_names:
                    print(f"Missing required column: {col}")
                    return False
        
        cursor.close()
        conn.close()
        
        print("Database schema validation successful")
        return True
    except Exception as e:
        print(f"Database schema validation failed: {e}")
        return False

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    expenses = fetch_expenses_from_db(session.get('user_id'))
    # No need to filter expenses here as fetch_expenses_from_db now returns only valid expenses
    total = sum(expense['amount'] for expense in expenses)
    
    # Get today's date for filtering today's expenses
    # Use UTC time to avoid timezone issues in deployed environments
    today = datetime.utcnow()
    print(f"Today's UTC date: {today}")
    
    # Debug: Print all expense dates to check format
    for expense in expenses:
        print(f"Expense date: {expense['date']}, Type: {type(expense['date'])}")
    
    # Convert today to string format for more reliable comparison
    today_str = today.strftime('%Y-%m-%d')
    
    # Filter expenses for today only
    todays_expenses = []
    for expense in expenses:
        # Extract just the date part (YYYY-MM-DD) for comparison
        expense_date_str = ''
        
        # Handle datetime objects
        if isinstance(expense['date'], datetime):
            # Convert to UTC to match today's UTC time
            expense_date_str = expense['date'].strftime('%Y-%m-%d')
        # Handle string dates
        elif isinstance(expense['date'], str):
            # Try to parse the string to ensure it's in the correct format
            try:
                # First try the standard format
                parsed_date = datetime.strptime(expense['date'], '%Y-%m-%d')
                expense_date_str = expense['date']
            except ValueError:
                # If that fails, try more flexible parsing
                try:
                    parsed_date = parser.parse(expense['date'])
                    expense_date_str = parsed_date.strftime('%Y-%m-%d')
                except:
                    # If all parsing fails, use the string as is
                    expense_date_str = expense['date']
        
        # Debug output to help diagnose issues
        print(f"Comparing expense date: {expense_date_str} with today: {today_str}")
        
        # Compare the date strings - only exact matches count as today
        if expense_date_str == today_str:
            todays_expenses.append(expense)
            print(f"MATCH: Adding expense {expense['description']} to today's expenses")
    
    # Debug: Print today's expenses
    print(f"Found {len(todays_expenses)} expenses for today")
    for expense in todays_expenses:
        print(f"Today's expense: {expense['description']}, Date: {expense['date']}")
    
    
    # Group expenses by category for chart
    categories = {}
    categories_list = set()
    for expense in expenses:
        category = expense['category'] or 'Uncategorized'
        categories_list.add(category)
        if category in categories:
            categories[category] += expense['amount']
        else:
            categories[category] = expense['amount']
    
    return render_template('dashboard.html', 
                           expenses=todays_expenses, 
                           total=total,
                           categories=json.dumps(list(categories.keys())),
                           amounts=json.dumps(list(categories.values()), cls=CustomJSONEncoder),
                           categories_list=sorted(list(categories_list)))

@app.route('/total-expenses')
@login_required
def total_expenses():
    expenses = fetch_expenses_from_db(session.get('user_id'))
    total = sum(expense['amount'] for expense in expenses)
    
    # Group expenses by category for filtering
    categories_list = set()
    for expense in expenses:
        category = expense['category'] or 'Uncategorized'
        categories_list.add(category)
    
    return render_template('total_expenses.html', 
                           expenses=expenses, 
                           total=total,
                           categories_list=sorted(list(categories_list)))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        date = request.form['date']
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        
        expense_id = add_expense_to_db(date, amount, description, category, session.get('user_id'))
        
        if expense_id:
            flash(f'Expense added successfully with ID: {expense_id}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Error adding expense', 'danger')
    
    # Pass today's date to the template in the correct format
    # Use UTC time to avoid timezone issues in deployed environments
    today_date = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('add_expense.html', today_date=today_date)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    conn = get_db_connection()
    
    if USE_MYSQL and MYSQL_AVAILABLE:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE id = %s AND user_id = %s", (id, session.get('user_id')))
        expense = cursor.fetchone()
    else:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (id, session.get('user_id')))
        result = cursor.fetchone()
        expense = dict(result) if result else None
    
    cursor.close()
    conn.close()
    
    if not expense:
        flash('Expense not found or you do not have permission to edit it', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        date = request.form['date']
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        
        success = update_expense_in_db(id, date, amount, description, category, session.get('user_id'))
        
        if success:
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Error updating expense', 'danger')
    
    return render_template('edit_expense.html', expense=expense)

@app.route('/delete/<int:id>')
@login_required
def delete_expense(id):
    # Verify ownership before deletion
    conn = get_db_connection()
    
    if USE_MYSQL and MYSQL_AVAILABLE:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE id = %s AND user_id = %s", (id, session.get('user_id')))
        expense = cursor.fetchone()
    else:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?", (id, session.get('user_id')))
        expense = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not expense:
        flash('Expense not found or you do not have permission to delete it', 'danger')
        return redirect(url_for('dashboard'))
    
    success = delete_expense_from_db(id)
    
    if success:
        flash('Expense deleted successfully!', 'success')
    else:
        flash('Error deleting expense', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if USE_MYSQL and MYSQL_AVAILABLE:
                cursor.execute(
                    "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
                    (username, hashed_password, email)
                )
            else:
                cursor.execute(
                    "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                    (username, hashed_password, email)
                )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            if 'UNIQUE constraint' in str(e) or 'Duplicate entry' in str(e):
                flash('Username or email already exists', 'danger')
            else:
                flash(f'Error during registration: {e}', 'danger')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        
        if USE_MYSQL and MYSQL_AVAILABLE:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user:
                user = dict(user)
        
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    
    if USE_MYSQL and MYSQL_AVAILABLE:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (session.get('user_id'),))
        user = cursor.fetchone()
    else:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session.get('user_id'),))
        user = dict(cursor.fetchone()) if cursor.fetchone() else None
    
    cursor.close()
    conn.close()
    
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('profile.html', user=user)

@app.route('/api/expenses')
@login_required
def api_expenses():
    expenses = fetch_expenses_from_db(session.get('user_id'))
    # Convert datetime objects to strings for JSON serialization
    for expense in expenses:
        if isinstance(expense['date'], datetime):
            expense['date'] = expense['date'].strftime('%Y-%m-%d')
        # Convert Decimal objects to float for JSON serialization
        if isinstance(expense['amount'], Decimal):
            expense['amount'] = float(expense['amount'])
    return jsonify(expenses)

@app.route('/api/expenses/add', methods=['POST'])
@login_required
def api_add_expense():
    data = request.get_json()
    
    if not data or not all(key in data for key in ['date', 'amount', 'description']):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    success = add_expense_to_db(
        data['date'],
        float(data['amount']),
        data['description'],
        data.get('category'),
        session.get('user_id')
    )
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to add expense'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'ok'})

@app.route('/health/db')
def db_health_check():
    if verify_database_connection():
        db_info = {
            'status': 'ok', 
            'database': 'connected',
            'type': 'MySQL' if USE_MYSQL and MYSQL_AVAILABLE else 'SQLite',
        }
        
        # Add MySQL-specific info if using MySQL
        if USE_MYSQL and MYSQL_AVAILABLE:
            db_info.update({
                'host': MYSQL_HOST,
                'database': MYSQL_DATABASE,
                'user': MYSQL_USER
            })
        return jsonify(db_info)
    else:
        return jsonify({'status': 'error', 'database': 'disconnected'}), 500

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Function to log database configuration
def log_database_config():
    """Log the current database configuration for debugging"""
    if USE_MYSQL and MYSQL_AVAILABLE:
        print("\n=== Database Configuration ===")
        print(f"Database Type: MySQL")
        print(f"Host: {MYSQL_HOST}")
        print(f"Port: {getattr(sys.modules[__name__], 'MYSQL_PORT', 3306)}")
        print(f"User: {MYSQL_USER}")
        print(f"Database: {MYSQL_DATABASE}")
        print(f"Password: {'*' * len(MYSQL_PASSWORD) if MYSQL_PASSWORD else 'Not set'}")
        print("===========================\n")
    else:
        print("\n=== Database Configuration ===")
        print(f"Database Type: SQLite")
        print(f"Database File: {SQLITE_DATABASE}")
        print("===========================\n")

# Initialize database on startup
if __name__ == '__main__':
    log_database_config()
    initialize_database()
    # Get port from environment variable for cloud deployment (like Render)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)