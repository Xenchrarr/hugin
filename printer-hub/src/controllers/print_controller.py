from flask import Blueprint, request, jsonify

from src.services.print_service import PrintService
from src.services.news_service import NewsService
from src.services.today_service import TodayService
from src.services.weather_service import WeatherService
from src.services.shopping_service import ShoppingService

print_blueprint = Blueprint('print', __name__)


@print_blueprint.route('/', methods=['POST'])
def print_content():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    lines = data.get('lines')
    if not lines or not isinstance(lines, list):
        return jsonify({'error': 'lines must be a non-empty list of strings'}), 400

    title = data.get('title')
    footer = data.get('footer')

    try:
        PrintService().print_content(lines=lines, title=title, footer=footer)
        return jsonify({'status': 'printed'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@print_blueprint.route('/news', methods=['POST'])
def print_news():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    feed_url = data.get('feed_url')
    if not feed_url:
        return jsonify({'error': 'feed_url is required'}), 400

    count = data.get('count', 5)

    try:
        result = NewsService().fetch_and_print(feed_url=feed_url, count=int(count))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@print_blueprint.route('/weather', methods=['POST'])
def print_weather():
    data = request.get_json(silent=True) or {}
    yr_id = data.get('yr_id') or None

    try:
        result = WeatherService().fetch_and_print(yr_id=yr_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@print_blueprint.route('/shopping', methods=['POST'])
def print_shopping():
    try:
        result = ShoppingService().fetch_and_print()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@print_blueprint.route('/today', methods=['POST'])
def print_today():
    try:
        result = TodayService().fetch_and_print()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
