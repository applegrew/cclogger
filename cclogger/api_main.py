import re
import os

from .bottle import run, default_app, debug, get
from .common_util import date_str_to_datetime, UTCOffset, date_filter

#app = Bottle()

default_app().router.add_filter('date', date_filter)

from . import api, dev

@get('/index')
def index():
    return "CCLogger API main live and kicking."

if dev:
	debug(True)
	run(reloader=True, port=9000)
else:
	os.chdir(os.path.dirname(__file__))
	application = default_app()
