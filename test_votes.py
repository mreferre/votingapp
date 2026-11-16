import os
from unittest import mock

os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
os.environ['DDB_AWS_REGION'] = 'us-east-1'
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['VOTES_PASSWORD'] = 'pw'

import pytest
import app as appmod


@pytest.fixture
def db(monkeypatch):
    counts = {'outback': 1, 'bucadibeppo': 2, 'ihop': 3, 'chipotle': 4}
    monkeypatch.setattr(appmod, 'readvote', lambda k: str(counts[k]))
    monkeypatch.setattr(appmod, 'updatevote', lambda k, v: counts.__setitem__(k, v) or str(v))
    return counts


@pytest.fixture
def client(db):
    appmod.app.config['TESTING'] = True
    return appmod.app.test_client()


def token(client):
    client.get('/votes')
    with client.session_transaction() as s:
        return s['csrf']


def login(client, pw='pw'):
    return client.post('/votes/login', data={'password': pw, 'csrf_token': token(client)})


def test_unset_password_denies(client, monkeypatch):
    monkeypatch.delenv('VOTES_PASSWORD')
    assert client.get('/votes').status_code == 503
    assert client.post('/votes/vote/ihop').status_code == 401


def test_unset_secret_denies(client, monkeypatch):
    monkeypatch.setattr(appmod.app, 'secret_key', None)
    assert client.get('/votes').status_code == 503


def test_login_form_when_anonymous(client):
    r = client.get('/votes')
    assert r.status_code == 200 and b'type="password"' in r.data and b'Outback' not in r.data


def test_wrong_password(client):
    assert login(client, 'nope').status_code == 303
    assert b'Outback' not in client.get('/votes').data


def test_login_requires_csrf(client):
    assert client.post('/votes/login', data={'password': 'pw'}).status_code == 403


def test_page_lists_restaurants_after_login(client):
    login(client)
    r = client.get('/votes')
    for name in (b'Outback', b'Buca di Beppo', b'IHOP', b'Chipotle'):
        assert name in r.data
    assert b'aria-live="polite"' in r.data


def test_vote_requires_auth(client, db):
    assert client.post('/votes/vote/ihop').status_code == 401
    assert db['ihop'] == 3


def test_vote_requires_csrf(client, db):
    login(client)
    assert client.post('/votes/vote/ihop').status_code == 403
    assert client.post('/votes/vote/ihop', headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert db['ihop'] == 3


def test_vote_fetch(client, db):
    login(client)
    r = client.post('/votes/vote/ihop', headers={'X-CSRF-Token': token(client), 'X-Requested-With': 'fetch'})
    assert r.get_json() == {'name': 'ihop', 'votes': 4} and db['ihop'] == 4


def test_vote_form_fallback_redirects(client, db):
    login(client)
    r = client.post('/votes/vote/chipotle', data={'csrf_token': token(client)})
    assert r.status_code == 302 and db['chipotle'] == 5


def test_unknown_restaurant(client):
    login(client)
    assert client.post('/votes/vote/nope', headers={'X-CSRF-Token': token(client)}).status_code == 404


def test_existing_api_still_works(client, db):
    assert client.get('/api/ihop').data == b'4'
    assert client.get('/').status_code == 200
