import os
import sqlite3
import mysql.connector
from urllib.parse import urlparse
from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Other"]
budget = 0

USE_MYSQL = os.environ.get('USE_MYSQL', '0') == '1'

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
        return mysql.connector.connect(**db_config)

    def add_expense_to_db(date, amount, description, category):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (date, amount, description, category) VALUES (%s, %s, %s, %s)",
            (date, amount, description, category)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def fetch_expenses_from_db():
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses")
        expenses = cursor.fetchall()
        cursor.close()
        conn.close()
        for e in expenses:
            if isinstance(e['date'], str):
                e['date'] = datetime.strptime(e['date'], "%Y-%m-%d")
        return expenses

else:
    DB_PATH = "expenses.db"

    def get_db_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def add_expense_to_db(date, amount, description, category):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (date, amount, description, category) VALUES (?, ?, ?, ?)",
            (date, amount, description, category)
        )
        conn.commit()
        cursor.close()
        conn.close()

    def fetch_expenses_from_db():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses")
        rows = cursor.fetchall()
        expenses = []
        for row in rows:
            expenses.append({
                'id': row['id'],
                'date': datetime.strptime(row['date'], "%Y-%m-%d"),
                'amount': row['amount'],
                'description': row['description'],
                'category': row['category']
            })
        cursor.close()
        conn.close()
        return expenses

def create_expenses_table():
    if USE_MYSQL:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description VARCHAR(255) NOT NULL,
                category VARCHAR(50) NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

def create_tables():
    conn = get_db_connection()  # Use your existing connection function
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal REAL NOT NULL,
            rate REAL NOT NULL,
            time REAL NOT NULL,
            interest REAL NOT NULL,
            calculated_on TEXT NOT NULL
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Ensure table exists at startup
create_expenses_table()
create_tables()

HTML = """
<!doctype html>
<html lang="en">
<head>
    <title>Expense Tracker Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
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
    <div class="dashboard-header p-4 mb-4">
        <h2><span>💰</span> Expense Tracker</h2>
        <p>Track your daily expenses and manage your budget effectively</p>
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
                    <li class="list-group-item">
                        <span class="badge bg-secondary category-badge">{{ expense['category'] }}</span>
                        ₹{{ expense['amount'] }} - {{ expense['description'] }}
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
                <ul class="list-group">
                {% for expense in month_expenses %}
                    <li class="list-group-item">
                        <span class="badge bg-info category-badge">{{ expense['category'] }}</span>
                        {{ expense['date'].strftime('%Y-%m-%d') }}: ₹{{ expense['amount'] }} - {{ expense['description'] }}
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
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    today_month = today.strftime("%Y-%m")
    month_str = today.strftime("%B, %Y")
    search = request.args.get('search', '').lower()
    expense_date = request.args.get('expense_date', today_str)
    month_filter = request.args.get('month_filter', today_month)

    all_expenses = fetch_expenses_from_db()

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
    remaining = budget - month_total
    budget_usage = round((month_total / budget) * 100, 2) if budget else 0
    month_count = len(month_expenses)
    month_avg = round(month_total / month_count, 2) if month_count else 0
    month_usage = budget_usage

    return render_template_string(
        HTML,
        today_total=f"{today_total:.2f}",
        month_total=f"{month_total:.2f}",
        budget=f"{budget:.2f}",
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
        today_month=today_month
    )

@app.route('/add', methods=['POST'])
def add_expense():
    try:
        date = request.form['date']
        amount = float(request.form['amount'])
        description = request.form['description']
        category = request.form['category']
        add_expense_to_db(date, amount, description, category)
    except Exception:
        pass
    return redirect(url_for('index'))

@app.route('/set_budget', methods=['POST'])
def set_budget():
    global budget
    try:
        budget = float(request.form['budget'])
    except Exception:
        pass
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)