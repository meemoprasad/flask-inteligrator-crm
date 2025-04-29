import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime
import pandas as pd # Import pandas for Excel export
from io import BytesIO # Import BytesIO for Excel export

app = Flask(__name__)
# Replace with a strong, unique secret key
app.secret_key = 'your_super_secret_key_replace_me'

# Define available pages for access control
AVAILABLE_PAGES = ['dashboard', 'customer_management', 'onboarded_customers'] # Add other pages as needed

# ---------- DATABASE SETUP ----------
# Main database for storing user credentials and details
MAIN_DB = 'main.db'

def init_main_db():
    """Initializes the main database and the users table."""
    conn = sqlite3.connect(MAIN_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
            name TEXT,
            phone TEXT,
            email TEXT,
            business_name TEXT,
            address TEXT,
            state TEXT,
            country TEXT,
            page_access TEXT DEFAULT 'dashboard' -- Comma-separated page names
        )
    ''')
    conn.commit()
    conn.close()

def init_user_db(username):
    """Initializes a new database for a specific user."""
    user_db_name = f"{username}.db"
    conn = sqlite3.connect(user_db_name)
    cursor = conn.cursor()
    # Create tables specific to the user's data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT UNIQUE NOT NULL, -- Assuming customer_id is distinct
            name TEXT,
            company TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            industry TEXT,
            core_business TEXT,
            contact TEXT,
            email TEXT,
            onboarding_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            reminder_datetime TEXT,
            message TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            remark TEXT,
            timestamp TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    ''')
    conn.commit()
    conn.close()

init_main_db()

