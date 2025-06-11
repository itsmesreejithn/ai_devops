import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRETE_KEY = os.getenv('SECRETE_KEY')

    # Local Model
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL')

    # Groq Model
    GROQ_MODEL = os.getenv('GROQ_MODEL')

    # OpenAI
    OPENAI_MODEL = os.getenv('OPENAI_MODEL')

    # Gitlab
    GITLAB_URL = os.getenv('GITLAB_URL')
    GITLAB_ADMIN_ACCESS_TOKEN = os.getenv('GITLAB_ADMIN_ACCESS_TOKEN')

    # Jenkins
    JENKINS_URL = os.getenv('JENKINS_URL')
    JENKINS_USERNAME = os.getenv('JENKINS_USERNAME')
    JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN")
    JENKINS_CREDENTIAL_ID = os.getenv("JENKINS_CREDENTIAL_ID")
    JENKSIN_AGETN_NODE = os.getenv("JENKSIN_AGETN_NODE")

    JENKINS_SSH_HOST = os.getenv("JENKINS_SSH_HOST")
    JENKINS_SSH_USERNAME = os.getenv("JENKINS_SSH_USERNAME")
    JENKINS_SSH_PASSWORD = os.getenv("JENKINS_SSH_PASSWORD")
    JENKINS_WORKSPACE_PATH = os.getenv("JENKINS_WORKSPACE_PATH")