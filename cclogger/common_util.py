import datetime
import email.utils
import pytz
import re
from datetime import tzinfo, timedelta
from functools import wraps

from . import bottle
from . import normalized_tz_obj, salt, cipher_key, verbose
from . import crypt

EMAIL_ID_RE = re.compile(r'\s*([^@\s]+)@([^@\s]+)\s*')

class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class ApiException(Exception):
    def __init__(self, code, msg):
        super(ApiException, self).__init__(msg)
        self.code = code
        self.msg = msg
        self.extra = dict()

    def get_code(self):
        return self.code

    def get_msg(self):
        return self.msg

    def set_extra(self, d):
        self.extra = d

    def get_extra(self):
        return self.extra

class UTCOffset(tzinfo):
    def __init__(self, utcoffset):
        self.utc_delta = timedelta(seconds=utcoffset)
        self.utc_offset_str = tzoffset_sec_to_hhmm(utcoffset)

    def utcoffset(self, dt):
        return self.utc_delta

    def dst(self, dt):
        return timedelta(0)

    def tzname(self,dt):
        return 'UTC %s' % self.utc_offset_str

def rfc822date_to_datetime(date):
    date = email.utils.parsedate_tz(date)
    utcdate = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date), pytz.utc)
    return utcdate.astimezone(normalized_tz_obj)

def rfc822date_to_tzinfo(date):
    offset = email.utils.parsedate_tz(date)[-1]
    return None if offset is None else UTCOffset(offset)

MONTHS_ABBR = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
def convert_month_abbr_to_digits(str_date):
    for i in range(len(MONTHS_ABBR)):
        str_date = str_date.replace(MONTHS_ABBR[i], str(i + 1).zfill(2))
        if str_date != str_date:
            return str_date
    return str_date

def date_str_to_datetime(str_date, format, tzinfo):
    date = datetime.datetime.strptime(str_date, format)
    date = date.replace(tzinfo=tzinfo)
    return date.astimezone(normalized_tz_obj)

def tzoffset_sec_to_hhmm(sec):
    sign = '-' if sec < 0 else '+'
    sec = sec if sec >= 0 else -sec
    m = sec / 60
    h = m / 60
    m = m % 60
    if m < 10:
        m = '0%d' % m
    else:
        m = str(m)
    if h < 10:
        h = '0%d' % h
    else:
        h = str(h)
    return u'%s%s%s' % (sign, h, m)

def make_float(s):
    s = str(s)
    s = s.replace(',', '').strip()
    return float(s)

def cap_words(s):
    if s is None:
        return None
    return ' '.join([x.capitalize() for x in s.split(' ')])

def trim_punctuations_and_spaces(s):
    return s.strip().strip('.,;:\'"[]|?*`~-+=_')

def normalize_place_name(s):
    return trim_punctuations_and_spaces(s).upper()

def is_valid_email(s):
    return True if EMAIL_ID_RE.match(s) else False

WEEKDAY =['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
def formatDate(date, mail):
    md = mail['Date']
    if date.utcoffset() is None:
        date = date.replace(tzinfo=normalized_tz_obj)
    date = date.astimezone(md.tzinfo)
    weekday = date.weekday()
    return "%s, %s" % (WEEKDAY[weekday], date.strftime('%d/%b/%y (%Z)'))

def get_at_domain(email):
    m = EMAIL_ID_RE.match(email)
    if m:
        return m.group(2)
    return None

def JsonResponse(f):
    @wraps(f)
    def _inner_(*args, **kwargs):
        try:
            if bottle.request.method == 'GET':
                out = f(*args, **kwargs)
            else:
                out = f(**bottle.request.forms)
            if out is None:
                out = {'Status': 'OK'}
            else:
                out['Status'] = 'OK'
        except ApiException, e:
            out = {
                'Status': 'ERR',
                'Code': e.get_code(),
                'Msg': e.get_msg()
            }
            extra = e.get_extra()
            if extra:
                out = dict(out.items() + extra.items())
        except Exception, e:
            import traceback
            print traceback.format_exc()
            out = {
                'Status': 'ERR',
                'Code': 'UNKNOWN',
                'Msg': str(e)
            }
        return out
    return _inner_

def route_with_option(path, method):
    def _wrap(f):
        @wraps(f)
        def _inner_(*args, **kwargs):
            if verbose:
                print 'Bottle got request of method type: ', bottle.request.method

            bottle.response.headers['Access-Control-Allow-Origin'] = '*'
            bottle.response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            bottle.response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
            if bottle.request.method != 'OPTIONS':
                return f(*args, **kwargs)

        bottle.route(path=path, method=['OPTIONS', method], callback=_inner_)
        return _inner_
    return _wrap

def encrypt(data, use_salt=False):
    if use_salt:
        data = data + salt
    
    return crypt.encrypt(data, cipher_key)

def decrypt(data, has_salt=False):
    data = crypt.decrypt(data, cipher_key)

    if has_salt:
        return data[:-1 * len(salt)]
    else:
        return data

def date_filter(config):
    ''' Converts dd-mm-yy to python datetime. '''
    format = config or '%d-%m-%y'
    regexp = r"(\d{1,2}-\d{1,2}-\d{2}):((\+|-)\d+)"

    def to_python(str_date):
        m = re.match(regexp, str_date)
        if m:
            date_part = m.group(1)
            tz_offset = m.group(2)
            return date_str_to_datetime(date_part, format, UTCOffset(int(tz_offset)))

    def to_url(date):
        return '%s:+0' % date.strftime(format)

    return regexp, to_python, to_url

def convert_url_date_to_pydate(str_date):
    regexp, to_python, to_url = date_filter()
    return to_python(str_date)
