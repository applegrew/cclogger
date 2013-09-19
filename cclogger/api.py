import imaplib

from .common_util import JsonResponse, get_at_domain, ApiException, encrypt, route_with_option, is_valid_email, \
    convert_url_date_to_pydate
from .client import MailClient
from .model import User, UserMail, InMailServerConfig, OutMailServerConfig, UserMailMap, TransactionAlert, Place, \
    PlaceManualPlaceMap, SmsPref, db
from .bottlesession import PickleSession
from .peewee import fn
from .parse import SmsParseCentral

session_manager = PickleSession()

def validate_email_pass(email, password):
    if not is_valid_email(email):
        raise ApiException('EMAIL_INVALID', 'Provided email \'%s\' is not valid.' % email)

    at_domain = get_at_domain(email)
    try:
        in_conf = InMailServerConfig.get(InMailServerConfig.at_domain == at_domain)
    except InMailServerConfig.DoesNotExist:
        raise ApiException('IN_MAIL_TYPE_UNKNOWN', 'Email of type %s is not supported.' % at_domain)

    try:
        out_conf = OutMailServerConfig.get(OutMailServerConfig.at_domain == at_domain)
    except OutMailServerConfig.DoesNotExist:
        raise ApiException('OUT_MAIL_TYPE_UNKNOWN', 'Email of type %s is not supported.' % at_domain)

    client = MailClient(in_conf, out_conf)
    try:
        client.open_connection(email, password)
    except (imaplib.IMAP4.error, imaplib.IMAP4_SSL.error) as e:
        raise ApiException('AUTH_FAIL', 'Could not login to mail server. Got: %s' % e)

    client.close_connection()

    return (at_domain, in_conf, out_conf)

@route_with_option('/signup_user', 'PUT')
@JsonResponse
def signup_user(email, password, name, **kwargs):
    if UserMail.select().where(UserMail.email == email).exists():
        raise ApiException('USER_EXISTS', 'Email provided already exists.')

    at_domain, in_conf, out_conf = validate_email_pass(email, password)

    with db.transaction():
        password = encrypt(password, True)
        user = User.create(name=name)
        usermail = UserMail.create(email=email, password=password, user=user, is_dummy=True,
            in_mail_config=in_conf, out_mail_config=out_conf)
        usermailmap = UserMailMap.create(user=user, user_mail=usermail)
    
    return {'EncryptedPassword': password}
        
@route_with_option('/update_email_password', 'POST')
@JsonResponse
def update_email_password(email, new_password, **kwargs):
    if not UserMail.select().where(UserMail.email == email).exists():
        raise ApiException('USER_NOT_EXIST', 'Email provided does not exist.')

    validate_email_pass(email, new_password)
    new_password = encrypt(new_password, True)

    usermail = UserMail.get(UserMail.email == email)
    usermail.password = new_password
    usermail.is_bad = False
    usermail.save()
    
    return {'EncryptedPassword': new_password}

@route_with_option('/login', 'POST')
@JsonResponse
def login(email, password, isEncrypted, **kwargs):
    isEncrypted = True if isEncrypted == 'Y' else False
    if not isEncrypted:
        password = encrypt(password, True)
    try:
        login_usermail = UserMail.get((UserMail.email == email) & (UserMail.password == password))
    except UserMail.DoesNotExist:
        raise ApiException('AUTH_FAIL', 'Wrong email or password.')

    try:
        login_usermailmap = UserMailMap.get((UserMailMap.user_mail == login_usermail)
            & (UserMailMap.is_referenced == False))
    except UserMailMap.DoesNotExist:
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    user = login_usermailmap.user

    token = session_manager.allocate_new_token()
    data = {'email': email, 'userid': user.id}
    session_manager.save(token, data)
    return {'Token': token, 'EncryptedPassword': password}

@route_with_option('/logout', 'POST')
@JsonResponse
def logout(token, **kwargs):
    session_manager.kill(token)

