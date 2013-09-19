import re
import sys
import model
import datetime
from string import Template
import urllib

from .client import send_mail
from .common_util import cap_words, formatDate
from . import admin_emails, splitbill_email_id

class UserError(Exception):
    """Signals to main.py that this was user error not internal error."""
    def __init__(self, arg):
        super(UserError, self).__init__()
        self.arg = arg

HELP_URL = "<a href='http://www.applegrew.com/splitbill_help.html?m=%s'>here</a>" % urllib.quote_plus(splitbill_email_id)

MSG_MAIL_BODY_TMPL = Template("""
    <b>${msg}</b><br/>
    <br/>
    Please click ${help_url} for help.<br/>
    <br/>
    -------------<br/>
    Original mail<br/>
    <br/>
    Subject: ${original_subject}<br/>
    <br/>
    ${original_mail}
    """)

SUCCESS_MAIL_BODY_TMPL = Template("""
    Transaction with id: ${id} recorded.<br/>
    <br/>
    Want to know what is Splitbill? Check out ${help_url}.<br/>
    <br/>
    <table border="1" cellpadding='3'>
    <colgroup margin="2"></colgroup>
    <tr>
        <td>#</td>\t<td>Name</td>\t<td>Remarks</td>
    </tr>
    ${user_rows}
    </table>
    <br/>
    Total Amount : ${amount}
    <br/>
    <br/>
    <b> Suggested Settlemt :</b>
    <br/>
    ${settle_msg}
    <br/>
    <br/>
    -------------<br/>
    Original mail<br/>
    <br/>
    Subject: ${original_subject}<br/>
    <br/>
    ${original_mail}
    """)

BILATERAL_SUCCESS_MAIL_BODY_TMPL = Template("""
    Transaction with id: ${id} recorded.<br/>
    <br/>
    Want to know what is Splitbill? Check out ${help_url}.<br/>
    <br/>
    <table border="1" cellpadding='3'>
    <colgroup margin="2"></colgroup>
    <tr>
        <td>#</td>\t<td>Name</td>\t<td>Remarks</td>
    </tr>
    ${user_rows}
    </table>
    <br/>
    <br/>
    -------------<br/>
    Original mail<br/>
    <br/>
    Subject: ${original_subject}<br/>
    <br/>
    ${original_mail}
    """)

NAME_MSG_TMPL = Template("""
    <tr>
        <td>${counter}</td>\t<td>${name}</td>\t<td>${msg}</td>
    </tr>
    """)

DELETE_SUCCESS_MAIL_BODY_TMPL = Template("""
    ${sender} deleted a transaction.<br/>
    <br/>
    Want to know what is Splitbill? Check out ${help_url}.<br/>
    <br/>
    Transaction with id : ${id} successfully deleted.
    <br/>
    Transaction  Description : ${description}
    <br/>
    <br/>
    -------------<br/>
    Original mail<br/>
    <br/>
    Subject: ${original_subject}<br/>
    <br/>
    ${original_mail}
    """)

GET_BODY_TMPL = Template("""
    Here is your transaction history ${fiterText}<br/>
    <br/>
    Want to know what is Splitbill? Check out ${help_url}.<br/>
    <br/>
    <br/>
    <b> Settlement summary :</b>
    <br/>
    ${settle_msg}
    <br/>
    <br/>
    <table border="1" cellpadding='3'>
    <tr>
        <td>Transaction Id</td>\t<td>Date</td>\t<td>Description</td>\t<td>command</td>\t<td>Amount</td>\t<td>Contribution</td>\t<td>Share</td>\t<td>Friends</td>
    </tr>
    ${user_rows}
    </table>
    <br/>
    <br/>
    -------------<br/>
    Original mail<br/>
    <br/>
    Subject: ${original_subject}<br/>
    <br/>
    ${original_mail}
    """)

GET_ROW_MSG_TMPL = Template("""
    <tr>
        <td>${id}</td>\t<td>${date}</td>\t<td>${description}</td>\t<td>${command}</td>\t<td>${amount}</td>\t<td>${contribution}</td>\t<td>${share}</td>\t<td>${friends}</td>
    </tr>
    """)


CMD_PART_RE = re.compile(r"^([a-zA-Z]+)")

def combineNameMail(pair):
    if isinstance(pair, (tuple, list)):
        name = pair[0]
        if name is None:
            name = ''
        return '%s (%s)' % (cap_words(name), pair[1])
    elif isinstance(pair, model.User):
        name = pair.name
        if name is None:
            name = ''
        return '%s (%s)' % (cap_words(name), pair.email)
    else:
        return pair

