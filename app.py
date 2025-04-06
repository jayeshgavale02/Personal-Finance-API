# Personal Finance Management System - Flask API with MySQL (phpMyAdmin)

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import os
from werkzeug.utils import secure_filename
import datetime
import google.generativeai as genai
# Set up Gemini (Google AI) configuration
genai.configure(api_key="AIzaSyCCdw1M87aOvwhwS7QpTO01gEfko_-Dbj0")  # replace with your actual key
app = Flask(__name__)
CORS(app)

# MySQL Config
app.config['MYSQL_HOST'] = 's3484.bom1.stableserver.net'
app.config['MYSQL_USER'] = 'codemine_finance_db'
app.config['MYSQL_PASSWORD'] = 'Jayu@7219183128'  # set your password
app.config['MYSQL_DB'] = 'codemine_finance_db'

# JWT Config
app.config['JWT_SECRET_KEY'] = 'your-secret-key'
jwt = JWTManager(app)

# File upload config
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mysql = MySQL(app)

# -------------------- User Auth ----------------------
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    cursor = mysql.connection.cursor()

    # Check if user already exists
    cursor.execute("SELECT * FROM users WHERE email = %s", (data['email'],))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.close()
        return jsonify({"message": "User with this email already exists"}), 400

    # Proceed to register new user
    hashed_password = generate_password_hash(data['password'])
    cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                   (data['name'], data['email'], hashed_password))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"message": "User registered successfully"}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", (data['email'],))
    user = cursor.fetchone()
    cursor.close()
    if user and check_password_hash(user['password'], data['password']):
        access_token = create_access_token(
            identity=str(user['id']),
            expires_delta=datetime.timedelta(hours=4)  # 4-hour expiration
        )
        return jsonify({"token": access_token, "user": user})
    return jsonify({"message": "Invalid credentials"}), 401

# -------------------- Protected Routes ----------------------
@app.route('/api/profile', methods=['POST'])
@jwt_required()
def save_profile():
    user_id = get_jwt_identity()
    data = request.json
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO profiles (user_id, age, location, marital_status, dependents) VALUES (%s, %s, %s, %s, %s)",
                   (user_id, data['age'], data['location'], data['marital_status'], data['dependents']))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"message": "Profile saved"})

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
    profile = cursor.fetchone()
    cursor.close()
    return jsonify(profile)

@app.route('/api/income', methods=['POST'])
@jwt_required()
def add_income():
    user_id = get_jwt_identity()
    data = request.json
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO incomes (user_id, type, amount, frequency) VALUES (%s, %s, %s, %s)",
                   (user_id, data['type'], data['amount'], data['frequency']))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"message": "Income added"})

@app.route('/api/income', methods=['GET'])
@jwt_required()
def get_income():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM incomes WHERE user_id = %s", (user_id,))
    income_data = cursor.fetchall()
    cursor.close()

    monthly_total = 0
    yearly_total = 0

    for item in income_data:
        amount = float(item['amount'])
        freq = item['frequency'].lower()

        if freq == 'monthly':
            monthly_total += amount
            yearly_total += amount * 12
        elif freq == 'quarterly':
            monthly_total += amount / 3
            yearly_total += amount * 4
        elif freq == 'yearly':
            monthly_total += amount / 12
            yearly_total += amount
        else:
            # Treat unknown frequency as monthly
            monthly_total += amount
            yearly_total += amount * 12

    return jsonify({
        "incomes": income_data,
        "monthly_income_total": f"{monthly_total:,.2f}",
        "yearly_income_total": f"{yearly_total:,.2f}"
    })


@app.route('/api/transactions/manual', methods=['POST'])
@jwt_required()
def add_transaction():
    user_id = get_jwt_identity()
    data = request.json
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO transactions (user_id, date, category, amount, note) VALUES (%s, %s, %s, %s, %s)",
                   (user_id, data['date'], data['category'], data['amount'], data['note']))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"message": "Transaction added"})

@app.route('/api/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (user_id,))
    transactions = cursor.fetchall()
    cursor.close()
    return jsonify(transactions)

@app.route('/api/transactions/upload', methods=['POST'])
@jwt_required()
def upload_transactions_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return jsonify({"message": "File uploaded", "filename": filename})

@app.route('/api/budget/custom', methods=['POST'])
@jwt_required()
def custom_budget():
    user_id = get_jwt_identity()
    data = request.json
    cursor = mysql.connection.cursor()
    for category, amount in data['budget'].items():
        cursor.execute("INSERT INTO budgets (user_id, category, amount) VALUES (%s, %s, %s)",
                       (user_id, category, amount))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"message": "Custom budget set"})

@app.route('/api/budget', methods=['GET'])
@jwt_required()
def get_budget():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM budgets WHERE user_id = %s", (user_id,))
    budget = cursor.fetchall()
    cursor.close()
    return jsonify(budget)


def format_currency(val):
    try:
        return f"₹{float(val):,.2f}"
    except:
        return val


