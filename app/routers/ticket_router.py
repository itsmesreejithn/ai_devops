from flask import Blueprint, request
from app.models.response import Response
from app.services.ticket_service import process_ticket_description
from app.services.background_service import BackgroundTaskManager
import uuid
import json

ticket_bp = Blueprint('ticket_bp', __name__)

@ticket_bp.route("/tickets", methods=["POST"])
def send_description():
    data = request.get_json()
    if not data or "description" not in data:
        return Response(message="Bad Request", status_code=400, error="Missing description field").to_json()
    
    description = data["description"]
    task_id = str(uuid.uuid4())
    
    # Start background task
    BackgroundTaskManager.run_task(task_id, process_ticket_description, description=description, thread_id=task_id)
    
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
    
    if status["status"] == "waiting_for_human":
        return Response(message="Waiting for human Input", status_code=200, data={
            "status": status["status"],
            "message": status["interrupt_message"],
            "thread_id": status["thread_id"],
            "resumable": status.get("resumable", True)
        }).to_json()
    
    return Response(message="Success", status_code=200, data={
        "status": status["status"],
        "result": status["result"] if status["status"] == "completed" else None
    }).to_json()

@ticket_bp.route("/tickets/resume/<task_id>", methods=["POST"])
def resume_task(task_id):
    data = request.get_json()
    if not data or "input" not in data:
        return Response(message="Bad Request", status_code=400, error="Missing user_input field").to_json()

    user_input = data["input"]

    status = BackgroundTaskManager.get_task_status(task_id=task_id)
    if status["status"] == "not_found":
        return Response(message="Not Found", status_code=404, error="Task not found").to_json()
    
    if status["status"] != "waiting_for_human":
        return Response(message="Bad Request", status_code=400, error="Task is not waiting for human input").to_json()
    
    thread_id = status.get("thread_id", task_id)

    BackgroundTaskManager.update_task_status(task_id, "resuming")

    BackgroundTaskManager.run_task(f"{task_id}_resume", process_ticket_description, thread_id=thread_id, user_input=user_input)

    return Response(message="Success", status_code=200, data={
        "message": "Workflow resumed",
        "task_id": task_id
    }).to_json()