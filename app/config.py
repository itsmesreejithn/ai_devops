import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRETE_KEY = os.getenv('SECRETE_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')