@app.route('/api/ai/ask', methods=['POST'])
@jwt_required()
def ai_prompt():
    user_id = get_jwt_identity()
    data = request.json
    query = data.get("query", "")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    def format_currency(val):
        return f"₹{float(val):,.2f}"

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT type, amount, frequency FROM incomes WHERE user_id = %s", (user_id,))
    incomes = cursor.fetchall()

    cursor.execute("SELECT category, amount FROM budgets WHERE user_id = %s", (user_id,))
    budgets = cursor.fetchall()

    cursor.execute("SELECT category, SUM(amount) as total_spent FROM transactions WHERE user_id = %s GROUP BY category",
                   (user_id,))
    transactions = cursor.fetchall()

    cursor.execute("SELECT goal_name, target_amount, deadline FROM savings_goals WHERE user_id = %s", (user_id,))
    goals = cursor.fetchall()

    cursor.close()

    # Format all amounts in ₹
    formatted_incomes = [f"{i['type']} - {format_currency(i['amount'])} ({i['frequency']})" for i in incomes]
    formatted_budgets = [f"{b['category']}: {format_currency(b['amount'])}" for b in budgets]
    formatted_spending = [f"{t['category']}: {format_currency(t['total_spent'])}" for t in transactions]
    formatted_goals = [f"{g['goal_name']} - Target: {format_currency(g['target_amount'])} by {g['deadline']}" for g in
                       goals]

    context = f"""
    USER FINANCIAL DATA (in Indian Rupees ₹):

    📥 Income Sources:
    {'; '.join(formatted_incomes) or 'No income data available.'}

    📊 Monthly Budgets:
    {'; '.join(formatted_budgets) or 'No budget set.'}

    💸 Spending Summary:
    {'; '.join(formatted_spending) or 'No transactions recorded.'}

    🎯 Saving Goals:
    {'; '.join(formatted_goals) or 'No goals set.'}

    🧠 User's Question:
    {query}
    """

    try:
        model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        response = model.generate_content(context)
        result = response.text.strip()
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    return jsonify({
        "query": query,
        "response": result
    })


@app.route('/api/ai/suggestions', methods=['GET'])
@jwt_required()
def get_suggestions():
    user_id = get_jwt_identity()

    def format_currency(val):
        return f"₹{float(val):,.2f}"

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cursor.execute("SELECT type, amount, frequency FROM incomes WHERE user_id = %s", (user_id,))
    incomes = cursor.fetchall()

    cursor.execute("SELECT category, amount FROM budgets WHERE user_id = %s", (user_id,))
    budgets = cursor.fetchall()

    cursor.execute("SELECT category, SUM(amount) as total_spent FROM transactions WHERE user_id = %s GROUP BY category", (user_id,))
    transactions = cursor.fetchall()

    cursor.execute("SELECT goal_name, target_amount, deadline FROM savings_goals WHERE user_id = %s", (user_id,))
    goals = cursor.fetchall()

    cursor.close()

    formatted_incomes = [f"{i['type']} - {format_currency(i['amount'])} ({i['frequency']})" for i in incomes]
    formatted_budgets = [f"{b['category']}: {format_currency(b['amount'])}" for b in budgets]
    formatted_spending = [f"{t['category']}: {format_currency(t['total_spent'])}" for t in transactions]
    formatted_goals = [f"{g['goal_name']} - Target: {format_currency(g['target_amount'])} by {g['deadline']}" for g in goals]

    context = f"""
    Based on the following user's financial data, suggest 3 personalized and actionable ways to save more or reduce expenses:

    📥 Income Sources:
    {'; '.join(formatted_incomes) or 'No income data available.'}

    📊 Monthly Budgets:
    {'; '.join(formatted_budgets) or 'No budget set.'}

    💸 Spending Summary:
    {'; '.join(formatted_spending) or 'No transactions recorded.'}

    🎯 Saving Goals:
    {'; '.join(formatted_goals) or 'No goals set.'}
    """

    try:
        model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        response = model.generate_content(context)
        suggestions = response.text.strip()
    except Exception as e:
        return jsonify({"error": f"AI error: {str(e)}"}), 500

    return jsonify({
        "suggestions": suggestions
    })


@app.route('/api/savings/goal', methods=['POST'])
@jwt_required()
def create_saving_goal():
    user_id = get_jwt_identity()
    data = request.json
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO savings_goals (user_id, goal_name, target_amount, deadline) VALUES (%s, %s, %s, %s)",
                   (user_id, data['goal_name'], data['target_amount'], data['deadline']))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"message": "Saving goal created"})

@app.route('/api/savings/progress', methods=['GET'])
@jwt_required()
def get_savings_goals():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM savings_goals WHERE user_id = %s", (user_id,))
    goals = cursor.fetchall()
    cursor.close()
    return jsonify(goals)


@app.route('/api/reports/monthly', methods=['GET'])
@jwt_required()
def monthly_report():
    user_id = get_jwt_identity()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT category, SUM(amount) as total FROM transactions WHERE user_id = %s GROUP BY category", (user_id,))
    report = cursor.fetchall()
    cursor.close()
    return jsonify({"monthly_report": report})

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
