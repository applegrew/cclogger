import time
import traceback
import time
import sys
import imaplib

from .client import MailClientManager, server_send_mail
from .model import db, UserMail, TransactionAlert
from . import SLEEP_PERIOD, admin_emails, consecutive_err_threshold
from .parse import ParseCentral

err_counts = 0
last_err_time = 0

client_manager = MailClientManager()

def now():
    return long(round(time.time() * 1000))

def incr_err():
    global err_counts, last_err_time

    curr = now()
    if err_counts == 0 or (curr - last_err_time) < 10000:
        err_counts += 1
        last_err_time = curr
    else:
        err_counts = 0

    return err_counts

def process_new():
    try:
        db.connect()
        for usermail in UserMail.select().where(UserMail.is_dummy == False, UserMail.is_bad == False, UserMail.is_sms == False):
            try:
                client = client_manager.get_mail_client_from_pool(usermail)

                uids = client.get_new_mail_uids()
                try:
                    uids = sorted(uids, key=int)
                except ValueError:
                    # I couldn't find any RFC doc specifying that UID must be number. Hence, taking no chance.
                    uids = sorted(uids)

                for uid in uids:
                    mark_read = False
                    if not TransactionAlert.select().where(TransactionAlert.uid == uid, \
                        TransactionAlert.user_mail == usermail).exists():

                        mail = client.fetch_mail(uid)
                        mark_read = ParseCentral.getInstance().parse(mail, uid, usermail)

                    if mark_read:
                        if not client.mark_mail_as_read(uid):
                            print "Could not mark mail as read."
                            if admin_emails:
                                server_send_mail(admin_emails,
                                    "CCTracker Error", "Could not mark mail as read.")
            except (imaplib.IMAP4_SSL.error, imaplib.IMAP4.error) as e:
                usermail.is_bad = True
                usermail.error = str(e)
                usermail.save()
            except Exception, e:
                print '>>> Exception: ', str(e)
                stk = traceback.format_exc()
                print stk
                print "Reporting exception to owner email", admin_emails
                if admin_emails:
                    server_send_mail(admin_emails, "CCTracker Exception: %s" % str(e), "<pre>\n%s</pre>" % stk)
                if incr_err() >= consecutive_err_threshold: #Turn off when there are consecutive_err_threshold consecutive errors.
                    print "Reached max error threshold. Shutting down."
                    return False

    finally:
        db.close()
    return True


def main_run(): 
    while(True):   
        try:
            if not process_new():
                return
            time.sleep(SLEEP_PERIOD) 
        except Exception, e:
            print '>>> Exception: ', str(e)
            stk = traceback.format_exc()
            print stk
            print "Reporting exception to owner email", admin_emails
            if admin_emails:
                server_send_mail(admin_emails, "CCTracker Exception: %s" % str(e), "<pre>\n%s</pre>" % stk)
            if incr_err() >= consecutive_err_threshold: #Turn off when there are consecutive_err_threshold consecutive errors.
                print "Reached max error threshold. Shutting down."
                return


