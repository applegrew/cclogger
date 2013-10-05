import imaplib
import os
import string
import email
import email.utils
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import time

from .common_util import rfc822date_to_datetime, rfc822date_to_tzinfo, Bunch, decrypt
from . import verbose, info, timeout, max_clients_pool, server_email, server_mail_host, server_mail_port, \
    server_mail_use_ssl, server_email_password

HTML_TAGS_RE = re.compile(r"</?[^<>]+>")
HTML_NEWLINE_RE = re.compile(r"<\s*br\s*/?>|<\s*tr\s*/?>", flags=re.IGNORECASE)

if False: # Use proxy quick hack.
    import socks
    import socket
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS4, '148.87.19.20', 80, True)
    socket.socket = socks.socksocket

def retryableCall(f, retries, delay, client):
    while True:
        try:
            return f()
        except imaplib.IMAP4_SSL.abort, imaplib.IMAP4.abort:
            if retries > 0:
                retries -= 1
                try:
                    client.mail.shutdown()
                except Exception, e:
                    if verbose:
                        print 'Error in shutting down mail.', e
                        print e

                time.sleep(delay)
                client.open_connection(non_retryable=True)
            else:
                raise
        except imaplib.IMAP4_SSL.readonly, imaplib.IMAP4.readonly:
            if retries > 0:
                retries -= 1
                time.sleep(delay)
            else:
                raise

class MailClientManager(object):
    def __init__(self):
        self.client_map = dict()
        self.count = 0
        self.is_cache_disabled = False

    def get_mail_client_from_pool(self, for_usermail):
        if self.is_cache_disabled:
            client = MailClient(for_usermail.in_mail_config, for_usermail.out_mail_config,
                for_usermail.email, decrypt(for_usermail.password, True))
        else:
            client = self.client_map.get(for_usermail.email, None)
            if not client:
                client = MailClient(for_usermail.in_mail_config, for_usermail.out_mail_config,
                    for_usermail.email, decrypt(for_usermail.password, True))
                self.count += 1
                if self.count > max_clients_pool:
                    self.is_cache_disabled = True # If number of mails to access is more than limit then
                                                  # there is no point in caching now. Snce, all mails will
                                                  # always be accessed one by one, in each run.
                    for email in self.client_map.keys():
                        self.client_map[email].close_connection()
                        del self.client_map[email]
                else:
                    self.client_map[for_usermail.email] = client

        client.open_connection()
        return client

    def return_client_to_pool(self, client):
        if self.is_cache_disabled:
            client.close_connection()

