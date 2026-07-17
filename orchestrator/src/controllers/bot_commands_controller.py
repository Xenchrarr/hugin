from flask import Blueprint, request

from src.auth import require_auth

bot_commands_blueprint = Blueprint('bot_commands', __name__)

_registry: dict[str, list[str]] = {}


@bot_commands_blueprint.route('/register', methods=['POST'])
def register_bot_commands():
    data = request.get_json(silent=True)
    if not data or not data.get('channel') or not isinstance(data.get('commands'), list):
        return {'message': 'channel and commands are required', 'status': 400}, 400

    channel = str(data['channel'])
    commands = [str(c) for c in data['commands'] if isinstance(c, str)]
    _registry[channel] = commands
    return {'message': 'ok'}


@bot_commands_blueprint.route('', methods=['GET'])
@require_auth
def list_bot_commands():
    return _registry
