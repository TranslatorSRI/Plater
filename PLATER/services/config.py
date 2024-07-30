###############
#  Configuration loader
#  Borrowed from : https://github.com/NCATS-Gamma/robokop-interfaces/blob/master/greent/config.py
#
##################
import os
import yaml
import traceback
import re
from PLATER.services.util.logutil import LoggingUtil


class Config(dict):

    @staticmethod
    def get_resource_path(resource_name):
        """ Given a string resolve it to a module relative file path unless it is already an absolute path. """
        resource_path = resource_name
        if not resource_path.startswith(os.sep):
            resource_path = os.path.join(os.path.dirname(__file__), resource_path)
        return resource_path

    def __init__(self, config, prefix=''):
        '''
        if not config.startswith (os.sep):
            config = os.path.join (os.path.dirname (__file__), config)
        '''
        if isinstance(config, str):
            config_path = Config.get_resource_path(config)
            with open(config_path, 'r') as f:
                self.conf = yaml.safe_load (f)
        elif isinstance(config, dict):
            self.conf = config
        else:
            raise ValueError
        self.prefix = prefix

    def get_service(self, service):
        result = {}
        try:
            result = self['translator']['services'][service]
        except:
            traceback.print_exc()
        return result

    def __setitem__(self, key, val):
        raise TypeError("Setting configuration is not allowed.")

    def __str__(self):
        return "Config with keys: "+', '.join(list(self.conf.keys()))

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __getitem__(self, key):
        """
        Use this accessor instead of getting conf directly in order to permit overloading with environment variables.
        Imagine you have a config file of the form

          person:
            address:
              street: Main

        This will be overridden by an environment variable by the name of PERSON_ADDRESS_STREET,
        e.g. export PERSON_ADDRESS_STREET=Gregson
        """
        key_var = re.sub("[\\W]", '', key)

        name = self.prefix+'_'+key_var if self.prefix else key_var
        try:
            env_name = name.upper()
            return os.environ[env_name]
        except KeyError:
            value = self.conf[key]
            if isinstance(value, dict):
                return Config(value, prefix=name)
            else:
                return value

def get_positive_int_from_config(config_var_name: str, default=None):
    config_var = config.get(config_var_name, None)
    if config_var is not None and config_var != "":
        try:
            config_int = int(config_var)
            if config_int >= 0:
                return config_int
            else:
                logger.warning(f'Negative value provided for {config_var_name}: {config_var}, using default {default}')
        except ValueError:
            logger.warning(f'Invalid value provided for {config_var_name}: {config_var}, using default {default}')
    return default

config = Config('plater.conf')
logger = LoggingUtil.init_logging(
    __name__,
    config.get('logging_level'),
    config.get('logging_format'),
)