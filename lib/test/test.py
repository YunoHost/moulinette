
def test_non_auth():
    return {'action': 'non-auth'}

def test_auth(auth):
    return {'action': 'auth',
            'authenticator': 'default', 'authenticate': 'all'}

def test_auth_profile(auth):
    return {'action': 'auth-profile',
            'authenticator': 'test-profile', 'authenticate': 'all'}

def test_auth_cli():
    return {'action': 'auth-cli',
            'authenticator': 'default', 'authenticate': ['cli']}

def test_anonymous():
    return {'action': 'anonymous',
            'authenticator': 'ldap-anonymous', 'authenticate': 'all'}

def test_root():
    return {'action': 'root-auth',
            'authenticator': 'as-root', 'authenticate': 'all'}
