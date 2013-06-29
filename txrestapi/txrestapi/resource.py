import re
from itertools import ifilter
from functools import wraps
from twisted.web.resource import Resource, NoResource

class _FakeResource(Resource):
    _result = ''
    isLeaf = True
    def __init__(self, result):
        Resource.__init__(self)
        self._result = result
    def render(self, request):
        return self._result


def maybeResource(f):
    @wraps(f)
    def inner(*args, **kwargs):
        result = f(*args, **kwargs)
        if not isinstance(result, Resource):
            result = _FakeResource(result)
        return result
    return inner


class APIResource(Resource):

    _registry = None

    def __init__(self, *args, **kwargs):
        Resource.__init__(self, *args, **kwargs)
        self._registry = []

    def _get_callback(self, request):
        filterf = lambda t:t[0] in (request.method, 'ALL')
        path_to_check = getattr(request, '_remaining_path', request.path)
        for m, r, cb in ifilter(filterf, self._registry):
            result = r.search(path_to_check)
            if result:
                request._remaining_path = path_to_check[result.span()[1]:]
                return cb, result.groupdict()
        return None, None

    def register(self, method, regex, callback):
        self._registry.append((method, re.compile(regex), callback))

    def unregister(self, method=None, regex=None, callback=None):
        if regex is not None: regex = re.compile(regex)
        for m, r, cb in self._registry[:]:
            if not method or (method and m==method):
                if not regex or (regex and r==regex):
                    if not callback or (callback and cb==callback):
                        self._registry.remove((m, r, cb))

    def getChild(self, name, request):
        r = self.children.get(name, None)
        if r is None:
            # Go into the thing
            callback, args = self._get_callback(request)
            if callback is None:
                return NoResource()
            else:
                return maybeResource(callback)(request, **args)
        else:
            return r
