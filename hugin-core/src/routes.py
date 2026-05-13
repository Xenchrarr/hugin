from flask import Blueprint

from src.controllers.calendar_controller import calendar_blueprint
from src.controllers.camera_controller import camera_blueprint
from src.controllers.charts_controller import charts_blueprint
from src.controllers.energy_controller import energy_blueprint
from src.controllers.home_controller import home_blueprint
from src.controllers.ideas_controller import ideas_blueprint
from src.controllers.power_controller import power_blueprint
from src.controllers.shopping_controller import shopping_blueprint
from src.controllers.today_controller import today_blueprint
from src.controllers.weather_controller import weather_blueprint

api = Blueprint('api', __name__)
api.register_blueprint(calendar_blueprint, url_prefix="/calendar")
api.register_blueprint(camera_blueprint, url_prefix="/camera")
api.register_blueprint(charts_blueprint, url_prefix="/charts")
api.register_blueprint(energy_blueprint, url_prefix="/energy")
api.register_blueprint(home_blueprint, url_prefix="/home")
api.register_blueprint(ideas_blueprint, url_prefix="/ideas")
api.register_blueprint(power_blueprint, url_prefix="/power")
api.register_blueprint(shopping_blueprint, url_prefix="/shopping")
api.register_blueprint(today_blueprint, url_prefix="/today")
api.register_blueprint(weather_blueprint, url_prefix="/weather")
