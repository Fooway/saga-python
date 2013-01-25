
""" dummy filesystem adaptor implementation """

import os
import shutil

import saga.url
import saga.adaptors.cpi.base
import saga.adaptors.cpi.filesystem
import saga.utils.misc

SYNC_CALL  = saga.adaptors.cpi.base.SYNC_CALL
ASYNC_CALL = saga.adaptors.cpi.base.ASYNC_CALL


###############################################################################
# adaptor info
#

_ADAPTOR_NAME          = 'saga.adaptor.dummysystem.local'
_ADAPTOR_SCHEMAS       = ['dummy']
_ADAPTOR_OPTIONS       = [
    { 
    'category'         : 'saga.engine',
    'name'             : 'enable_ctrl_c', 
    'type'             : bool, 
    'default'          : True,
    'valid_options'    : [True, False],
    'documentation'    : 'install SIGINT signal handler to abort application.',
    'env_variable'     : None
    },
    { 
    'category'         : 'saga.engine',
    'name'             : 'load_beta_adaptors', 
    'type'             : bool, 
    'default'          : False,
    'valid_options'    : [True, False],
    'documentation'    : 'load adaptors which are marked as beta (i.e. not released).',
    'env_variable'     : None
    }
]
_ADAPTOR_CAPABILITIES  = {}

_ADAPTOR_DOC           = {
    'name'             : _ADAPTOR_NAME,
    'cfg_options'      : _ADAPTOR_OPTIONS, 
    'capabilities'     : _ADAPTOR_CAPABILITIES,
    'description'      : 'The local filesystem adaptor.',
    'details'          : """This adaptor interacts with local filesystem, by
                            using the (POSIX like) os and shutil Python packages.
                            It is named 'dummy', as this adaptor is only used
                            for testing and debugging -- it is *not* good for
                            production.
                            """,
    'schemas'          : {'dummy' : 'an invented schema.'},
}

_ADAPTOR_INFO          = {
    'name'             : _ADAPTOR_NAME,
    'version'          : 'v0.1beta',
    'schemas'          : _ADAPTOR_SCHEMAS,
    'cpis'             : [{
        'type'         : 'saga.filesystem.Directory',
        'class'        : 'DummyDirectory'
        }, 
        {
        'type'         : 'saga.filesystem.File',
        'class'        : 'DummyFile'
        }
    ]
}


###############################################################################
# The adaptor class

class Adaptor (saga.adaptors.cpi.base.AdaptorBase):
    """ 
    This is the actual adaptor class, which gets loaded by SAGA (i.e. by the
    SAGA engine), and which registers the CPI implementation classes which
    provide the adaptor's functionality.
    """

    def __init__ (self) :

        saga.adaptors.cpi.base.AdaptorBase.__init__ (self, _ADAPTOR_INFO, _ADAPTOR_OPTIONS)


    def sanity_check (self) :
        pass



###############################################################################
#
class DummyDirectory (saga.adaptors.cpi.filesystem.Directory) :

    def __init__ (self, api, adaptor) :
        saga.adaptors.cpi.CPIBase.__init__ (self, api, adaptor)


    @SYNC_CALL
    # FIXME: where are the flags?
    def init_instance (self, adaptor_state, url, flags, session) :

        self._url     = url
        self._flags   = flags
        self._session = session

        self._init_check ()

        return self._api


    @ASYNC_CALL
    def init_instance_async (self, adaptor_state, url, flags, session, ttype) :
        self._url     = url
        self._flags   = flags
        self._session = session

        self._init_check ()
        
        t = saga.task.Task (self, 'init_instance', {'ttype'   : ttype, 
                                                    'url'     : url, 
                                                    'flags'   : flags, 
                                                    'session' : session})
        t._set_result (saga.dummysystem.Directory (url, flags, session, _adaptor_name=_ADAPTOR_NAME))
        t._set_state  (saga.task.DONE)

        return t


    def _init_check (self) :

        url   = self._url
        flags = self._flags 

        if not saga.utils.misc.url_is_local (url) :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (not local)"     %  url)
        if url.port :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has port)"      %  url)
        if url.fragment :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has fragment)"  %  url)
        if url.query :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has query)"     %  url)
        if url.username :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has username)"  %  url)
        if url.password :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has password)"  %  url)

        self._path = url.path
        path       = url.path

        if not os.path.exists (path) :

            if saga.dummysystem.CREATE & flags :
                if saga.dummysystem.CREATE_PARENTS & flags :
                    try :
                        os.makedirs (path)
                    except Exception as e :
                        raise saga.exceptions.NoSuccess ("Could not 'mkdir -p %s': %s)"  \
                                                        % (path, str(e)))
                else :
                    try :
                        os.mkdir (path)
                    except Exception as e :
                        raise saga.exceptions.NoSuccess ("Could not 'mkdir %s': %s)"  \
                                                        % (path, str(e)))
            else :
                raise saga.exceptions.BadParameter ("Cannot handle url %s (directory does not exist)"  \
                                                   %  path)
        
        if not os.path.isdir (path) :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (is not a directory)"  \
                                               %  path)
        


    @SYNC_CALL
    def get_url (self) :

        return self._url


    @SYNC_CALL
    def open (self, url, flags) :
        
        if not url.scheme and not url.host : 
            url = saga.url.Url (str(self._url) + '/' + str(url))

        f = saga.dummysystem.File (url, flags, self._session, _adaptor_name=_ADAPTOR_NAME)
        return f


