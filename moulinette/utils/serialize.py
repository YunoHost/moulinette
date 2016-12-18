import logging
from json.encoder import JSONEncoder

logger = logging.getLogger('moulinette.utils.serialize')


# JSON utilities -------------------------------------------------------

class JSONExtendedEncoder(JSONEncoder):
    """Extended JSON encoder

    Extend default JSON encoder to recognize more types and classes. It
    will never raise if the object can't be encoded and return its repr
    instead.
    The following objects and types are supported:
        - set: converted into list

    """

    def default(self, o):
        """Return a serializable object"""
        # Convert compatible containers into list
        if isinstance(o, set) or (
                hasattr(o, '__iter__') and hasattr(o, 'next')):
            return list(o)

        # Return the repr for object that json can't encode
        logger.warning('cannot properly encode in JSON the object %s, '
                       'returned repr is: %r', type(o), o)
        return repr(o)
