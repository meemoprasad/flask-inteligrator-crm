from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, abort # Import abort
import sqlite3
from datetime import datetime
import pandas as pd
import io
import sys

app = Flask(__name__)

# Initialize database
# ... (init_db function remains the same)
def init_db():
    with sqlite3.connect("customers.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                name TEXT,
                company TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                country TEXT DEFAULT 'India',
                industry TEXT,
                core_business TEXT,
                contact TEXT,
                email TEXT,
                onboarding_date TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                reminder_date TEXT,
                reminder_message TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                followup_text TEXT,
                followup_date TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)
    print("Database initialized.")


# Dashboard (index page now)
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# Onboarding Customers
@app.route('/customer_management', )
def customer_management():
    search = request.args.get('search', '')
    industry_filter = request.args.get('industry', '')
    city_filter = request.args.get('city', '')

    customers = []
    try:
        with sqlite3.connect("customers.db") as conn:
            conn.row_factory = sqlite3.Row # Use Row factory to access columns by name if needed, though index is used in HTML
            cursor = conn.cursor()
            query = "SELECT * FROM customers WHERE 1=1"
            params = []

            if search:
                query += " AND (name LIKE ? OR company LIKE ?)"
                params.extend([f'%{search}%', f'%{search}%'])
            if industry_filter:
                query += " AND industry = ?"
                params.append(industry_filter)
            if city_filter:
                query += " AND city = ?"
                params.append(city_filter)

            query += " ORDER BY onboarding_date DESC"
            cursor.execute(query, params)
            customers = cursor.fetchall()

        return render_template('customer_management.html', customers=customers)

    except Exception as e:
        print(f"Error loading or rendering customer management page: {e}", file=sys.stderr)
        abort(500) # Return a server error


