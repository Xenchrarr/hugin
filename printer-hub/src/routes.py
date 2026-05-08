from flask import Blueprint, jsonify

from src.controllers.print_controller import print_blueprint

api = Blueprint('api', __name__)
api.register_blueprint(print_blueprint, url_prefix="/print")


@api.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})
