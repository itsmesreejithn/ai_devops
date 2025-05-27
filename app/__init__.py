from flask import Flask
from flask_cors import CORS
from app.models.response import Response
from app.constants import API_VERSION_1
from app.routers.test import test_bp
from app.routers.ticket_router import ticket_bp

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config.from_object("app.config.Config")

    blueprints = [
        (test_bp, API_VERSION_1),
        (ticket_bp, API_VERSION_1)
    ]

    for bp, url_prefix in blueprints:
        app.register_blueprint(bp, url_prefix=url_prefix)

    @app.errorhandler(Exception)
    def handle_exception(e):
        return Response(status_code=500, message="Internal Server Error", error=str(e)).to_json()

    return app