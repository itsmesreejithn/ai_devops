import base64
import requests

def generate_basic_auth_header(username: str, password: str) -> str:
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return encoded_credentials

def get_jenkins_crumb(JENKINS_URL: str, encoded_credentials: str) -> str:
    try: 
        CRUB_URL = f"{JENKINS_URL}/crumbIssuer/api/json"
        response = requests.get(CRUB_URL, headers={"Authorization": encoded_credentials})
        print(response.json())
        if response.status_code == 200:
            return response.json()["crumbRequestField"], response.json()["crumb"]
    except Exception as e:
        print(e)
        raise Exception(f"Failed to get Jenkins crumb: {e}")
