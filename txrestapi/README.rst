============
Introduction
============

``txrestapi`` makes it easier to create Twisted REST API services. Normally, one
would create ``Resource`` subclasses defining each segment of a path; this is
cubersome to implement and results in output that isn't very readable.
``txrestapi`` provides an ``APIResource`` class allowing complex mapping of path to
callback (a la Django) with a readable decorator.

===============================
Basic URL callback registration
===============================

First, let's create a bare API service::

    >>> from txrestapi.resource import APIResource
    >>> api = APIResource()

and a web server to serve it::

    >>> from twisted.web.server import Site
    >>> from twisted.internet import reactor
    >>> site = Site(api, timeout=None)

and a function to make it easy for us to make requests (only for doctest
purposes; normally you would of course use ``reactor.listenTCP(8080, site)``)::

    >>> from twisted.web.server import Request
    >>> class FakeChannel(object):
    ...     transport = None
    >>> def makeRequest(method, path):
    ...     req = Request(FakeChannel(), None)
    ...     req.prepath = req.postpath = None
    ...     req.method = method; req.path = path
    ...     resource = site.getChildWithDefault(path, req)
    ...     return resource.render(req)

We can now register callbacks for paths we care about. We can provide different
callbacks for different methods; they must accept ``request`` as the first
argument::

    >>> def get_callback(request): return 'GET callback'
    >>> api.register('GET', '^/path/to/method', get_callback)
    >>> def post_callback(request): return 'POST callback'
    >>> api.register('POST', '^/path/to/method', post_callback)

Then, when we make a call, the request is routed to the proper callback::

    >>> print makeRequest('GET', '/path/to/method')
    GET callback
    >>> print makeRequest('POST', '/path/to/method')
    POST callback

We can register multiple callbacks for different requests; the first one that
matches wins::

    >>> def default_callback(request):
    ...     return 'Default callback'
    >>> api.register('GET', '^/.*$', default_callback) # Matches everything
    >>> print makeRequest('GET', '/path/to/method')
    GET callback
    >>> print makeRequest('GET', '/path/to/different/method')
    Default callback

Our default callback, however, will only match GET requests. For a true default
callback, we can either register callbacks for each method individually, or we
can use ALL::

    >>> api.register('ALL', '^/.*$', default_callback)
    >>> print makeRequest('PUT', '/path/to/method')
    Default callback
    >>> print makeRequest('DELETE', '/path/to/method')
    Default callback
    >>> print makeRequest('GET', '/path/to/method')
    GET callback

Let's unregister all references to the default callback so it doesn't interfere
with later tests (default callbacks should, of course, always be registered
last, so they don't get called before other callbacks)::

    >>> api.unregister(callback=default_callback)

=============
URL Arguments
=============

Since callbacks accept ``request``, they have access to POST data or query
arguments, but we can also pull arguments out of the URL by using named groups
in the regular expression (similar to Django). These will be passed into the
callback as keyword arguments::

    >>> def get_info(request, id):
    ...     return 'Information for id %s' % id
    >>> api.register('GET', '/(?P<id>[^/]+)/info$', get_info)
    >>> print makeRequest('GET', '/someid/info')
    Information for id someid

Bear in mind all arguments will come in as strings, so code should be
accordingly defensive.

================
Decorator syntax
================

Registration via the ``register()`` method is somewhat awkward, so decorators
are provided making it much more straightforward. ::

    >>> from txrestapi.methods import GET, POST, PUT, ALL
    >>> class MyResource(APIResource):
    ...
    ...     @GET('^/(?P<id>[^/]+)/info')
    ...     def get_info(self, request, id):
    ...         return 'Info for id %s' % id
    ...
    ...     @PUT('^/(?P<id>[^/]+)/update')
    ...     @POST('^/(?P<id>[^/]+)/update')
    ...     def set_info(self, request, id):
    ...         return "Setting info for id %s" % id
    ...
    ...     @ALL('^/')
    ...     def default_view(self, request):
    ...         return "I match any URL"

Again, registrations occur top to bottom, so methods should be written from
most specific to least. Also notice that one can use the decorator syntax as
one would expect to register a method as the target for two URLs ::

    >>> site = Site(MyResource(), timeout=None)
    >>> print makeRequest('GET', '/anid/info')
    Info for id anid
    >>> print makeRequest('PUT', '/anid/update')
    Setting info for id anid
    >>> print makeRequest('POST', '/anid/update')
    Setting info for id anid
    >>> print makeRequest('DELETE', '/anid/delete')
    I match any URL

======================
Callback return values
======================

You can return Resource objects from a callback if you wish, allowing you to
have APIs that send you to other kinds of resources, or even other APIs.
Normally, however, you'll most likely want to return strings, which will be
wrapped in a Resource object for convenience.
