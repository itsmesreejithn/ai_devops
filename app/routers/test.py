from flask import Blueprint
from app.models.response import Response

test_bp = Blueprint('test_bp', __name__)

@test_bp.route('/test', methods=["GET"])
def get_test():
    return Response("success", 200, "Test running successfully").to_json()