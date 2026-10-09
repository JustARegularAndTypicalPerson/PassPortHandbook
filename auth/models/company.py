from app import db
from sqlalchemy.orm import validates

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    logo_url = db.Column(db.String(255))  # URL to logo image
    business_sector = db.Column(db.String(64), nullable=False)  # e.g., 'IT', 'Retail', 'Manufacturing'
    rating_threshold = db.Column(db.Integer, nullable=False, default=3)
    
    @validates('rating_threshold')
    def validate_rating_threshold(self, key, value):
        if value == 6 or value == -1:
            raise ValueError("Rating threshold cannot be 6 or -1.")
        if not (1 <= value <= 5):  # Ensure the value is within a reasonable range (1-5)
            raise ValueError("Rating threshold must be between 1 and 5.")
        return value  

    # Address fields
    country = db.Column(db.String(64), nullable=False)
    city = db.Column(db.String(64), nullable=False)
    street = db.Column(db.String(128), nullable=False)
    house = db.Column(db.String(32), nullable=False)
    office = db.Column(db.String(32), nullable=True)

    # Foreign key to user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (
    db.UniqueConstraint('name', 'user_id', name='uq_user_company_name'),
)