# ---------- AUTH ROUTES ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check for the hardcoded admin login
        if username == 'inteligrator' and password == 'Bankimongra@123':
            session['username'] = username
            session['role'] = 'admin'
            # Admin has access to all defined pages
            session['page_access'] = AVAILABLE_PAGES + ['user_management', 'create_user', 'edit_user', 'delete_user']
            # Admin also gets a database named 'inteligrator.db'
            if not os.path.exists(f"{username}.db"):
                 init_user_db(username)
            return redirect(url_for('dashboard'))

        # Check in the main database for other users
        conn = sqlite3.connect(MAIN_DB)
        cursor = conn.cursor()
        # Select all columns including the new ones
        cursor.execute("SELECT username, password, role, page_access FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and user[1] == password:  # user[1] is the password from the database
            session['username'] = user[0]  # Set session username
            session['role'] = user[2]  # Set session role
            session['page_access'] = user[3].split(',') if user[3] else [] # page_access as a list

            # Check if the user's specific database exists, create if not
            if not os.path.exists(f"{user[0]}.db"):
                init_user_db(user[0])

            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the current user."""
    session.pop('username', None)
    session.pop('role', None)
    session.pop('page_access', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

# ---------- ACCESS CONTROL DECORATOR ----------
def login_required(f):
    """Decorator to require a logged-in user."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require an admin user."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session.get('role') != 'admin':
            flash('Unauthorized access.')
            return redirect(url_for('dashboard')) # Redirect to dashboard or login
        return f(*args, **kwargs)
    return decorated_function

def page_access_required(page_name):
    """Decorator to require access to a specific page."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                flash('Please log in to access this page.')
                return redirect(url_for('login'))
            # Admin has access to all pages implicitly
            if session.get('role') == 'admin':
                return f(*args, **kwargs)
            # Check if the page_name is in the user's page_access list
            if page_name not in session.get('page_access', []):
                flash(f'You do not have access to the {page_name.replace("_", " ").title()} page.')
                return redirect(url_for('dashboard')) # Redirect to dashboard
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------- USER MANAGEMENT (ADMIN ONLY) ----------
@app.route('/user_management')
@admin_required
def user_management():
    """Displays a list of users (admin only)."""
    conn = sqlite3.connect(MAIN_DB)
    cursor = conn.cursor()
    # Exclude the hardcoded admin from this list and FETCH ALL COLUMNS including password
    cursor.execute("SELECT username, password, role, page_access, name, phone, email, business_name, address, state, country FROM users WHERE username != 'inteligrator'")
    users_data = cursor.fetchall()
    conn.close()

    users_list = []
    for user in users_data:
        users_list.append({
            'username': user[0],
            'password': user[1], # Include password
            'role': user[2],
            'page_access': user[3],
            'name': user[4],
            'phone': user[5],
            'email': user[6],
            'business_name': user[7],
            'address': user[8],
            'state': user[9],
            'country': user[10]
        })

    return render_template('user_management.html', users=users_list)

@app.route('/create_user', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Handles user creation (admin only)."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        business_name = request.form.get('business_name')
        address = request.form.get('address')
        state = request.form.get('state')
        country = request.form.get('country')
        # Get page access as a list and join with comma
        page_access_list = request.form.getlist('page_access')
        page_access = ','.join(page_access_list) if page_access_list else 'dashboard'


        conn = sqlite3.connect(MAIN_DB)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (username, password, role, name, phone, email, business_name, address, state, country, page_access)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, password, role, name, phone, email, business_name, address, state, country, page_access))
            conn.commit()
            flash(f'User "{username}" created successfully.')
            # Initialize the database for the new user immediately upon creation
            init_user_db(username)
            return redirect(url_for('user_management'))
        except sqlite3.IntegrityError:
            flash(f'Error: Username "{username}" already exists.')
        finally:
            conn.close()

    return render_template('user_creation.html', available_pages=AVAILABLE_PAGES)

@app.route('/edit_user/<username>', methods=['GET', 'POST'])
@admin_required
def edit_user(username):
    """Handles editing user details (admin only)."""
    conn = sqlite3.connect(MAIN_DB)
    cursor = conn.cursor()
    # Fetch user details excluding the hardcoded admin
    cursor.execute("SELECT username, role, page_access FROM users WHERE username = ? AND username != 'inteligrator'", (username,))
    user = cursor.fetchone()

    if not user:
        flash('User not found.')
        conn.close()
        return redirect(url_for('user_management'))

    user_data = {'username': user[0], 'role': user[1], 'page_access': user[2].split(',') if user[2] else []} # Split page_access into a list

    if request.method == 'POST':
        new_password = request.form['password']
        # Get page access as a list and join with comma
        new_page_access_list = request.form.getlist('page_access')
        new_page_access = ','.join(new_page_access_list) if new_page_access_list else 'dashboard'


        cursor.execute('''
            UPDATE users SET password = ?, page_access = ? WHERE username = ?
        ''', (new_password, new_page_access, username))
        conn.commit()
        flash(f'User "{username}" updated successfully.')
        conn.close()
        return redirect(url_for('user_management'))

    conn.close()
    return render_template('edit_user.html', user=user_data, available_pages=AVAILABLE_PAGES)


@app.route('/delete_user/<username>')
@admin_required
def delete_user(username):
    """Handles deleting a user (admin only)."""
    conn = sqlite3.connect(MAIN_DB)
    cursor = conn.cursor()
    # Prevent deleting the hardcoded admin
    if username == 'inteligrator':
        flash('Cannot delete the primary admin user.')
        conn.close()
        return redirect(url_for('user_management'))

    try:
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        flash(f'User "{username}" deleted successfully.')
        # Optionally, delete the user's database file
        user_db_name = f"{username}.db"
        if os.path.exists(user_db_name):
            os.remove(user_db_name)
            print(f"Deleted database file: {user_db_name}") # Log for debugging
    except Exception as e:
        flash(f'Error deleting user "{username}": {e}')
        print(f"Error deleting user {username}: {e}") # Log for debugging
    finally:
        conn.close()

    return redirect(url_for('user_management'))

# ---------- CUSTOMER MANAGEMENT (USER SPECIFIC) ----------
def get_user_db():
    """Returns the database connection for the current user."""
    if 'username' not in session:
        return None
    username = session['username']
    user_db_name = f"{username}.db"
    # Check if the user's database file exists before connecting
    if not os.path.exists(user_db_name):
        # This should ideally not happen if init_user_db is called on login/creation,
        # but as a fallback, we can create it here.
        init_user_db(username)
    return sqlite3.connect(user_db_name)

@app.route('/dashboard')
@login_required
def dashboard():
    """Displays the user dashboard."""
    return render_template('dashboard.html')

@app.route('/customer_management', methods=['GET', 'POST'])
@page_access_required('customer_management')
@login_required
def customer_management():
    """Handles customer management for the current user."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()

    if request.method == 'POST':
        # This block seems redundant as /add_customer is a separate route
        pass # Keep for now in case of future form submissions here

    search_query = request.args.get('search')
    industry_filter = request.args.get('industry')
    city_filter = request.args.get('city')

    query = "SELECT rowid, * FROM customers WHERE 1=1"
    params = []

    if search_query:
        query += " AND (name LIKE ? OR company LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    if industry_filter:
        query += " AND industry LIKE ?"
        params.append(f"%{industry_filter}%")
    if city_filter:
        query += " AND city LIKE ?"
        params.append(f"%{city_filter}%")

    cursor.execute(query, params)
    customers = cursor.fetchall()
    conn.close()

    return render_template('customer_management.html', customers=customers)

@app.route('/add_customer', methods=['POST'])
@page_access_required('customer_management')
@login_required
def add_customer():
    """Adds a new customer to the current user's database."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    cursor = conn.cursor()

    name = request.form['name']
    company = request.form['company']
    address = request.form['address']
    city = request.form['city']
    state = request.form['state']
    country = request.form['country']
    industry = request.form['industry']
    core_business = request.form['core_business']
    contact = request.form['contact']
    email = request.form.get('email')
    onboarding_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Generate a simple customer ID (can be improved)
    customer_id = f"{company[:3].upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        cursor.execute('''
            INSERT INTO customers (customer_id, name, company, address, city, state, country, industry, core_business, contact, email, onboarding_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, name, company, address, city, state, country, industry, core_business, contact, email, onboarding_date))
        conn.commit()
        flash('Customer added successfully!')
    except sqlite3.IntegrityError:
        flash('Error: Customer ID already exists.')
    except Exception as e:
        flash(f'Error adding customer: {e}')
    finally:
        conn.close()

    return redirect(url_for('customer_management'))


@app.route('/edit_customer/<int:id>', methods=['GET', 'POST'])
@page_access_required('customer_management')
@login_required
def edit_customer(id):
    """Handles editing a customer for the current user."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        company = request.form['company']
        address = request.form['address']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        industry = request.form['industry']
        core_business = request.form['core_business']
        contact = request.form['contact']
        email = request.form.get('email')

        try:
            cursor.execute('''
                UPDATE customers SET name = ?, company = ?, address = ?, city = ?, state = ?, country = ?, industry = ?, core_business = ?, contact = ?, email = ?
                WHERE rowid = ?
            ''', (name, company, address, city, state, country, industry, core_business, contact, email, id))
            conn.commit()
            flash('Customer updated successfully!')
        except Exception as e:
            flash(f'Error updating customer: {e}')
        finally:
            conn.close()
        return redirect(url_for('customer_management'))

    # GET request
    cursor.execute("SELECT rowid, * FROM customers WHERE rowid = ?", (id,))
    customer = cursor.fetchone()
    conn.close()

    if not customer:
        flash('Customer not found.')
        return redirect(url_for('customer_management'))

    return render_template('edit_customer.html', customer=customer)

@app.route('/delete_customer/<int:id>')
@page_access_required('customer_management')
@login_required
def delete_customer(id):
    """Deletes a customer from the current user's database."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM customers WHERE rowid = ?", (id,))
        conn.commit()
        flash('Customer deleted successfully!')
    except Exception as e:
        flash(f'Error deleting customer: {e}')
    finally:
        conn.close()

    return redirect(url_for('customer_management'))

@app.route('/onboarded_customers')
@page_access_required('onboarded_customers')
@login_required
def onboarded_customers():
    """Displays onboarded customers with reminders and follow-ups for the current user."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()

    cursor.execute("SELECT rowid, * FROM customers")
    customers = cursor.fetchall()

    # Fetch reminders and followups based on customer rowid
    cursor.execute("SELECT r.rowid, r.customer_id, r.reminder_datetime, r.message FROM reminders r JOIN customers c ON r.customer_id = c.rowid")
    reminders = cursor.fetchall()

    cursor.execute("SELECT f.rowid, f.customer_id, f.remark, f.timestamp FROM followups f JOIN customers c ON f.customer_id = c.rowid ORDER BY f.timestamp DESC")
    followups = cursor.fetchall()

    conn.close()

    return render_template('onboarded_customers.html', customers=customers, reminders=reminders, followups=followups)

@app.route('/set_reminder/<int:customer_rowid>', methods=['POST'])
@page_access_required('onboarded_customers')
@login_required
def set_reminder(customer_rowid):
    """Sets a reminder for a customer in the current user's database."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    cursor = conn.cursor()

    reminder_date_time_str = request.form['reminder_date']
    reminder_message = request.form['reminder_message']

    try:
        # Insert reminder using the customer's rowid
        cursor.execute('''
            INSERT INTO reminders (customer_id, reminder_datetime, message)
            VALUES (?, ?, ?)
        ''', (customer_rowid, reminder_date_time_str, reminder_message))
        conn.commit()
        flash('Reminder set successfully!')
    except Exception as e:
        flash(f'Error setting reminder: {e}')
    finally:
        conn.close()

    return redirect(url_for('onboarded_customers'))

@app.route('/add_followup/<int:customer_rowid>', methods=['POST'])
@page_access_required('onboarded_customers')
@login_required
def add_followup(customer_rowid):
    """Adds a follow-up remark for a customer in the current user's database."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))
    cursor = conn.cursor()

    followup_text = request.form['followup_text']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        # Insert follow-up using the customer's rowid
        cursor.execute('''
            INSERT INTO followups (customer_id, remark, timestamp)
            VALUES (?, ?, ?)
        ''', (customer_rowid, followup_text, timestamp))
        conn.commit()
        flash('Follow-up added successfully!')
    except Exception as e:
        flash(f'Error adding follow-up: {e}')
    finally:
        conn.close()

    return redirect(url_for('onboarded_customers'))

@app.route('/check_reminders')
@login_required
def check_reminders():
    """Checks for upcoming reminders for the current user."""
    conn = get_user_db()
    if conn is None:
        return jsonify([]) # Return empty list if no user DB

    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Select reminders that are due now or in the past, joining with customers to get the name
    cursor.execute('''
        SELECT r.rowid, c.name, r.message
        FROM reminders r
        JOIN customers c ON r.customer_id = c.rowid
        WHERE r.reminder_datetime <= ?
    ''', (now,))
    reminders_due = cursor.fetchall()

    # In a real application, you would delete or mark these reminders as triggered
    # For this example, we'll just return them

    reminders_list = []
    for reminder in reminders_due:
        reminders_list.append({
            'reminder_id': reminder['rowid'],
            'customer_name': reminder['name'],
            'reminder_message': reminder['message']
        })

    conn.close()
    return jsonify(reminders_list)

@app.route('/download_excel')
@page_access_required('customer_management') # Or whichever page grants download access
@login_required
def download_excel():
    """Downloads customer data as an Excel file for the current user."""
    conn = get_user_db()
    if conn is None:
        flash('Database connection error.')
        return redirect(url_for('login'))

    try:
        cursor = conn.cursor()
        # Select all columns from the customers table
        cursor.execute("SELECT * FROM customers")
        rows = cursor.fetchall()
        # Get column names
        col_names = [description[0] for description in cursor.description]

        conn.close()

        if not rows:
            flash("No customer data to export.")
            return redirect(url_for('customer_management'))

        df = pd.DataFrame(rows, columns=col_names)

        # Create a BytesIO object to save the Excel file in memory
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Customers')
        writer.close() # Use close() instead of save() for newer pandas/xlsxwriter
        output.seek(0)

        from flask import send_file
        return send_file(output, download_name=f'{session["username"]}_customers.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except ImportError:
        flash("Required libraries (pandas, xlsxwriter) not installed for Excel export.")
        if conn:
            conn.close()
        return redirect(url_for('customer_management'))
    except Exception as e:
        flash(f"Error during Excel export: {e}")
        if conn:
            conn.close()
        return redirect(url_for('customer_management'))


# Placeholder for reset_password - needs proper implementation (e.g., sending email with a reset link)
@app.route('/reset_password', methods=['POST'])
def reset_password():
    """Placeholder for password reset functionality."""
    # This is a placeholder. A real password reset would involve:
    # 1. Generating a reset token.
    # 2. Storing the token and its expiry time in the database.
    # 3. Emailing the user a link with the token.
    # 4. A route to handle the reset link, verify the token, and allow password change.
    flash("Password reset functionality is not fully implemented in this example.")
    return jsonify({"message": "Password reset functionality is not fully implemented."}), 501 # Not Implemented


# ---------- MAIN ----------
if __name__ == '__main__':
    # Ensure the main database is initialized on startup
    init_main_db()
    app.run(debug=True)
