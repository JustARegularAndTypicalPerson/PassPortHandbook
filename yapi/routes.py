import base64
import hmac
import hashlib
import json
import os
import requests

from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_login import login_user
from app import db
from auth.models.user import User  # Update with actual path

yapi_bp = Blueprint('yapi_bp', __name__)
PARTNER_TOKEN = os.environ.get("YCLIENTS_PARTNER_TOKEN", "")

def activate_yclients_integration(salon_id):
    YCLIENTS_CALLBACK_URL = "https://api.yclients.com/api/v1/marketplace/partner/callback"
    ACCESS_TOKEN = os.environ.get("YCLIENTS_ACCESS_TOKEN", "")
    APPLICATION_ID = os.environ.get("YCLIENTS_APPLICATION_ID", "")
    API_KEY = os.environ.get("YCLIENTS_API_KEY", "")
    WEBHOOK_URL = os.environ.get("YCLIENTS_WEBHOOK_URL", "")
    CHANNELS = ["sms"]

    if not ACCESS_TOKEN or not APPLICATION_ID or not WEBHOOK_URL:
        return False

    try:
        application_id = int(APPLICATION_ID)
    except ValueError:
        return False

    payload = {
        "salon_id": int(salon_id),
        "application_id": application_id,
        "webhook_urls": [WEBHOOK_URL],
        "channels": CHANNELS
    }
    if API_KEY:
        payload["api_key"] = API_KEY

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(YCLIENTS_CALLBACK_URL, json=payload, headers=headers, timeout=15)
    except requests.RequestException:
        return False

    if response.status_code == 201:
        return True
    else:
        return False

@yapi_bp.route('/signup', methods=['GET', 'POST'])
def yclients_signup():
    salon_id = request.args.get('salon_id')
    user_data_encoded = request.args.get('user_data')
    user_data_sign = request.args.get('user_data_sign')

    if not (salon_id and user_data_encoded and user_data_sign):
        return "Missing parameters", 400

    try:
        decoded_bytes = base64.b64decode(user_data_encoded)
        decoded_json = decoded_bytes.decode('utf-8')
        user_info = json.loads(decoded_json)
    except Exception as e:
        return f"Failed to decode user_data: {e}", 400

    # Validate signature
    if not PARTNER_TOKEN:
        return "Yclients integration is not configured", 503

    calculated_sign = hmac.new(PARTNER_TOKEN.encode(), decoded_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_sign, user_data_sign):
        return "Invalid signature", 403

    # Extract user details
    phone = user_info.get("phone")
    email = user_info.get("email")
    salon_name = user_info.get("salon_name")
    name = salon_name

    # Check for existing user
    existing_user = User.query.filter((User.phone_number == phone) | (User.email == email)).first()

    if request.method == 'POST':
        password = request.form.get("password")
        if not password or len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("yclients_register.html", name=name, phone=phone, email=email)

        if not existing_user:
            # Register new user
            user = User(
                name=name,
                email=email,
                phone_number=phone,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            activate_yclients_integration(salon_id)
        else:
            user = existing_user

        login_user(user)
        flash("Welcome!", "success")
        return redirect(url_for("auth_bp.profile"))

    # If GET and user exists, log in directly
    if existing_user:
        login_user(existing_user)
        flash("Welcome back!", "success")
        return redirect(url_for("auth_bp.profile"))

    # Show password form for new user
    return render_template("yclients_register.html", name=name, phone=phone, email=email)
