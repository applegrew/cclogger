import re
from bs4 import BeautifulSoup

from ..parse import AlertMailParser, ParserException, SmsParser
from ..model import TransactionAlert, Place, db
from ..common_util import date_str_to_datetime, convert_month_abbr_to_digits, make_float, normalize_place_name
from .. import verbose

class ParseCitiIndiaAlert(AlertMailParser):

    def get_from_emails_to_track(self):
        return ['CitiAlert.India@citicorp.com',]

    def get_name(self):
        return 'CitiIndia'

    @db.commit_on_success
    def parse_mail(self, from_email, to_email, date, tzinfo, subject, body, uid, usermail):
        subject = subject.lower()
    	soup = BeautifulSoup(body)

        subject_pattern = re.compile(r"\s*Transaction confirmation on your Citibank credit card\s*".lower())
        m = subject_pattern.match(subject, re.IGNORECASE)
        if m:
            pattern = re.compile(r"(?P<currency>[a-zA-Z.$]+)\s*(?P<amt>[0-9,.]+)\s+was spent on your Credit Card\s+(?P<cc>[0-9X]+)\s+on\s+(?P<date>[0-9]{1,2}-[A-Z]{3}-[0-9]{2})\s+at\s+(?P<place>.*)\.\s+")
            m = pattern.search(soup.find(text=pattern), re.IGNORECASE)
            if m:
            	patterns = m.groupdict()

                pattern = re.compile(r"Reference\s*No:\s*(?P<refid>[0-9A-Za-z-]+)")
                m = pattern.search(soup.find(text=pattern), re.IGNORECASE)
                refid = m.groupdict()['refid']

            	place_name = normalize_place_name(patterns['place'])
            	try:
            		place = Place.get(Place.place_name == place_name)
            	except Place.DoesNotExist:
            		place = Place.create(place_name=place_name)

            	date = convert_month_abbr_to_digits(patterns['date'])
                date = date_str_to_datetime(date, '%d-%m-%y', tzinfo)

            	trans = TransactionAlert.create(uid=uid, from_address=from_email, card_no=patterns['cc'],
            		currency=patterns['currency'], amt=make_float(patterns['amt']), user_mail=usermail,
            		date=date, place=place, meta1=refid, created_by=self.get_name())

                if verbose:
                    print 'Successfully parsed and saved alert: ', trans
            	return True

            raise ParserException(self.get_name(), 'BODY_PRASE_FAIL', 'Could not parse transaction confirmation mail body.')

        subject_pattern = re.compile(r"\s*Cancellation of transaction on your Citibank credit card\s*".lower())
        m = subject_pattern.match(subject)
        if m:
            pattern = re.compile(r"Reference\s*No:\s*(?P<refid>[0-9A-Za-z-]+)")
            m = pattern.search(soup.find(text=pattern), re.IGNORECASE)
            if m:
                patterns = m.groupdict()
                refid = patterns['refid']
                try:
                    trans = TransactionAlert.get(TransactionAlert.meta1 == refid, TransactionAlert.created_by == self.get_name())
                except TransactionAlert.DoesNotExist:
                    raise ParserException('Cannot cancel citi transaction with ref. id ' + refid + '. No such record found.')
                trans.delete_instance()

                if verbose:
                    print 'Successfully parsed and cancelled alert with reference id: ', refid
                return True

            raise ParserException(self.get_name(), 'BODY_PRASE_FAIL', 'Could not parse cancel transaction mail body.')

        if verbose:
            print ":( No match found. There some mails with this matching from address but subject is unknown."
        return False

class ParseCitiIndiaSms(SmsParser):

    def get_from_addresses_to_track(self):
        return ['LM-Citibk',]

    def get_name(self):
        return 'Citi Bank'

    @db.commit_on_success
    def parse_sms(self, from_address, body, date, tzinfo, smsid, usermail):
        body_pattern = re.compile(r"(?P<currency>[a-zA-Z.$]+)\s*(?P<amt>[0-9,.]+)\s+was spent on your Credit Card\s+(?P<cc>[0-9X]+)\s+on\s+(?P<date>[0-9]{1,2}-[A-Z]{3}-[0-9]{2})\s+at\s+(?P<place>.*)\.\s+")
        m = body_pattern.search(body, re.IGNORECASE)
        if m:
            patterns = m.groupdict()

            place_name = normalize_place_name(patterns['place'])
            try:
                place = Place.get(Place.place_name == place_name)
            except Place.DoesNotExist:
                place = Place.create(place_name=place_name)

            date = convert_month_abbr_to_digits(patterns['date'])
            date = date_str_to_datetime(date, '%d-%m-%y', tzinfo)

            trans = TransactionAlert.create(uid=smsid, from_address=from_address, card_no=patterns['cc'],
                currency=patterns['currency'], amt=make_float(patterns['amt']), user_mail=usermail,
                date=date, place=place, created_by=self.get_name())

            if verbose:
                print 'Successfully parsed and saved alert: ', trans
            return True

ParseCitiIndiaAlert()
ParseCitiIndiaSms()
