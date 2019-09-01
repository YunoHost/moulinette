from moulinette.utils.text import search, searchf, prependlines, random_ascii


def test_search():
    assert search('a', 'a a a') == ['a', 'a', 'a']
    assert search('a', 'a a a', count=2) == ['a', 'a']
    assert not search('a', 'c c d')


def test_searchf(test_file):
    assert searchf('bar', str(test_file)) == ['bar']
    assert not searchf('baz', str(test_file))


def test_prependlines():
    assert prependlines('abc\nedf\nghi', 'XXX') == 'XXXabc\nXXXedf\nXXXghi'
    assert prependlines('', 'XXX') == 'XXX'


def test_random_ascii():
    assert isinstance(random_ascii(length=2), unicode)
