from flask import Blueprint, jsonify

from src.controllers.script_controller import script_blueprint
from src.controllers.git_controller import git_blueprint

api = Blueprint('api', __name__)
api.register_blueprint(script_blueprint, url_prefix="/script")
api.register_blueprint(git_blueprint, url_prefix="/git")


@api.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})