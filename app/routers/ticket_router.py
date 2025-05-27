from flask import Blueprint, request
from app.models.response import Response
from app.services.ticket_service import process_ticket_description
from app.services.background_service import BackgroundTaskManager
import uuid

ticket_bp = Blueprint('ticket_bp', __name__)

@ticket_bp.route("/tickets", methods=["POST"])
def send_description():
    data = request.get_json()
    if not data or "description" not in data:
        return Response(message="Bad Request", status_code=400, error="Missing description field").to_json()
    
    description = data["description"]
    task_id = str(uuid.uuid4())
    
    # Start background task
    BackgroundTaskManager.run_task(task_id, process_ticket_description, description=description)
    
    return Response(message="Success", status_code=202, data={
        "message": "Ticket processing started",
        "task_id": task_id
    }).to_json()

@ticket_bp.route("/tickets/status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    status = BackgroundTaskManager.get_task_status(task_id)
    
    if status["status"] == "not_found":
        return Response(message="Not Found", status_code=404, error="Task not found").to_json()
    
    if status["status"] == "failed":
        return Response(message="Processing Failed", status_code=500, data={
            "status": status["status"],
            "error": status["error"]
        }).to_json()
    
    return Response(message="Success", status_code=200, data={
        "status": status["status"],
        "result": status["result"] if status["status"] == "completed" else None
    }).to_json()