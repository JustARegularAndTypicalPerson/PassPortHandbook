import qrcode
import io
from flask import Blueprint, send_file, request

qr_code_bp = Blueprint("qr_code_bp", __name__)

@qr_code_bp.route("/<int:company_id>")
def generate_qr(company_id):
    """Generates a QR code dynamically for a given company ID."""
    company_url = f"{request.host_url}b/{company_id}"  # Replace with actual company URL

    # Generate QR code
    qr = qrcode.make(company_url)

    # Save QR code to in-memory buffer
    img_io = io.BytesIO()
    qr.save(img_io, format="PNG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/png")