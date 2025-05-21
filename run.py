from app import create_app
import os
from dotenv import load_dotenv

load_dotenv()

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=os.getenv('PORT', 5001),
        debug=os.getenv('DEBUG', True),
    )