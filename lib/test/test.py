
def test_non_auth():
    print('non-auth')

def test_auth(auth):
    print('[default] / all / auth: %r' % auth)

def test_auth_cli():
    print('[default] / cli')

def test_anonymous():
    print('[ldap-anonymous] / all')
