import txrestapi
__package__="txrestapi"
import re
import os.path
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.resource import Resource, NoResource
from twisted.web.server import Request, Site
from twisted.web.client import getPage
from twisted.trial import unittest
from .resource import APIResource
from .methods import GET, PUT

class FakeChannel(object):
    transport = None

def getRequest(method, url):
    req = Request(FakeChannel(), None)
    req.method = method
    req.path = url
    return req

class APIResourceTest(unittest.TestCase):

    def test_returns_normal_resources(self):
        r = APIResource()
        a = Resource()
        r.putChild('a', a)
        req = Request(FakeChannel(), None)
        a_ = r.getChild('a', req)
        self.assertEqual(a, a_)

    def test_registry(self):
        compiled = re.compile('regex')
        r = APIResource()
        r.register('GET', 'regex', None)
        self.assertEqual([x[0] for x in r._registry], ['GET'])
        self.assertEqual(r._registry[0], ('GET', compiled, None))

    def test_method_matching(self):
        r = APIResource()
        r.register('GET', 'regex', 1)
        r.register('PUT', 'regex', 2)
        r.register('GET', 'another', 3)

        req = getRequest('GET', 'regex')
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 1)

        req = getRequest('PUT', 'regex')
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 2)

        req = getRequest('GET', 'another')
        result = r._get_callback(req)
        self.assert_(result)
        self.assertEqual(result[0], 3)

        req = getRequest('PUT', 'another')
        result = r._get_callback(req)
        self.assertEqual(result, (None, None))

    def test_callback(self):
        marker = object()
        def cb(request):
            return marker
        r = APIResource()
        r.register('GET', 'regex', cb)
        req = getRequest('GET', 'regex')
        result = r.getChild('regex', req)
        self.assertEqual(result.render(req), marker)

    def test_longerpath(self):
        marker = object()
        r = APIResource()
        def cb(request):
            return marker
        r.register('GET', '/regex/a/b/c', cb)
        req = getRequest('GET', '/regex/a/b/c')
        result = r.getChild('regex', req)
        self.assertEqual(result.render(req), marker)

    def test_args(self):
        r = APIResource()
        def cb(request, **kwargs):
            return kwargs
        r.register('GET', '/(?P<a>[^/]*)/a/(?P<b>[^/]*)/c', cb)
        req = getRequest('GET', '/regex/a/b/c')
        result = r.getChild('regex', req)
        self.assertEqual(sorted(result.render(req).keys()), ['a', 'b'])

    def test_order(self):
        r = APIResource()
        def cb1(request, **kwargs):
            kwargs.update({'cb1':True})
            return kwargs
        def cb(request, **kwargs):
            return kwargs
        # Register two regexes that will match
        r.register('GET', '/(?P<a>[^/]*)/a/(?P<b>[^/]*)/c', cb1)
        r.register('GET', '/(?P<a>[^/]*)/a/(?P<b>[^/]*)', cb)
        req = getRequest('GET', '/regex/a/b/c')
        result = r.getChild('regex', req)
        # Make sure the first one got it
        self.assert_('cb1' in result.render(req))

    def test_no_resource(self):
        r = APIResource()
        r.register('GET', '^/(?P<a>[^/]*)/a/(?P<b>[^/]*)$', None)
        req = getRequest('GET', '/definitely/not/a/match')
        result = r.getChild('regex', req)
        self.assert_(isinstance(result, NoResource))

    def test_all(self):
        r = APIResource()
        def get_cb(r): return 'GET'
        def put_cb(r): return 'PUT'
        def all_cb(r): return 'ALL'
        r.register('GET', '^path', get_cb)
        r.register('ALL', '^path', all_cb)
        r.register('PUT', '^path', put_cb)
        # Test that the ALL registration picks it up before the PUT one
        for method in ('GET', 'PUT', 'ALL'):
            req = getRequest(method, 'path')
            result = r.getChild('path', req)
            self.assertEqual(result.render(req), 'ALL' if method=='PUT' else method)


class TestResource(Resource):
    isLeaf = True
    def render(self, request):
        return 'aresource'


class TestAPI(APIResource):

    @GET('^/(?P<a>test[^/]*)/?')
    def _on_test_get(self, request, a):
        return 'GET %s' % a

    @PUT('^/(?P<a>test[^/]*)/?')
    def _on_test_put(self, request, a):
        return 'PUT %s' % a

    @GET('^/gettest')
    def _on_gettest(self, request):
        return TestResource()


class DecoratorsTest(unittest.TestCase):
    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        r = TestAPI()
        site = Site(r, timeout=None)
        self.port = self._listen(site)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getURL(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    @inlineCallbacks
    def test_get(self):
        url = self.getURL('test_thing/')
        result = yield getPage(url, method='GET')
        self.assertEqual(result, 'GET test_thing')

    @inlineCallbacks
    def test_put(self):
        url = self.getURL('test_thing/')
        result = yield getPage(url, method='PUT')
        self.assertEqual(result, 'PUT test_thing')

    @inlineCallbacks
    def test_resource_wrapper(self):
        url = self.getURL('gettest')
        result = yield getPage(url, method='GET')
        self.assertEqual(result, 'aresource')


def test_suite():
    import unittest as ut
    suite = unittest.TestSuite()
    suite.addTest(ut.makeSuite(DecoratorsTest))
    suite.addTest(ut.makeSuite(APIResourceTest))
    suite.addTest(unittest.doctest.DocFileSuite(os.path.join('..', 'README.rst')))
    return suite

