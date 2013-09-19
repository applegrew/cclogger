from .model import InMailServerConfig, OutMailServerConfig, User, UserMail, UserMailMap, TransactionAlert, \
	Place, PlaceManualPlaceMap, SmsPref

recreate = True
if recreate:
	TransactionAlert.drop_table(fail_silently=True)
	PlaceManualPlaceMap.drop_table(fail_silently=True)
	Place.drop_table(fail_silently=True)
	UserMailMap.drop_table(fail_silently=True)
	UserMail.drop_table(fail_silently=True)
	SmsPref.drop_table(fail_silently=True)
	User.drop_table(fail_silently=True)
	OutMailServerConfig.drop_table(fail_silently=True)
	InMailServerConfig.drop_table(fail_silently=True)

InMailServerConfig.create_table(fail_silently=True)
OutMailServerConfig.create_table(fail_silently=True)
User.create_table(fail_silently=True)
SmsPref.create_table(fail_silently=True)
UserMail.create_table(fail_silently=True)
UserMailMap.create_table(fail_silently=True)
Place.create_table(fail_silently=True)
PlaceManualPlaceMap.create_table(fail_silently=True)
TransactionAlert.create_table(fail_silently=True)

d = InMailServerConfig.get_or_create(at_domain="gmail.com")
d.hostname = "imap.gmail.com"
d.port=993
d.use_ssl=True
d.save()

d = OutMailServerConfig.get_or_create(at_domain="gmail.com")
d.hostname = "smtp.gmail.com"
d.port=465
d.use_ssl=True
d.save()
