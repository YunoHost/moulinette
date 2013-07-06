from twisted.web.server import Site
from .resource import APIResource


class RESTfulService(Site):
    def __init__(self, port=8080):
        self.root = APIResource()
