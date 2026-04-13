import os

from src import app

if __name__ == "__main__":
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    PORT = int(os.environ.get('PORT', '5100'))
    HOST = '0.0.0.0'
    app.run(host=HOST, port=PORT, debug=DEBUG)

