import re

from ..parse import ParserException, SmsParser
from ..model import TransactionAlert, Place, db
from ..common_util import date_str_to_datetime, make_float, normalize_place_name
from .. import verbose

class ParseHdfcSms(SmsParser):

    def get_from_addresses_to_track(self):
        return ['AM-HDFCBK',]

    def get_name(self):
        return 'HDFC Bank'

    @db.commit_on_success
    def parse_sms(self, from_address, body, date, tzinfo, smsid, usermail):
        body_pattern = re.compile(r"Thank you for using your HDFC bank CREDIT card ending \s+(?P<cc>[0-9]+)\s+ for\s+(?P<currency>[a-zA-Z.$]+)\s*(?P<amt>[0-9,.]+)\s+ in\s+(?P<city>[A-Z]*)\.\s+at\s+(?P<place>.*)\.\s+, on\s+(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}).*")
        m = body_pattern.search(body, re.IGNORECASE)
        if m:
            patterns = m.groupdict()

            place_name = normalize_place_name(patterns['place'])
            try:
                place = Place.get(Place.place_name == place_name)
            except Place.DoesNotExist:
                place = Place.create(place_name=place_name)

            date = date_str_to_datetime(patterns['date'], '%Y-%m-%d', tzinfo)

            trans = TransactionAlert.create(uid=smsid, from_address=from_address, card_no=patterns['cc'],
                currency=patterns['currency'], amt=make_float(patterns['amt']), user_mail=usermail,
                date=date, place=place, created_by=self.get_name())

            if verbose:
                print 'Successfully parsed and saved alert: ', trans
            return True

ParseHdfcSms()
