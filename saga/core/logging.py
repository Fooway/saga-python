# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

__author__    = "Ole Christian Weidner"
__copyright__ = "Copyright 2012, The SAGA Project"
__license__   = "MIT"

''' Provides API handles for SAGA's logging system.
'''

from saga.utils.singleton import Singleton

class Config(object): # This should inherit from some sort of a Config base class
    __metaclass__ = Singleton

    def __init__(self):
        pass

def getConfig():
    ''' Returns a handle to logging system's configuration.
    '''
    return Config() 

