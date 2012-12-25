# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

__author__    = "Ole Christian Weidner"
__copyright__ = "Copyright 2012, The SAGA Project"
__license__   = "MIT"

""" Provides the SAGA runtime. """

import signal
import sys

from   saga.utils.singleton import Singleton
from   saga.engine.logger   import getLogger, get_traceback
from   saga.engine.config   import getConfig, Configurable

import saga.engine.registry  # adaptors to load


##################################################################################
# a define to make get_adaptor more readable
ANY_ADAPTOR = None

############# These are all supported options for saga.engine ####################
##
_config_options = [
    { 
    'category'      : 'saga.engine',
    'name'          : 'enable_ctrl_c', 
    'type'          : bool, 
    'default'       : True,
    'valid_options' : [True, False],
    'documentation' : 'install SIGINT signal handler to abort application.',
    'env_variable'  : None
    },
    { 
    'category'      : 'saga.engine',
    'name'          : 'load_beta_adaptors', 
    'type'          : bool, 
    'default'       : False,
    'valid_options' : [True, False],
    'documentation' : 'load adaptors which are marked as beta (i.e. not released).',
    'env_variable'  : None
    }
]

################################################################################
##
def getEngine():

    """ Return a handle to the Engine singleton."""
    return Engine() 


################################################################################
##
class Engine(Configurable): 
    """ Represents the SAGA engine runtime system.

        The Engine is a singleton class that takes care of adaptor
        loading and management, and which binds adaptor instances to
        API object instances.   The Engine singleton is implicitly
        instantiated as soon as SAGA is imported into Python.  It
        will, on creation, load all available adaptors.  Adaptors
        modules MUST provide an 'Adaptor' class, which will register
        the adaptor in the engine with information like these
        (simplified)::

          _ADAPTOR_INFO = {
            'name'    : _adaptor_name,
            'cpis'    : [{ 
              'type'    : 'saga.job.Job',
              'class'   : 'LocalJob',
              'schemas' : ['fork', 'local']
              }, 
              { 
              'type'    : 'saga.job.Service',
              'class'   : 'LocalJobService',
              'schemas' : ['fork', 'local']
              } 
            ]
          }

        where 'class' points to the actual adaptor classes, and
        'schemas' lists the URL schemas for which those adaptor
        classes should be considered.  Note that schemas are case
        insensitive.  More details on the adaptor registration process
        and on adaptor meta data can be found in the adaptors writer
        guide.

        :todo: add link to adaptor writers documentation.

        While loading adaptors, the Engine builds up an internal
        registry of adaptor classes, hierarchically sorted like this
        (simplified)::

          _cpis = 
          { 
              'job' : 
              { 
                  'gram' : [<gram job  adaptor class>]
                  'ssh'  : [<ssh  job  adaptor class>]
                  'http' : [<aws  job  adaptor class>,
                            <occi job  adaptor class>]
                  ...
              },
              'file' : 
              { 
                  'ftp'  : <ftp  file adaptor class>
                  'scp'  : <scp  file adaptor class>
                  ...
              },
              ...
          }

        to enable simple lookup operations when binding an API object
        to an adaptor class instance.  For example, a
        'saga.job.Service('http://remote.host.net/')' constructor
        would use (simplified)::

          def __init__ (self, url="", session=None) :
              
              for adaptor_class in self._engine._cpis{'job'}{url.scheme}

                  try :
                      self._adaptor = adaptor_class (self, url, session}

                  except saga.Exception e :
                      # adaptor bailed out
                      continue

                  else :
                      # successfully bound to adaptor
                      return

    """
    __metaclass__ = Singleton


    #-----------------------------------------------------------------
    # 
    def __init__(self):
        
        # Engine manages cpis from adaptors
        self._cpis = {}


        # set the configuration options for this object
        Configurable.__init__(self, 'saga.engine', _config_options)
        self._cfg = self.get_config()


        # Initialize the logging
        self._logger = getLogger ('saga.engine')


        # install signal handler, if requested
        if self._cfg['enable_ctrl_c'].get_value () :

            def signal_handler (signal, frame):
                sys.stderr.write ("Ctrl+C caught. Exiting...")
                sys.exit (0)

            self._logger.debug ("installing signal handler for SIGKILL")
            signal.signal (signal.SIGINT, signal_handler)


        # load adaptors
        self._load_adaptors ()




    #-----------------------------------------------------------------
    # 
    def _load_adaptors (self, inject_registry=False):
        """ Try to load all adaptors that are registered in 
            saga.engine.registry.py. This method is called from the constructor. 

            :param inject_registry: Inject a fake registry. *For unit tests only*.
        """
        global_config = getConfig()

        # check if we support alpha/beta adaptos
        allow_betas = self._cfg['load_beta_adaptors'].get_value ()


        if inject_registry is False:
            registry = saga.engine.registry.adaptor_registry
        else:
            self._cpis = {} # reset cpi infos
            registry   = inject_registry

        # attempt to load all registered modules
        for module_name in registry:

            self._logger.info ("Loading  adaptor %s"  %  module_name)


            adaptor_module = None
            try :
                adaptor_module = __import__ (module_name, fromlist=['Adaptor'])

            except Exception as e:
                self._logger.warn  ("Skipping adaptor %s: module loading failed: %s" \
                                %  (module_name, str(e)))
                self._logger.debug (get_traceback())
                continue # skip to next adaptor


            # we expect the module to have an 'Adaptor' class implemented,
            # which returns a info dict for all implemented CPI
            # classes on 'register()'
            adaptor_info = None
            try: 
                adaptor_instance = adaptor_module.Adaptor ()
                adaptor_info     = adaptor_instance.register ()

            except Exception, ex:
                self._logger.warning ("Skipping adaptor %s: loading failed: %s" \
                                   % (module_name, str(ex)))
                self._logger.debug   (get_traceback ())
                continue # skip to next adaptor


            # No exception, but adaptor_info is empty?
            if adaptor_info is None :
                self._logger.warning ("Skipping adaptor %s: adaptor meta data are invalid" \
                                   % module_name)
                self._logger.debug   (get_traceback ())
                continue  # skip to next adaptor


            if  not 'name'    in adaptor_info or \
                not 'cpis'    in adaptor_info or \
                not 'version' in adaptor_info    :
                self._logger.warning ("Skipping adaptor %s: adaptor meta data are incomplete" \
                                   % module_name)
                self._logger.debug   (get_traceback ())
                continue  # skip to next adaptor

            adaptor_name    = adaptor_info['name']
            adaptor_version = adaptor_info['version']
            adaptor_enabled = True   # default unless disabled by 'enabled' option or version filer


            # check if the adaptor has anything to register
            if not 'cpis' in adaptor_info :
                self._logger.warn ("Skipping adaptor %s: does not register any cpis" \
                                % (module_name))
                continue


            # default to 'disabled' if adaptor version is 'alpha' or
            # 'beta', but honor the 'load_beta_adaptors' config option.
            if not allow_betas :

                if 'alpha' in adaptor_version.lower() or \
                   'beta'  in adaptor_version.lower()    :

                    self._logger.info ("Skipping adaptor %s: beta versions are disabled (%s)" \
                                    % (module_name, adaptor_version))
                    continue  # skip to next adaptor


            # get the 'enabled' option in the adaptor's config
            # section (saga.cpi.base ensures it it there after
            # instantiating the module's Adaptor class)
            adaptor_config  = global_config.get_category (adaptor_name)
            adaptor_enabled = adaptor_config['enabled'].get_value ()

            # only load adaptor if it is not disabled via config files
            if adaptor_enabled == False :
                self._logger.info ("Skipping adaptor %s: 'enabled' set to False" \
                                % (module_name))
                continue


            # we got a valid and enabled adaptor info - yay!
            for cpi_info in adaptor_info['cpis'] :

                # check cpi information details for completeness
                if  not 'type'    in cpi_info or \
                    not 'class'   in cpi_info or \
                    not 'schemas' in cpi_info    :
                    self._logger.info ("Skipping adaptor %s cpi: cpi info detail is incomplete" \
                                    % (module_name))
                    continue


                # register adaptor class for the given API type and
                # all listed URL schemas
                cpi_type      = cpi_info['type']
                cpi_classname = cpi_info['class']
                cpi_schemas   = cpi_info['schemas']

                for cpi_schema in cpi_schemas :

                    cpi_schema = cpi_schema.lower ()
                    cpi_class  = getattr (adaptor_module, cpi_classname)

                    # make sure we can register that cpi type
                    if not cpi_type in self._cpis :
                        self._cpis[cpi_type] = {}

                    # make sure we can register that schema
                    if not cpi_schema in self._cpis[cpi_type] :
                        self._cpis[cpi_type][cpi_schema] = []

                    # we register the cpi class, so that we can create
                    # instances as needed, and the adaptor instance,
                    # as that is passed to the cpi class c'tor later
                    # on (the adaptor instance is used to share state
                    # between cpi instances, amongst others)
                    info = {'cpi_class'        : cpi_class, 
                            'adaptor_instance' : adaptor_instance}

                    # make sure this tuple was not registered, yet
                    if not info in self._cpis[cpi_type][cpi_schema] :

                        self._cpis[cpi_type][cpi_schema].append (info)


        # self._dump()


    #-----------------------------------------------------------------
    # 
    def find_adaptors (self, ctype, schema) :
        '''
        Look for a suitable cpi class serving a particular schema
        '''

        adaptor_names = []

        schema = schema.lower ()

        if not ctype in self._cpis :
            return []

        if not schema in self._cpis[ctype] :
            return []


        for info in self._cpis[ctype][schema] :

            adaptor_instance = info['adaptor_instance']
            adaptor_name     = adaptor_instance.get_name ()
            adaptor_names.append (adaptor_name)

        return adaptor_names



    #-----------------------------------------------------------------
    # 
    def get_adaptor (self, api_instance, ctype, schema, ttype, requested_name, *args, **kwargs) :
        '''
        Look for a suitable cpi class for bind, and instantiate it.
        
        If 'requested_name' is given, only matching adaptors are considered, and
        the resulting adaptor classes are not initialized.  This code path is
        used to re-bind to existing adaptors.
        '''
        schema = schema.lower ()

        #self._logger.debug(": '%s - %s - %s' "  %  (ctype, schema, requested_name))

        if not ctype in self._cpis :
            raise saga.exceptions.NotImplemented ("No adaptor class found for '%s' and URL scheme %s://" % (ctype, schema))

        if not schema in self._cpis[ctype] :
            raise saga.exceptions.NotImplemented ("No adaptor class found for '%s' and URL scheme %s://" %  (ctype, schema))


        # cycle through all applicable adaptors, and try to instantiate the ones
        # with matching name.  
        # If that works, and ttype signals a sync object construction, call the 
        # init_instance(), which effectively performs the semantics of the API
        # level object constructor.  For asynchronous object instantiation (via
        # create factory methods), the init_instance_async will be called from
        # API level -- but at that point will not be able to abort the adaptor
        # binding if the constructor semantics signals a problem (i.e. cannot
        # handle URL after all).
        msg = ""
        for info in self._cpis[ctype][schema] :

            cpi_class        = info['cpi_class']
            adaptor_instance = info['adaptor_instance']
            adaptor_name     = adaptor_instance.get_name ()

            try :
                # instantiate cpi
                cpi_instance = cpi_class (api_instance, adaptor_instance)
                cpi_name     = cpi_instance.get_cpi_name ()

                if requested_name != None :
                    if requested_name == adaptor_name :
                        return cpi_instance

                    # ignore this adaptor
                    self._logger.debug ("get_adaptor %s.%s -- ignore %s != %s" \
                                          %  (adaptor_name, cpi_name, requested_name, adaptor_name))
                    continue


                if ttype == None :
                    # run the sync constructor for sync construction, and return
                    # the adaptor_instance to bind to the API instance.
                    cpi_instance.init_instance  (*args, **kwargs)

                    self._logger.debug("BOUND get_adaptor %s.%s -- success"
                            %  (adaptor_name, cpi_name))
                    return cpi_instance

                else :
                    # the async constructor will return a task, which we pass
                    # back to the caller (instead of the adaptor instance). That 
                    # task is responsible for binding the adaptor to the later 
                    # returned API instance.
                    self._logger.debug("get_adaptor %s.%s -- async task creation"  %  (adaptor_name, cpi_name))

                    task = cpi_instance.init_instance_async (ttype, *args, **kwargs)
                    return task


            except Exception as e :
                # adaptor class initialization failed - try next one
                m    = "%s.%s: %s"  %  (adaptor_name, cpi_class, str(e))
                msg += "\n  %s" % m
                self._logger.info("get_adaptor %s", m)
                continue

        self._logger.error ("No suitable adaptor found for '%s' and URL scheme '%s'" %  (ctype, schema))
        raise saga.exceptions.NotImplemented ("No suitable adaptor found: %s" %  msg)


    #-----------------------------------------------------------------
    # 
    def loaded_cpis (self):
        return self._cpis


    #-----------------------------------------------------------------
    # 
    def _dump (self) :
        import pprint
        pprint.pprint (self._cpis)

