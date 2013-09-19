import re

from . import verbose
from .common_util import ApiException

class ParserException(Exception):
    def __init__(self, tag, code, msg, cc_no=None):
        super(ParserException, self).__init__(msg)
        self.cc_no = cc_no if cc_no is not None else ''
        self.code = code
        self.msg = msg
        self.tag = tag

    def get_code(self):
        return self.code

    def get_msg(self):
        return self.msg

    def get_card_no(self):
        return self.cc_no

    def get_tag(self):
        return self.tag

    def __unicode__(self):
        return u'%s [%s][%s]: %s' % (self.get_tag(), self.get_code(), self.get_card_no(), self.get_msg())

class BaseParseCentral(object):
    INSTANCE = None
    parsers = dict()

    def __init__(self):
        if self.INSTANCE is not None:
            raise ValueError("An instantiation already exists!")

    def register(self, parser):
        if verbose:
            print 'Register parser called by :', parser.get_name()

    def get_parsers(self):
        return self.parsers

class ParseCentral(BaseParseCentral):
    @classmethod
    def getInstance(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = ParseCentral()
            if verbose:
                print 'Instantiated ParseCentral'
        return cls.INSTANCE

    def register(self, parser):
        super(ParseCentral, self).register(parser)

        emails = parser.get_from_emails_to_track()
        for email in emails:
            self.parsers[email.strip().lower()] = parser
            if verbose:
                print 'Registered parser for email: ', email

    def parse(self, mail, uid, usermail):
        from_email = mail['From'][1].strip().lower()
        parser = self.parsers.get(from_email, None)
        if parser:
            try:
                return parser.parse_mail(from_email, mail['To'], mail['Date'], mail['DateTzinfo'],
                    mail['Subject'], mail['Body'], uid, usermail)
            except ParserException:
                # Todo log them into notifications table and create api to access that.
                pass
        else:
            if verbose:
                print 'No parser found for from_email: ', from_email

class SmsParseCentral(BaseParseCentral):
    parsers_addresses = list()
    parser_name_to_parser_map = dict()

    @classmethod
    def getInstance(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = SmsParseCentral()
            if verbose:
                print 'Instantiated SmsParseCentral'
        return cls.INSTANCE

    def register(self, parser):
        super(SmsParseCentral, self).register(parser)

        addresses = parser.get_from_addresses_to_track()
        self.parser_name_to_parser_map[parser.get_name()] = parser
        for address in addresses:
            address = address.strip().lower()
            self.parsers[address] = parser
            self.parsers_addresses.append(address)
            if verbose:
                print 'Registered sms parser for address: ', address

    def get_addresses_interested(self):
        return self.parsers_addresses

    def get_parser_names(self):
        return self.parser_name_to_parser_map.keys()

    def get_addresses_for_parser_names(self, parser_names):
        addresses = list()
        for parser_name in parser_names:
            parser = self.parser_name_to_parser_map[parser_name]
            if parser:
                addresses = addresses + parser.get_from_addresses_to_track()
        return addresses

    def parse(self, from_address, body, date, tzinfo, smsid, usermail):
        from_address = from_address.strip().lower()
        parser = self.parsers.get(from_address, None)
        if parser:
            body = body.strip()
            body = re.sub(r"\n\r", "", body)
            body = re.sub(r"\s{2,}", " ", body) # Removes multiple spaces
            try:
                return parser.parse_sms(from_address, body, date, tzinfo, smsid, usermail)
            except ParserException, e:
                a = ApiException('PARSE_FAILED', unicode(e))
                a.set_extra({
                    'Smsid': smsid
                    })
                raise a
        else:
            if verbose:
                print 'No parser found for from_address: ', from_address

class BaseParser(object):

    def get_name(self):
        "Must be unique for each kind of parsers."
        raise NotImplementedError

class AlertMailParser(BaseParser):
    def __init__(self):
        ParseCentral.getInstance().register(self)

    def get_from_emails_to_track(self):
        raise NotImplementedError

    def parse_mail(self, from_email, to_email, date, tzinfo, subject, body, uid, usermail):
        raise NotImplementedError

class SmsParser(BaseParser):
    def __init__(self):
        SmsParseCentral.getInstance().register(self)
    
    def get_from_addresses_to_track(self):
        raise NotImplementedError

    def parse_sms(self, from_address, body, date, tzinfo, smsid, usermail):
        raise NotImplementedError

from .parsers import *

