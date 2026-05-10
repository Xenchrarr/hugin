import os

PORT = int(os.environ.get('PORT', '6002'))
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
PRINTER_DEVICE = os.environ.get('PRINTER_DEVICE', '/dev/usb/lp0')
HUGIN_CORE_URL = os.environ.get('HUGIN_CORE_URL', 'http://hugin-core:5100')
YR_ID = os.environ.get('YR_ID', '')
