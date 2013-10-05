from . import peewee
from . import db_name, db_user, db_pass, db_host, db_port, verbose

db_args = {}
if db_host:
    db_args['host'] = db_host
if db_port:
    db_args['port'] = db_port
if db_user:
    db_args['user'] = db_user
if db_pass:
    db_args['passwd'] = db_pass

if verbose: print 'Instantiating DB with: %s/%s@%s:%s' % (db_user if db_user else 'x', db_pass if db_pass else 'x',
    db_host if db_host else 'x', str(db_port) if db_port else 'x')

db = peewee.MySQLDatabase(db_name, **db_args)

class BaseModel(peewee.Model):
    class Meta:
        database = db

class BaseMailServerConfig(BaseModel):
    at_domain = peewee.CharField(unique=True)
    hostname = peewee.CharField(max_length=255)
    port = peewee.IntegerField()
    use_ssl = peewee.BooleanField()

    def __unicode__(self):
        return u"%s (%s)" % (self.at_domain, self.conf_type)

class InMailServerConfig(BaseMailServerConfig):
    pass

class OutMailServerConfig(BaseMailServerConfig):
    pass

class User(BaseModel):
    name = peewee.CharField(max_length=200)

    def __unicode__(self):
        return self.name

class SmsPref(BaseModel):
    user = peewee.ForeignKeyField(User, cascade=True, db_index=True)
    addresses = peewee.CharField(max_length=200) # ` delimited addresses

    def get_addresses(self):
        a = self.addresses
        if a:
            return a.split('`')
        else:
            return None
    def set_addresses(self, arr_address):
        self.addresses = '`'.join(arr_address)

    def __unicode__(self):
        return u"%s => %s" % (self.name, self.addresses)

class UserMail(BaseModel):
    email = peewee.CharField(unique=True, max_length=254)
    password = peewee.CharField(max_length=128)
    in_mail_config = peewee.ForeignKeyField(InMailServerConfig, db_index=True, default=-1)
    out_mail_config = peewee.ForeignKeyField(OutMailServerConfig, db_index=True, default=-1)
    is_dummy = peewee.BooleanField() # If true then do not check mails of this id. This is meant only for authentication.
    is_bad = peewee.BooleanField(default=False)
    error = peewee.CharField(max_length=100, null=True)
    #partition = peewee.CharField(max_length=5) # For future extension so that different parallel instances can check disjoint batches of mail boxes.
    is_sms = peewee.BooleanField(db_index=True, default=False)

    def __unicode__(self):
        return u'%s (is_sms:%s)' % (self.email, str(self.is_sms))

    class Meta:
        indexes = (
            (('email', 'password'), False),
            (('is_dummy', 'is_bad'), False),
            )

class UserMailMap(BaseModel):
    user = peewee.ForeignKeyField(User, db_index=True, cascade=True)
    user_mail = peewee.ForeignKeyField(UserMail, cascade=True)
    is_referenced = peewee.BooleanField(default=False)

    def __unicode__(self):
        return u'%s <=> %s' % (self.user, self.user_mail)

    class Meta:
        indexes = (
            (('user_mail', 'is_referenced'), False),
            )

class Place(BaseModel):
    place_name = peewee.CharField(max_length=300)
    kind = peewee.CharField(max_length=200, default='Unknown')
    is_manual_generated = peewee.BooleanField(default=False) # If True this record is created manually so same place in different rows can be clubbed together.
    equivalent_manual_place = peewee.ForeignKeyField('self', null=True)

    def __unicode__(self):
        return self.place_name

    class Meta:
        indexes = (
            (('place_name', 'is_manual_generated'), False),
            (('kind', 'is_manual_generated'), False),
            )

class TransactionAlert(BaseModel):
    user_mail = peewee.ForeignKeyField(UserMail, cascade=True)
    uid = peewee.CharField(max_length=255)
    from_address = peewee.CharField(max_length=254)
    date = peewee.DateTimeField(db_index=True)
    card_no = peewee.CharField(max_length=40)
    currency = peewee.CharField(max_length=3)
    amt = peewee.DecimalField(decimal_places=2, auto_round=True, always_float=True)
    place = peewee.ForeignKeyField(Place)
    meta1 = peewee.CharField(max_length=50, db_index=True, null=True)
    created_by = peewee.CharField(max_length=10, db_index=True)

    def __unicode__(self):
        return u'%s %.2f transaction on card %s.' % (self.currency, self.amt, self.card_no)

    class Meta:
        indexes = (
            (('user_mail', 'uid'), False),
            (('card_no', 'currency', 'place'), False),
            )