class MailClient(object):
    def __init__(self, in_mail_config, out_mail_config, username=None, password=None, mail=None):
        self.mail = mail
        self.username = username
        self.password = password
        self.in_mail_config = in_mail_config
        self.out_mail_config = out_mail_config

    def open_connection(self, username=None, password=None, retries=5, delay=3, non_retryable=False):
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        if self.mail:
            try:
                if verbose: print 'mail is not None. Checking if it is already open.'
                self.mail.noop()
                if verbose: print 'Connection is still open.'
                return True
            except Exception, e:
                #The possibly the server connection is severed.
                if verbose:
                    print 'Possibly connection is severed. Reconnecting.'
                    print e

        # Connect to the server
        if verbose:
            print 'Connecting to', self.in_mail_config.hostname , self.in_mail_config.port

        if self.in_mail_config.use_ssl:
            mail = imaplib.IMAP4_SSL(self.in_mail_config.hostname, self.in_mail_config.port)
        else:
            mail = imaplib.IMAP4(self.in_mail_config.hostname, self.in_mail_config.port)
        
        # Login to our account
        if verbose: 
            print 'Logging in with credentials: ', self.username, self.password

        if non_retryable:
            mail.login(self.username, self.password)
            mail.select("inbox")
        else:
            retryableCall(lambda : mail.login(self.username, self.password), retries, delay, self)
            retryableCall(lambda : mail.select("inbox"), retries, delay, self) # connect to inbox.
        self.mail = mail

    def close_connection(self):
        if self.mail:
            if verbose: print 'Shutting down connection.'
            try:
                self.mail.close()
                self.mail.logout()
                self.mail = None
            except Exception, e:
                if verbose:
                    print 'Exception on trying to close the connection.'
                    print e

            return
        if verbose: print 'Connection was not open. Cannot close it.'

    def get_new_mail_uids(self, retries=5, delay=3):
        if verbose: print 'Getting list of new mails.'

        result, data = retryableCall(lambda : self.mail.uid('search', None, "UNSEEN"), retries, delay, self) # search and return uids instead
        
        if verbose: print (result, data)
        if result == 'OK':
            return data[0].split()

        raise Exception("get_new_mail_uids failed. Got bad result %s" % result)

    # note that if you want to get html content (body) and the email contains
    # multiple payloads (plaintext / html), you must parse each message separately.
    # use something like the following: (taken from a stackoverflow post)
    def get_html_block(self, email_message_instance):
        text_body = None
        maintype = email_message_instance.get_content_maintype()
        if maintype == 'multipart':
            for part in email_message_instance.get_payload():
                if part.get_content_maintype() == 'html':
                    return part.get_payload()
                elif part.get_content_maintype() == 'text':
                    text_body = part.get_payload()
        elif maintype == 'html':
            return email_message_instance.get_payload()
        elif maintype == 'text':
            text_body = email_message_instance.get_payload()

        if text_body:
            return '<html><head></head><body><pre>%s</pre></body></html>' % text_body

    def parse_email(self, raw_mail):

        email_message = email.message_from_string(raw_mail)
        complexTos = []
        if not email_message['To'] is None:
            complexTos.extend(email_message['To'].split(','))
        if not email_message['Cc'] is None:
            complexTos.extend(email_message['Cc'].split(','))
         
        fromMail = tuple([x.strip().lower() for x in email.utils.parseaddr(email_message['From'])])
        to = []
        for t in complexTos:
            email_pair = tuple([x.strip().lower() for x in email.utils.parseaddr(t)])
            if not(email_pair in to) and email_pair[1] != fromMail[1]:
                to.append(email_pair) # These are tuples of the form ('name', 'emailid') for email name <emailid>
        
        mail = {
            'To': to,
            'From': fromMail,
            'Subject': email_message['Subject'],
            'Date': rfc822date_to_datetime(email_message['Date']),
            'DateTzinfo': rfc822date_to_tzinfo(email_message['Date']),
            'Body': self.get_html_block(email_message)
        }

        if verbose:
            print 'parsed email', 'TO: ', mail['To'], 'From: ', mail['From'], 'Subject: ', mail['Subject']
        return mail

    def fetch_mail(self, uid, retries=5, delay=3):

        if verbose: print 'Fetching full mail for uid %s' % uid
        #result, data = mail.uid('fetch', uid, '(RFC822)')
        result, data = retryableCall(lambda : self.mail.uid('fetch', uid, '(BODY.PEEK[HEADER])'), retries, delay, self)
        if result == 'OK':
            header = data[0][1]
            result, data = retryableCall(lambda : self.mail.uid('fetch', uid, '(BODY.PEEK[TEXT])'), retries, delay, self)
            if result == 'OK':
                body = data[0][1]
                if verbose:
                    print 'Raw mail dump:-'
                    print (result, data)
                return self.parse_email("%s\n%s" % (header, body))
        raise Exception("fetch_mail failed. Got bad result %s" % result)

    def mark_mail_as_read(self, uid, retries=5, delay=3):
        if verbose: print 'Marking mail with uid %s as seen.' % uid

        result, data = retryableCall(lambda : self.mail.uid('store', uid, '+FLAGS', r'(\Seen)'), retries, delay, self)

        if verbose: print 'mark_mail_as_read: result, data', result, data
        return result == 'OK'

    def send_mail(self, to, from_email, subject, html_body):
        if not self.out_mail_config:
            raise Exception('out_mail_config not set. Cannot send mail.')

        send_mail(to, from_email, subject, html_body, self.out_mail_config, self.username, self.password)

def send_mail(to, from_email, subject, html_body, out_mail_config, username, password):
    """Send mail. to is a list of email ids."""

    tonew = []
    for t in to:
        if isinstance(t, (tuple, list)):
            t = "%s<%s>" % (t[0], t[1])
        else:
            t = "%s<%s>" % (t.user.name, t.email)
        tonew.append(t)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = ', '.join(map(str,tonew))
    #msg['To'] = 'app<admin@gmail.com>, '
    
    part1 = MIMEText(html_to_text(html_body), 'plain')
    part2 = MIMEText(html_body, 'html')
    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part1)
    msg.attach(part2)

    if info:
        print 'Sending mail to', tonew, subject
    if verbose:
        print 'Sending mail', out_mail_config.hostname, out_mail_config.port, timeout, out_mail_config.use_ssl , tonew, subject

    if out_mail_config.use_ssl:
        s = smtplib.SMTP_SSL(out_mail_config.hostname, out_mail_config.port, timeout=timeout)
    else:
        s = smtplib.SMTP(out_mail_config.hostname, out_mail_config.port, timeout=timeout)
    s.login(username, password)
    s.sendmail(from_email, tonew, msg.as_string())
    s.quit()

def html_to_text(html):
    text = html
    text = string.replace(text, "\n", "")
    text = HTML_NEWLINE_RE.sub("\n", text)
    text = HTML_TAGS_RE.sub("", text)
    return text

def server_send_mail(to, subject, html_body):
    conf = Bunch()
    conf.hostname = server_mail_host
    conf.port = server_mail_port
    conf.use_ssl = server_mail_use_ssl
    send_mail(to, server_email, subject, html_body, conf, server_email, server_email_password)

