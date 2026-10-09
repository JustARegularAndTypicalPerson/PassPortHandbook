from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # The original client landing page and its assets are excluded from this snapshot.
    return render_template('main.html')

@main_bp.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@main_bp.route('/terms')
def terms():
    return render_template('terms.html')
