import logging
from json.encoder import JSONEncoder
import datetime

logger = logging.getLogger("moulinette.core")


# JSON utilities -------------------------------------------------------


class JSONExtendedEncoder(JSONEncoder):

    """Extended JSON encoder

    Extend default JSON encoder to recognize more types and classes. It will
    never raise an exception if the object can't be encoded and return its repr
    instead.

    The following objects and types are supported:
        - set: converted into list

    """

    def default(self, o):

        import pytz  # Lazy loading, this takes like 3+ sec on a RPi2 ?!

        """Return a serializable object"""
        # Convert compatible containers into list
        if isinstance(o, set) or (hasattr(o, "__iter__") and hasattr(o, "next")):
            return list(o)

        # Display the date in its iso format ISO-8601 Internet Profile (RFC 3339)
        if isinstance(o, datetime.date):
            if o.tzinfo is None:
                o = o.replace(tzinfo=pytz.utc)
            return o.isoformat()

        # Return the repr for object that json can't encode
        logger.warning(
            "cannot properly encode in JSON the object %s, " "returned repr is: %r",
            type(o),
            o,
        )
        return repr(o)