@route_with_option('/add_account', 'PUT')
@JsonResponse
def add_account(token, email, password, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']

    if email == login_email:
        validate_email_pass(email, password)
        password = encrypt(password, True)

        usermail = UserMail.get(UserMail.email == email)
        usermail.is_dummy = False
        usermail.password = password
        usermail.is_bad = False
        usermail.save()
    else:
        userid = data['userid']

        try:
            user = User.get(User.id == userid)
        except User.DoesNotExist:
            session_manager.kill(token)
            raise ApiException('INVALID_LOGIN', 'Bad login state.')

        create_usermailmap = False

        with db.transaction():
            try:
                usermail = UserMail.get(UserMail.email == email)
                usermailmap = UserMailMap.get((UserMailMap.user_mail == usermail)
                    & (UserMailMap.is_referenced == False))
                if usermailmap.user.id != user.id:
                    raise ApiException('BAD_EMAIL', 'This email cannot be used.')

                validate_email_pass(email, password)
                usermail.is_bad = False
            except UserMail.DoesNotExist:
                create_usermailmap = True
                at_domain, in_conf, out_conf = validate_email_pass(email, password)
                usermail = UserMail(email=email, in_mail_config=in_conf, out_mail_config=out_conf)

            password = encrypt(password, True)
            usermail.password = password
            usermail.is_dummy = False
            usermail.save()

            if create_usermailmap:
                UserMailMap.create(user=user, user_mail=usermail)

    return {'EncryptedPassword': password}
                
@route_with_option('/report/<token>/<from_date:date>/<to_date:date>/<only_totals>', 'GET')
@JsonResponse
def report(token, from_date, to_date, only_totals, **kwargs):
    only_totals = True if only_totals == 'Y' else False

    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']
    userid = data['userid']

    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    usermails = UserMailMap.select().where(UserMailMap.user == user) # This is report (read only) api so select referenced usermailmaps too.
    
    out = dict()
    out['Result'] = res = dict()

    for t in TransactionAlert.select(
        TransactionAlert.card_no, TransactionAlert.currency, fn.Sum(TransactionAlert.amt).alias('total_amt')) \
        .where((TransactionAlert.user_mail << usermails) & (TransactionAlert.date >= from_date) & (TransactionAlert.date <= to_date)) \
        .group_by(TransactionAlert.card_no, TransactionAlert.currency):
        
        card_details = res.get(t.card_no, dict())
        total = card_details.get('Totals', [])

        total.append({'Currency': t.currency, 'Amt': t.total_amt})
        card_details['Totals'] = total
        res[t.card_no] = card_details

    if not only_totals:

        for t in TransactionAlert.select(
            TransactionAlert.card_no, TransactionAlert.currency, TransactionAlert.place,
            fn.Sum(TransactionAlert.amt).alias('total_amt')) \
            .where((TransactionAlert.user_mail << usermails) & (TransactionAlert.date >= from_date) & (TransactionAlert.date <= to_date)) \
            .group_by(TransactionAlert.card_no, TransactionAlert.currency, TransactionAlert.place):

            card_details = res.get(t.card_no, dict())
            places = card_details.get('Places', [])

            places.append({'Currency': t.currency, 'Amt': t.total_amt, 'Place': t.place.place_name, 'Kind': t.place.kind})
            card_details['Places'] = places
            res[t.card_no] = card_details

        for t in TransactionAlert.select(
            TransactionAlert.card_no, TransactionAlert.currency, Place.kind, fn.Sum(TransactionAlert.amt).alias('total_amt')) \
            .dicts() \
            .join(Place) \
            .where((TransactionAlert.user_mail << usermails)
                & (TransactionAlert.date >= from_date) & (TransactionAlert.date <= to_date)) \
            .group_by(TransactionAlert.card_no, TransactionAlert.currency, Place.kind):

            card_details = res.get(t['card_no'], dict())
            kinds = card_details.get('Kinds', [])

            kinds.append({'Currency': t['currency'], 'Amt': t['total_amt'], 'Kind': t['kind']})
            card_details['Kinds'] = kinds
            res[t['card_no']] = card_details

    return out

@route_with_option('/add_sms', 'PUT')
@JsonResponse
def add_sms(token, from_address, body, date, smsid, **kwargs):
    import uuid

    date = convert_url_date_to_pydate(date)
    if not date:
        raise ApiException('DATE_INVALID', 'Given date is invalid.')

    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']
    userid = data['userid']

    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    sq = UserMail.select().join(UserMailMap).where((UserMail.is_sms == True)
        & (UserMailMap.user == user)
        & (UserMailMap.is_referenced == False))

    if sq.exists():
        usersms = sq.get()
    else:
        with db.transaction():
            usersms = UserMail.create(email=uuid.uuid4(), password="-", is_dummy=True, is_sms=True)
            UserMailMap.create(user=user, user_mail=usersms)

    if TransactionAlert.select().where((TransactionAlert.user_mail == usersms) & (TransactionAlert.uid == smsid)).exists():
        a = ApiException('SMS_ALREADY_EXISTS', 'For the given user an sms is already registered with the given id.')
        a.set_extra({
            'Smsid': smsid
            })
        raise a
    else:
        SmsParseCentral.getInstance().parse_sms(from_address, body, date, date.tzinfo, smsid, usersms)
        return {'Smsid': smsid}

@route_with_option('/user_pref_sms_addresses/<token>', 'GET')
@JsonResponse
def user_pref_sms_addresses(token, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']
    userid = data['userid']

    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    try:
        return {'Addresses': SmsPref.get(user=user).get_addresses()}
    except SmsPref.DoesNotExist:
        return {'Addresses': SmsParseCentral.getInstance().get_addresses_interested()}

@route_with_option('/sms_opt_in_for_banks/<token>', 'GET')
@JsonResponse
def get_sms_opt_in_for_banks(token, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']
    userid = data['userid']

    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')
    
    from sets import Set

    selected_parsers = Set()
    all_parsers = Set(SmsParseCentral.getInstance().get_parser_names())
    parsers = SmsParseCentral.getInstance().get_parsers()
    try:
        for address in SmsPref.get(user=user).get_addresses():
            if address in parsers:
                selected_parsers.add(parsers[address].get_name())
    except SmsPref.DoesNotExist:
        selected_parsers = all_parsers # Default is that all are selected.

    out = []
    for parser_name in selected_parsers:
        out.append({'Name': parser_name, 'Value': True})

    for parser_name in (all_parsers - selected_parsers):
        out.append({'Name': parser_name, 'Value': False})

    return {'Banks': out}

@route_with_option('/sms_opt_in_for_banks', 'POST')
@JsonResponse
def sms_opt_in_for_banks(token, banks, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    login_email = data['email']
    userid = data['userid']

    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    try:
        pref = SmsPref.get(user=user)
    except SmsPref.DoesNotExist:
        pref = SmsPref()
        pref.user = user

    pref.set_addresses(SmsParseCentral.getInstance().get_addresses_for_parser_names(banks))
    perf.save()
    
@route_with_option('/add_reference_accounts', 'PUT')
@JsonResponse
def add_reference_accounts(token, accounts, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    userid = data['userid']
    
    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    with db.transaction():
        for account in accounts:
            usermail_id = account['usermail_id']
            referer_userid = account['referer_userid']
            
            if referer_userid == userid:
                raise ApiException('BAD_INPUT', 'Given referer_userid is incorrect.')
    
            try:
                usermail = UserMail.get(UserMail.id == usermail_id)
            except UserMail.DoesNotExist:
                raise ApiException('BAD_INPUT', 'Given usermail_id is incorrect.')
            
            if not UserMailMap.get((UserMailMap.user_mail == usermail)
                    & (UserMailMap.user == user)
                    & (UserMailMap.is_referenced == False)).exists():
                raise ApiException('BAD_INPUT', 'Given usermail_id is incorrect.')
                
            try:
                referer_user = User.get(User.id == referer_userid)
            except User.DoesNotExist:
                raise ApiException('BAD_INPUT', 'Given referer_userid is incorrect.')
                
            UserMailMap.create(user=referer_user, user_mail=usermail, is_referenced=True)
    
@route_with_option('/remove_reference_accounts', 'POST')
@JsonResponse
def remove_reference_accounts(token, reference_usermailmap_ids, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    userid = data['userid']
    
    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')

    with db.transaction():
        for reference_usermailmap_id in reference_usermailmap_ids:
            try:
                ref_usermailmap = UserMailMap.get((UserMailMap.id == reference_usermailmap_id)
                    & (UserMailMap.is_referenced == True))
            except UserMailMap.DoesNotExist:
                raise ApiException('BAD_INPUT', 'Given reference_usermailmap_id is incorrect.')
                
            if not UserMailMap.get((UserMailMap.user_mail == ref_usermailmap.user_mail)
                    & (UserMailMap.user == user)
                    & (UserMailMap.is_referenced == False)).exists():
                raise ApiException('BAD_INPUT', 'Given reference_usermailmap_id is incorrect.')
                
            ref_usermailmap.delete_instance()
            
@route_with_option('/get_reference_accounts', 'GET')
@JsonResponse
def get_reference_accounts(token, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    userid = data['userid']
    
    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')
        
    owned_usermails = UserMail.select().join(UserMailMap).where(
                                  (UserMailMap.user == user)
                                & (UserMailMap.is_referenced == False))

    result = list()
    out = dict()
    out['Accounts'] = result    

    for ref_usermailmap in UserMailMap.select().where((UserMailMap.user == user)
                                & (UserMailMap.is_referenced == True)
                                & (UserMailMap.user_mail << owned_usermails)):

        result.append({
            'Reference_usermailmap_id': ref_usermailmap.id,
            'Referer_userid': ref_usermailmap.user.id,
            'Referer_name': ref_usermailmap.user.name
        })

    return out
    
@route_with_option('/get_accounts', 'GET')
@JsonResponse
def get_accounts(token, **kwargs):
    data = session_manager.load(token)
    if not data:
        raise ApiException('BAD_TOKEN', 'Invalid token provided. Login again.')

    session_manager.mark_accessed(token)
    userid = data['userid']
    
    try:
        user = User.get(User.id == userid)
    except User.DoesNotExist:
        session_manager.kill(token)
        raise ApiException('INVALID_LOGIN', 'Bad login state.')
        
    owned_usermails = UserMail.select().join(UserMailMap).where(
                                  (UserMailMap.user == user)
                                & (UserMailMap.is_referenced == False))

    result = list()
    out = dict()
    out['Accounts'] = result    

    for usermail in UserMail.select().join(UserMailMap).where(
                          (UserMailMap.user == user)
                        & (UserMailMap.is_referenced == False)):

        result.append({
            'Usermail_id': usermail.id,
            'Usermail_email': usermail.email,
            'Is_sms': usermail.is_sms
        })

    return out