######################################################################
#
# file adaptor class
#
class DummyFile (saga.adaptors.cpi.filesystem.File) :

    def __init__ (self, api, adaptor) :
        saga.adaptors.cpi.CPIBase.__init__ (self, api, adaptor)


    @SYNC_CALL
    def init_instance (self, adaptor_state, url, flags, session) :

        self._url     = url
        self._flags   = flags
        self._session = session

        self._init_check ()

        return self


    @ASYNC_CALL
    def init_instance_async (self, adaptor_state, url, flags, session, ttype) :

        self._url     = url
        self._flags   = flags
        self._session = session

        self._init_check ()
        
        t = saga.task.Task ()

        t._set_result (saga.dummysystem.File (url, flags, session, _adaptor_name=_ADAPTOR_NAME))
        t._set_state  (saga.task.DONE)

        return t


    def _init_check (self) :

        url   = self._url
        flags = self._flags 

        if not saga.utils.misc.url_is_local (url) :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (not local)"     %  url)
        if url.port :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has port)"      %  url)
        if url.fragment :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has fragment)"  %  url)
        if url.query :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has query)"     %  url)
        if url.username :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has username)"  %  url)
        if url.password :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (has password)"  %  url)

        self._path = url.path
        path       = url.path

        if not os.path.exists (path) :

            (dirname, filename) = os.path.split (path)

            if not filename :
                raise saga.exceptions.BadParameter ("Cannot handle url %s (names directory)"  \
                                                 %  path)

            if not os.path.exists (dirname) :
                if saga.filesystem.CREATE_PARENTS & flags :
                    try :
                        os.makedirs (path)
                    except Exception as e :
                        raise saga.exceptions.NoSuccess ("Could not 'mkdir -p %s': %s)"  \
                                                        % (path, str(e)))
                else :
                    raise saga.exceptions.BadParameter ("Cannot handle url %s (parent dir does not exist)"  \
                                                     %  path)
        
            if not os.path.exists (filename) :
                if saga.filesystem.CREATE & flags :
                    try :
                        open (path, 'w').close () # touch
                    except Exception as e :
                        raise saga.exceptions.NoSuccess ("Could not 'touch %s': %s)"  \
                                                        % (path, str(e)))
                else :
                    raise saga.exceptions.BadParameter ("Cannot handle url %s (file does not exist)"  \
                                                     %  path)
        
        if not os.path.isfile (path) :
            raise saga.exceptions.BadParameter ("Cannot handle url %s (is not a file)"  \
                                               %  path)

    @SYNC_CALL
    def get_url (self) :
        return self._url

    @ASYNC_CALL
    def get_url_async (self, ttype) :

        t = saga.task.Task ()

        t._set_state  = saga.task.Done
        t._set_result = self._url

        return t


    @SYNC_CALL
    def get_size_self (self) :
        return os.path.getsize (self._url.path)


    @ASYNC_CALL
    def get_size_self_async (self, ttype) :

        t = saga.task.Task ()

        t._set_result (os.path.getsize (self._url.path))
        t._set_state  (saga.task.DONE)

        return t


    @SYNC_CALL
    def copy_self (self, target, flags) :

        tgt_url = saga.url.Url (target)
        tgt     = tgt_url.path
        src     = self._url.path

        if tgt_url.schema :
            if not tgt_url.schema in _ADAPTOR_SCHEMAS :
                raise saga.exceptions.BadParameter ("Cannot handle url %s (unknown schema)" %  target)

        if tgt[0] != '/' :
            tgt = "%s/%s"   % (os.path.dirname (src), tgt)

        print " copy %s %s" % (self._url, tgt)
        shutil.copy2 (src, tgt)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
