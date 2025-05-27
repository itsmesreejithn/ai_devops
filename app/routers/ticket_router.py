from flask import Blueprint, request
from app.models.response import Response
from app.services.ticket_service import process_ticket_description

ticket_bp = Blueprint('ticket_bp', __name__)

@ticket_bp.route("/tickets", methods=["POST"])
def send_description():
    data = request.get_json()
    if not data or "description" not in data:
        return Response(message="Bad Request", status_code=400, error="Missing description field").to_json()
    
    description = data["description"]
    result = process_ticket_description(description=description)
    
    return Response(message="success", status_code=200, data=result).to_json()