@app.route('/add_customer', methods=['POST'])
def add_customer():
    # ... (add_customer logic remains the same)
    try:
        name = request.form['name']
        company = request.form['company']
        address = request.form['address']
        city = request.form['city']
        state = request.form['state']
        country = request.form.get('country', 'India')
        industry = request.form['industry']
        core_business = request.form['core_business']
        contact = request.form['contact']
        email = request.form['email']
        onboarding_date = datetime.now().strftime('%Y-%m-%d')
        customer_id = generate_customer_id(name, onboarding_date)

        customer = (customer_id, name, company, address, city, state, country, industry, core_business, contact, email, onboarding_date)

        with sqlite3.connect("customers.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO customers (customer_id, name, company, address, city, state, country, industry, core_business, contact, email, onboarding_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, customer)
            conn.commit()

        return redirect(url_for('customer_management'))

    except Exception as e:
        print(f"Error adding customer: {e}", file=sys.stderr)
        abort(500) # Return a server error


# ... (generate_customer_id function remains the same)
def generate_customer_id(name, date_str):
    initials = ''.join([x[0] for x in name.strip().upper().split()])[:3]
    date_part = date_str.replace('-', '')[-6:]
    return f"{initials}{date_part}".ljust(6, 'X')


# Implement the route to display the edit customer form
@app.route('/edit_customer/<int:id>')
def edit_customer(id):
    try:
        with sqlite3.connect("customers.db") as conn:
            conn.row_factory = sqlite3.Row # Use Row factory for easier access
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers WHERE id = ?", (id,))
            customer = cursor.fetchone() # Fetch a single row

        if customer is None:
            abort(404) # Return 404 if customer not found

        # Pass the single customer row (as a Row object or tuple) to the template
        return render_template('edit_customer.html', customer=customer)

    except Exception as e:
        print(f"Error loading edit customer page for ID {id}: {e}", file=sys.stderr)
        abort(500) # Return a server error

# Implement the route to handle the update POST request from the edit form
@app.route('/update_customer/<int:id>', methods=['POST'])
def update_customer(id):
    try:
        # Retrieve data from the submitted form
        name = request.form['name']
        company = request.form['company']
        address = request.form['address']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country'] # No default needed, as form provides it
        industry = request.form['industry']
        core_business = request.form['core_business']
        contact = request.form['contact']
        email = request.form['email']
        # The hidden input field 'id' is also in the form, but we are using the ID from the URL (<int:id>)

        with sqlite3.connect("customers.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE customers
                SET name = ?, company = ?, address = ?, city = ?, state = ?, country = ?, industry = ?, core_business = ?, contact = ?, email = ?
                WHERE id = ?
            """, (name, company, address, city, state, country, industry, core_business, contact, email, id))
            conn.commit()

        # Redirect back to the customer management list after updating
        return redirect(url_for('customer_management'))

    except Exception as e:
        print(f"Error updating customer with ID {id}: {e}", file=sys.stderr)
        abort(500) # Return a server error


# Implement the route to handle the delete request
@app.route('/delete_customer/<int:id>')
def delete_customer(id):
    try:
        with sqlite3.connect("customers.db") as conn:
            cursor = conn.cursor()
            # Optional: Check if customer exists before attempting deletion
            cursor.execute("SELECT id FROM customers WHERE id = ?", (id,))
            customer = cursor.fetchone()
            if customer is None:
                print(f"Attempted to delete non-existent customer with ID: {id}", file=sys.stderr)
                abort(404) # Or redirect with a message

            cursor.execute("DELETE FROM customers WHERE id = ?", (id,))
            conn.commit()

        # Redirect back to the customer management list after deletion
        return redirect(url_for('customer_management'))

    except Exception as e:
        print(f"Error deleting customer with ID {id}: {e}", file=sys.stderr)
        abort(500) # Return a server error


# ... (onboarded_customers, set_reminder, add_followup, check_reminders remain the same)
@app.route('/onboarded_customers')
def onboarded_customers():
    try:
        with sqlite3.connect("customers.db") as conn:
            conn.row_factory = sqlite3.Row # Use Row factory here too
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM customers")
            customers = cursor.fetchall()

            cursor.execute("SELECT * FROM reminders")
            reminders = cursor.fetchall()

            cursor.execute("SELECT * FROM followups")
            followups = cursor.fetchall()

        return render_template('onboarded_customers.html', customers=customers, reminders=reminders, followups=followups)
    except Exception as e:
         print(f"Error loading onboarded customers page: {e}", file=sys.stderr)
         abort(500)


@app.route('/set_reminder/<int:customer_id>', methods=['POST'])
def set_reminder(customer_id):
    try:
        reminder_date = request.form['reminder_date']
        reminder_message = request.form['reminder_message']
        with sqlite3.connect('customers.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO reminders (customer_id, reminder_date, reminder_message) VALUES (?, ?, ?)", (customer_id, reminder_date, reminder_message))
            conn.commit()
        # Redirect back to onboarded customers page after setting reminder
        return redirect(url_for('onboarded_customers'))
    except Exception as e:
        print(f"Error setting reminder for customer {customer_id}: {e}", file=sys.stderr)
        abort(500)


@app.route('/add_followup/<int:customer_id>', methods=['POST'])
def add_followup(customer_id):
    try:
        followup_text = request.form['followup_text']
        followup_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect('customers.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO followups (customer_id, followup_text, followup_date) VALUES (?, ?, ?)", (customer_id, followup_text, followup_date))
            conn.commit()
        # Redirect back to onboarded customers page after adding followup
        return redirect(url_for('onboarded_customers'))
    except Exception as e:
        print(f"Error adding followup for customer {customer_id}: {e}", file=sys.stderr)
        abort(500)


@app.route('/check_reminders')
def check_reminders():
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect('customers.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT customers.name, reminders.reminder_message
            FROM reminders
            JOIN customers ON reminders.customer_id = customers.id
            WHERE strftime('%Y-%m-%d %H:%M', reminder_date) = ?
        """, (now,))
        reminders_due = cursor.fetchall()
        conn.close()
        return jsonify([{'customer_name': r[0], 'reminder_message': r[1]} for r in reminders_due])
    except Exception as e:
        print(f"Error checking reminders: {e}", file=sys.stderr)
        return jsonify({'error': 'An error occurred'}), 500


# Add download excel route (placeholder - implement as needed)
@app.route('/download_excel')
def download_excel():
    # Logic to fetch data and create excel file
    # For now, a placeholder
    print("Download Excel route hit (placeholder)")
    return "Download Excel functionality goes here"


if __name__ == '__main__':
    init_db()
    app.run(debug=True)