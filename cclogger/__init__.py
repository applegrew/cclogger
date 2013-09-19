from .globals import verbose, info, timeout, db_host, db_port, db_name, db_user, db_pass, \
    admin_emails, SLEEP_PERIOD, consecutive_err_threshold, normalized_tz, max_clients_pool, \
    server_email, server_mail_host, server_mail_port, server_mail_use_ssl, server_email_password, \
    salt, cipher_key, dev

normalized_tz_obj = None

def load_config():
    import ConfigParser
    import email.utils
    import os

    global verbose, admin_emails, normalized_tz, normalized_tz_obj, info, timeout, max_clients_pool, \
        db_host, db_port, db_name, db_user, db_pass, SLEEP_PERIOD, consecutive_err_threshold, \
        server_email, server_mail_host, server_mail_port, server_mail_use_ssl, server_email_password, \
        salt, cipher_key, dev
        
    # Read the config file
    config = ConfigParser.SafeConfigParser(defaults = {
        'max_clients_pool': str(max_clients_pool),
        'timeout': str(timeout),
        'verbose': str(verbose),
        'info': str(info),
        'normalized_tz': normalized_tz,
        'poll_invertal': str(SLEEP_PERIOD),
        'consecutive_err_threshold': str(consecutive_err_threshold),
        'db_username': db_user,
        'db_password': db_pass,
        'db_host': db_host,
        'db_port': str(db_port),
        'server_email': server_email,
        'server_mail_host': server_mail_host,
        'server_mail_port': str(server_mail_port),
        'server_mail_use_ssl': str(server_mail_use_ssl),
        'server_email_password': server_email_password,
        'salt': salt,
        'cipher_key': cipher_key,
        'dev': str(dev),
        'admin_emails': ''
        })
    config.read(os.path.dirname(__file__) + '/settings.ini')

    max_clients_pool = config.getint('server', 'max_clients_pool')
    timeout = config.getint('server', 'timeout')

    server_email = config.get('server', 'server_email')
    server_mail_host = config.get('server', 'server_mail_host')
    server_mail_port = config.getint('server', 'server_mail_port')
    server_mail_use_ssl = config.getboolean('server', 'server_mail_use_ssl')
    server_email_password = config.get('server', 'server_email_password')

    db_host = config.get('db', 'db_host')
    db_port = config.getint('db', 'db_port') # Value of 0 signifies no port value set.
    db_name = config.get('db', 'db_schema')
    db_pass = config.get('db', 'db_password')
    db_user = config.get('db', 'db_username')

    admin_emails = config.get('account', 'admin_emails')
    if not admin_emails:
        admin_emails = []
    else:
        admin_emails = [email.utils.parseaddr(e.lower().strip()) for e in admin_emails.split(',')]

    dev = config.getboolean('app', 'dev')
    verbose = config.getboolean('app', 'verbose')
    info = config.getboolean('app', 'info') or verbose
    SLEEP_PERIOD = config.getint('app', 'poll_invertal')
    consecutive_err_threshold = config.getint('app', 'consecutive_err_threshold')
    salt = config.get('app', 'salt')
    cipher_key = config.get('app', 'cipher_key')

    normalized_tz = config.get('app', 'normalized_tz')
    import pytz
    normalized_tz_obj = pytz.timezone(normalized_tz)

    if verbose:
        import logging
        logging.basicConfig(format='\n---\n%(asctime)s %(message)s\n---\n', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
        logger = logging.getLogger('peewee')
        logger.setLevel(logging.DEBUG)
    
    if info:
        print 'config loaded'

load_config()
