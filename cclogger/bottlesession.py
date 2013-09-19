#!/usr/bin/env python
#
#  Bottle session manager.  See README for full documentation.
#
#  Adapted by: AppleGrew from https://github.com/linsomniac/bottlesession
#
#  License: 3-clause BSD

from __future__ import with_statement

from . import bottle
import pickle
import os
import uuid


class BaseSession(object):
    '''Base class which implements some of the basic functionality required for
    session managers.  Cannot be used directly.
    '''

    def load(self, token):
        raise NotImplementedError

    def save(self, token, data):
        raise NotImplementedError

    def kill(self, token):
        raise NotImplementedError

    def make_token(self):
        return str(uuid.uuid4())

    def allocate_new_token(self):
        #  retry allocating a unique sessionid
        for i in xrange(100):
            token = self.make_token()
            if not self.load(token):
                return token
        raise ValueError('Unable to allocate unique token')

class PickleSession(BaseSession):
    '''Class which stores session information in the file-system.

    :param session_dir: Directory that session information is stored in.
            (default: ``'/tmp/bottlesession'``).
    '''
    def __init__(self, session_dir='/tmp/bottlesession', *args, **kwargs):
        super(PickleSession, self).__init__(*args, **kwargs)
        self.session_dir = session_dir
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)

    def get_session_path(self, token):
        return os.path.join(self.session_dir, 'session-%s' % token)

    def load(self, token):
        filename = self.get_session_path(token)
        if not os.path.exists(filename):
            return None
        with open(filename, 'r') as fp:
            session = pickle.load(fp)
        return session

    def save(self, token, data):
        fileName = self.get_session_path(token)
        tmpName = fileName + '.' + str(uuid.uuid4())
        with open(tmpName, 'w') as fp:
            self.session = pickle.dump(data, fp)
        os.rename(tmpName, fileName)

    def kill(self, token):
        filename = self.get_session_path(token)
        if os.path.exists(filename):
            os.remove(filename)

    def mark_accessed(self, token):
        filename = self.get_session_path(token)
        if os.path.exists(filename):
            os.utime(filename, None)
    