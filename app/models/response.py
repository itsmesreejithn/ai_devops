from flask import jsonify

class Response:
    def __init__(self, message, status_code, data=None):
        self.message = message
        self.status_code = status_code
        self.data = data

    def to_json(self):
        response = {
            "message": self.message,
            "status_code": self.status_code
        }

        if self.data is not None:
            response["data"] = self.data

        flask_response = jsonify(response)
        flask_response.status_code = self.status_code
        return flask_response