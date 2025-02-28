from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import io
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    joined_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    family_members = db.relationship('FamilyMember', backref='user', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    family_member_id = db.Column(db.Integer, db.ForeignKey('family_member.id'), nullable=False)

class FamilyMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    earnings = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expenses = db.relationship('Expense', backref='family_member', lazy=True)
    investments = db.relationship('Investment', backref='family_member', lazy=True)

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    family_member_id = db.Column(db.Integer, db.ForeignKey('family_member.id'), nullable=False)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)  # Annual Percentage Rate (APR)
    tenure = db.Column(db.Integer, nullable=False)  # Loan tenure in months
    emi = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    saved_amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SavingsHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'deposit' or 'withdrawal'
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SupportRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Fetch data from the database
    expenses = Expense.query.all() or []
    family_members = FamilyMember.query.all() or []
    investments = Investment.query.all() or []
    user = current_user
    family_data = get_family_data(user.id) or {}
    savings_data = get_savings_data(user.id) or {}
    budgets = Budget.query.all() or []
    loans = Loan.query.all() or []
    savings_goals = SavingsGoal.query.all() or []
    reminders = Reminder.query.filter_by(user_id=user.id).all() or []
    notifications = Notification.query.filter_by(user_id=user.id).all() or []
    savings_history = SavingsHistory.query.filter_by(user_id=user.id).all() or []

    # Calculate total earnings
    total_earnings = sum(member.earnings for member in family_members)

    # Calculate total expenses
    total_expenses = sum(expense.amount for expense in expenses)

    # Calculate savings breakdown
    savings_breakdown = {
        "Emergency": sum(goal.saved_amount for goal in savings_goals if goal.category == "Emergency"),
        "Investment": sum(goal.saved_amount for goal in savings_goals if goal.category == "Investment"),
        "Retirement": sum(goal.saved_amount for goal in savings_goals if goal.category == "Retirement")
    }
    total_savings = sum(savings_breakdown.values())

    # Calculate savings suggestions
    savings_suggestions = get_savings_suggestions(user.id) or []

    # Calculate savings calculator results
    savings_calculator_results = get_savings_calculator_results(user.id) or {}

    # Fetch monthly expenses data
    monthly_expenses = get_monthly_expenses(user.id) or []

    # Fetch investment growth data
    investment_growth = get_investment_growth(user.id) or []

    # Calculate remaining balance and payment progress for each loan
    for loan in loans:
        loan.remaining_balance = get_remaining_balance(loan)
        loan.payment_progress = ((loan.amount - loan.remaining_balance) / loan.amount) * 100

    return render_template(
        'index.html',
        expenses=expenses,
        family_members=family_members,
        investments=investments,
        user=user,
        family_data=family_data,
        savings_data=savings_data,
        budgets=budgets,
        loans=loans,
        savings_goals=savings_goals,
        savings_breakdown=savings_breakdown,
        total_savings=total_savings,
        total_earnings=total_earnings,
        total_expenses=total_expenses,
        savings_suggestions=savings_suggestions,
        savings_calculator_results=savings_calculator_results,
        reminders=reminders,
        notifications=notifications,
        savings_history=savings_history,
        monthly_expenses=monthly_expenses,
        investment_growth=investment_growth
    )

# Define the functions to get family data, savings data, savings suggestions, and savings calculator results
def get_family_data(user_id):
    # Implement the logic to fetch family data
    return {}

def get_savings_data(user_id):
    # Implement the logic to fetch savings data
    return {}

def get_savings_suggestions(user_id):
    # Implement the logic to calculate savings suggestions
    return []

def get_savings_calculator_results(user_id):
    # Implement the logic to calculate savings calculator results
    return {}

def get_monthly_expenses(user_id):
    # Implement the logic to fetch monthly expenses data
    return []

def get_investment_growth(user_id):
    # Implement the logic to fetch investment growth data
    return []

def calculate_emi(amount, interest_rate, tenure):
    monthly_interest_rate = interest_rate / (12 * 100)
    emi = (amount * monthly_interest_rate * (1 + monthly_interest_rate) ** tenure) / ((1 + monthly_interest_rate) ** tenure - 1)
    return emi

def get_remaining_balance(loan):
    total_paid = sum(payment.amount for payment in loan.payments)
    remaining_balance = loan.amount - total_paid
    return remaining_balance

def generate_repayment_schedule(loan):
    schedule = []
    balance = loan.amount
    monthly_interest_rate = loan.interest_rate / (12 * 100)
    for month in range(1, loan.tenure + 1):
        interest = balance * monthly_interest_rate
        principal = loan.emi - interest
        balance -= principal
        schedule.append({
            'month': month,
            'emi': loan.emi,
            'principal': principal,
            'interest': interest,
            'balance': balance
        })
    return schedule

def send_payment_alerts():
    today = datetime.today().date()
    upcoming_payments = Loan.query.filter(Loan.due_date <= today + timedelta(days=7)).all()
    for loan in upcoming_payments:
        user = User.query.get(loan.user_id)
        send_email(user.email, "Upcoming EMI Due Date", f"Your EMI for {loan.provider} is due on {loan.due_date.strftime('%Y-%m-%d')}.")

# Add Loan
@app.route('/add_loan', methods=['POST'])
@login_required
def add_loan():
    provider = request.form['provider']
    amount = request.form['amount']
    interest_rate = request.form['interest_rate']
    tenure = request.form['tenure']
    emi = request.form['emi']
    due_date = request.form['due_date']
    
    new_loan = Loan(
        provider=provider,
        amount=float(amount),
        interest_rate=float(interest_rate),
        tenure=int(tenure),
        emi=float(emi),
        due_date=datetime.strptime(due_date, '%Y-%m-%d'),
        user_id=current_user.id
    )
    db.session.add(new_loan)
    db.session.commit()
    
    return redirect(url_for('index'))

# Calculate EMI
@app.route('/calculate_emi', methods=['GET'])
@login_required
def calculate_emi_route():
    amount = float(request.args.get('amount'))
    interest_rate = float(request.args.get('interest_rate'))
    tenure = int(request.args.get('tenure'))
    emi = calculate_emi(amount, interest_rate, tenure)
    interest = (emi * tenure) - amount
    principal = amount
    emi_results = {
        'emi': emi,
        'interest': interest,
        'principal': principal
    }
    return render_template('index.html', emi_results=emi_results)

# Generate Repayment Schedule
@app.route('/repayment_schedule/<int:loan_id>')
@login_required
def repayment_schedule_route(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    schedule = generate_repayment_schedule(loan)
    return render_template('index.html', repayment_schedule=schedule, loan=loan)

# Download Repayment Schedule
@app.route('/download_repayment_schedule/<int:loan_id>')
@login_required
def download_repayment_schedule(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    schedule = generate_repayment_schedule(loan)
    
    # Create a CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Month', 'EMI', 'Principal', 'Interest', 'Balance'])
    for payment in schedule:
        writer.writerow([payment['month'], payment['emi'], payment['principal'], payment['interest'], payment['balance']])
    
    output.seek(0)
    
    return send_file(output, mimetype='text/csv', attachment_filename='repayment_schedule.csv', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
