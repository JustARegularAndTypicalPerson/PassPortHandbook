from flask import Blueprint, flash, render_template, request, redirect, url_for
from flask_login import login_required
from app import db
from auth.models.company import Company

ad_bp = Blueprint("ad_bp", __name__)

# Route to display business information with the option to leave a review
@ad_bp.route('<int:company_id>', methods=['GET', 'POST'])
def business_page(company_id):
    # Retrieve the company by ID
    company = Company.query.get_or_404(company_id)

    # Variable to store whether to show the support or feedback option
    show_support = False
    show_feedback_link = False

    # Handle POST request to submit the review
    if request.method == 'POST':
        rating = int(request.form.get('rating'))  # Get the rating value from the form
        
        # Flash a confirmation message
        flash(f"Thank you for your rating of {rating} stars!", "success")
        
        # Check the rating and set the options accordingly
        if rating > company.rating_threshold:  # If rating is lower than or equal to the threshold
            show_feedback_link = True
        else:
            show_support = True

    # Render the template with the company data, rating options, and threshold
    return render_template('business.html', 
                           company=company, 
                           rating_threshold=company.rating_threshold,
                           show_support=show_support, 
                           show_feedback_link=show_feedback_link)