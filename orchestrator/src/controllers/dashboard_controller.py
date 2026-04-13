from flask import Blueprint, request

from src.services.dashboard_service import get_dashboard_stats

dashboard_blueprint = Blueprint('dashboard', __name__)


@dashboard_blueprint.route('/stats', methods=['GET'])
def stats():
    range_key = request.args.get('range', '30d')
    try:
        data = get_dashboard_stats(range_key)
        return {'status': 200, **data}, 200
    except Exception as e:
        return {'message': str(e), 'status': 500}, 500
