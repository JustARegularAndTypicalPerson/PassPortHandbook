import random
from flask import Blueprint, flash, redirect, request, render_template, url_for, session
from flask_login import current_user, login_required, login_user, logout_user
from app import db
from auth.models.company import Company
from auth.models.user import User

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth_bp.profile'))

    if request.method == 'POST':
        # Collect form data
        name = request.form.get('name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        
        # Check if a user with this email or phone already exists
        if User.query.filter((User.email == email) | (User.phone_number == phone_number)).first():
            flash('A user with that email or phone number already exists.', 'error')
            return redirect(url_for('auth_bp.register'))
        
        # Store registration data temporarily in session
        session['registration_data'] = {
            'name': name,
            'surname': surname,
            'email': email,
            'phone_number': phone_number,
            'password': password  # In production, ensure you handle passwords securely.
        }
        
        # Generate a random 6-digit verification code and store in session
        code = random.randint(100000, 999999)
        session['verification_code'] = code
        
        # Simulate sending SMS (Replace with an actual SMS API like Twilio)
        flash(f"Verification code sent to {phone_number}: {code}", "success")
        return redirect(url_for('auth_bp.confirm_phone'))
    
    return render_template('register.html')

@auth_bp.route('/confirm_phone', methods=['GET', 'POST'])
def confirm_phone():
    if request.method == 'POST':
        code = request.form.get("code")
        expected_code = session.get('verification_code')
        if not expected_code or str(code) != str(expected_code):
            flash("Invalid verification code.", "error")
            return redirect(url_for('auth_bp.confirm_phone'))
        
        # Retrieve registration data from session and create the new user
        registration_data = session.get('registration_data')
        if not registration_data:
            flash("Registration data not found. Please register again.", "error")
            return redirect(url_for('auth_bp.register'))
        
        user = User(
            name=registration_data['name'],
            surname=registration_data['surname'],
            email=registration_data['email'],
            phone_number=registration_data['phone_number']
        )
        user.set_password(registration_data['password'])
        db.session.add(user)
        db.session.commit()
        
        # Clear temporary session data
        session.pop('registration_data', None)
        session.pop('verification_code', None)
        
        # Log the user in and complete registration
        login_user(user)
        flash("Phone verified and registration complete.", "success")
        return redirect(url_for('auth_bp.profile'))
    
    return render_template('confirm_phone.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth_bp.profile'))

    if request.method == 'POST':
        login_field = request.form.get('login')
        password = request.form.get('password')
        
        # Search for a user by email or phone number
        user = User.query.filter(
            (User.email == login_field) | (User.phone_number == login_field)
        ).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('auth_bp.profile'))
        
        flash('Invalid login credentials.', 'error')
        return redirect(url_for('auth_bp.login'))
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # Clears any lingering registration/session data
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_name = request.form.get('name')
        new_surname = request.form.get('surname')
        new_email = request.form.get('email')
        
        if not new_name or not new_email:
            flash("Username, email are required.", "error")
            return redirect(url_for('auth_bp.profile'))

        current_user.name = new_name
        current_user.surname = new_surname
        current_user.email = new_email
        db.session.commit()
        
        flash("Profile updated successfully.", "success")
        return redirect(url_for('auth_bp.profile'))
    
    return render_template('profile.html', user=current_user)

@auth_bp.route('/profile/delete', methods=['POST'])
@login_required
def delete_profile():
    user_to_delete = current_user
    db.session.delete(user_to_delete)
    db.session.commit()
    logout_user()
    flash("Your profile has been deleted.", "success")
    return redirect(url_for('auth_bp.register'))

@auth_bp.route('/create_business', methods=['POST'])
@login_required
def create_business():
    name = request.form.get('name')
    logo_url = request.form.get('logo_url')
    business_sector = request.form.get('business_sector')
    country = request.form.get('country')
    city = request.form.get('city')
    street = request.form.get('street')
    house = request.form.get('house')
    office = request.form.get('office')

    company = Company(
        name=name,
        logo_url=logo_url,
        business_sector=business_sector,
        country=country,
        city=city,
        street=street,
        house=house,
        office=office,
        user_id=current_user.id
    )
    db.session.add(company)
    db.session.commit()
    flash("Business created successfully!", "success")
    return redirect(url_for('auth_bp.profile'))

@auth_bp.route('/update_business/<int:company_id>', methods=['POST'])
@login_required
def update_business(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        flash("Business not found or you don't have permission to edit it.", "error")
        return redirect(url_for('auth_bp.profile'))

    company.name = request.form.get('name')
    company.business_sector = request.form.get('business_sector')
    db.session.commit()
    flash("Business updated successfully!", "success")
    return redirect(url_for('auth_bp.profile'))

@auth_bp.route('/delete_business/<int:company_id>', methods=['POST'])
@login_required
def delete_business(company_id):
    company = Company.query.filter_by(id=company_id, user_id=current_user.id).first()
    if not company:
        flash("Business not found or you don't have permission to delete it.", "error")
        return redirect(url_for('auth_bp.profile'))

    db.session.delete(company)
    db.session.commit()
    flash("Business deleted successfully!", "success")
    return redirect(url_for('auth_bp.profile'))