def reply_user(msg, mail):
    reply_user_error(msg, mail)

def reply_user_error(msg, mail):
    subject = "Re: %s - %s" % (mail['Subject'], msg)
    allTo = [mail['From']]
    allTo.extend(mail['To'])
    send_mail(allTo, subject, MSG_MAIL_BODY_TMPL.substitute(
        msg=msg, help_url=HELP_URL, original_subject=mail['Subject'], original_mail=mail['Body'].replace("\n","\n<br>")))

def reply_success(id, mail, to, name_msg, settle_msg, amount):
    subject = "Re: %s" % mail['Subject']
    user_rows = ''
    i = 1
    for name, msg in name_msg:
        user_rows = "%s\n%s" % (user_rows, NAME_MSG_TMPL.substitute(counter=i, name=combineNameMail(name), msg=msg))
        i += 1
        
    body = SUCCESS_MAIL_BODY_TMPL.substitute(
        id = id,
        help_url=HELP_URL,
        original_subject=mail['Subject'],
        original_mail=mail['Body'].replace("\n","\n<br>"),
        user_rows=user_rows,
        settle_msg =settle_msg,
        amount=amount
        )

    send_mail(to, subject, body)

def reply_success_bilateral(id, mail, to ,name_msg):
    subject = "Re: %s" % mail['Subject']
    user_rows = ''
    i = 1
    for name, msg in name_msg:
        user_rows = "%s\n%s" % (user_rows, NAME_MSG_TMPL.substitute(counter=i, name=name, msg=msg))
        i += 1
        
    body = BILATERAL_SUCCESS_MAIL_BODY_TMPL.substitute(
        id = id,
        help_url=HELP_URL,
        original_subject=mail['Subject'],
        original_mail=mail['Body'].replace("\n","\n<br>"),
        user_rows=user_rows
        )

    send_mail(to, subject, body)
    
def reply_delete_success(mail, to, trans_id, trans_desc):
    subject = "Re: %s" % mail['Subject']
    
    body = DELETE_SUCCESS_MAIL_BODY_TMPL.substitute(
        sender=combineNameMail(mail['From']),
        help_url=HELP_URL,
        id=trans_id,
        description=trans_desc,
        original_subject=mail['Subject'],
        original_mail=mail['Body'],
        )
      
    send_mail(to, subject, body)

def reply_get(mail, usermsg, settle_msg, fiterText):
    subject = "Re: %s" % mail['Subject']
    user_rows = ''
    for id, trans_date, description, command, amount, contribution, share, friends in usermsg:
        user_rows = "%s\n%s" % (user_rows, GET_ROW_MSG_TMPL.substitute(
            id=id,
            date=trans_date,
            description=description,
            command=command,
            amount=amount,
            contribution=contribution,
            share=share,
            friends=friends)
        )
        
    body = GET_BODY_TMPL.substitute(
        help_url=HELP_URL,
        original_subject=mail['Subject'],
        original_mail=mail['Body'],
        user_rows=user_rows,
        settle_msg=settle_msg,
        fiterText =fiterText
        )

    tonew =[]
    tonew.append(mail['From'])
    tonew.extend(mail['To'])
    send_mail(tonew, subject, body)

def getUserDate(s, mail):
    """Date format is dd/mm. tzinfo and year are captured from mail."""
    md = mail['Date']
    if s:
        s1 = s.split('/')
        try:
            return datetime.datetime(
                year=md.year, day=int(s1[0]), month=int(s1[1]),
                hour=md.hour, minute=md.minute, second=md.second,
                tzinfo=md.tzinfo)
        except ValueError, e:
            reply_user_error("Invalid date - %s. Error: %s" % (s, str(e),), mail)
            raise UserError()
    else:
        return md

def get_cmd(subject):
    subject = subject.strip()
    m = CMD_PART_RE.match(subject)
    if m is None:
        return None

    return m.group(1)[0]

def getAmt(amt, mail):
    try:
        return float(amt)
    except ValueError:
        reply_user_error(("Invalid amount given: %",amt), mail)
        return None

def admin_only(f):
    def new_f(mail):
        if mail['From'][1] in [mail_address for name, mail_address in admin_emails]:
            f(mail)
        else:
            reply_user_error('You are not authorised to issue this command.', mail)
    return new_f




