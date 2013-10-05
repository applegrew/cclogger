from __future__ import absolute_import

import sys

run_api = False
if len(sys.argv) < 2:
	run_api = True
else:
	if sys.argv[1] == 'api':
		run_api = True

if run_api:
	from cclogger import api_main
	application = api_main.main_run()
else:
	from cclogger import poll_main
	poll_main.main_run()

