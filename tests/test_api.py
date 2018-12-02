# -*- coding: utf-8 -*-

from webtest import TestApp as WebTestApp
from bottle import Bottle
from moulinette.interfaces.api import filter_csrf


URLENCODED = 'application/x-www-form-urlencoded'
FORMDATA = 'multipart/form-data'
TEXT = 'text/plain'

TYPES = [URLENCODED, FORMDATA, TEXT]
SAFE_METHODS = ["HEAD", "GET", "PUT", "DELETE"]


app = Bottle(autojson=True)
app.install(filter_csrf)


@app.get('/')
def get_hello():
    return "Hello World!\n"


@app.post('/')
def post_hello():
    return "OK\n"


@app.put('/')
def put_hello():
    return "OK\n"


@app.delete('/')
def delete_hello():
    return "OK\n"


webtest = WebTestApp(app)


def test_get():
    r = webtest.get("/")
    assert r.status_code == 200


def test_csrf_post():
    r = webtest.post("/", "test", expect_errors=True)
    assert r.status_code == 403


def test_post_json():
    r = webtest.post("/", "test",
                     headers=[("Content-Type", "application/json")])
    assert r.status_code == 200


def test_csrf_post_text():
    r = webtest.post("/", "test",
                     headers=[("Content-Type", "text/plain")],
                     expect_errors=True)
    assert r.status_code == 403


def test_csrf_post_urlencoded():
    r = webtest.post("/", "test",
                     headers=[("Content-Type",
                               "application/x-www-form-urlencoded")],
                     expect_errors=True)
    assert r.status_code == 403


def test_csrf_post_form():
    r = webtest.post("/", "test",
                     headers=[("Content-Type", "multipart/form-data")],
                     expect_errors=True)
    assert r.status_code == 403


def test_ok_post_text():
    r = webtest.post("/", "test",
                     headers=[("Content-Type", "text/plain"),
                              ("X-Requested-With", "XMLHttpRequest")])
    assert r.status_code == 200


def test_ok_post_urlencoded():
    r = webtest.post("/", "test",
                     headers=[("Content-Type",
                               "application/x-www-form-urlencoded"),
                              ("X-Requested-With", "XMLHttpRequest")])
    assert r.status_code == 200


def test_ok_post_form():
    r = webtest.post("/", "test",
                     headers=[("Content-Type", "multipart/form-data"),
                              ("X-Requested-With", "XMLHttpRequest")])
    assert r.status_code == 200
