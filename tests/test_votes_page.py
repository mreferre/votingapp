import base64
import os
import sys

import boto3
import pytest
from moto import mock_dynamodb

os.environ.setdefault("DDB_AWS_REGION", "us-east-1")
os.environ.setdefault("DDB_TABLE_NAME", "votingapp-restaurants")
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SLUGS = ["outback", "bucadibeppo", "ihop", "chipotle"]
NAMES = ["Outback", "Buca di Beppo", "IHOP", "Chipotle"]
PASSWORD = "s3cret-pw"


def basic(password, user="anyone"):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VOTES_PASSWORD", PASSWORD)
    with mock_dynamodb():
        table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="votingapp-restaurants",
            KeySchema=[{"AttributeName": "name", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "name", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        for i, slug in enumerate(SLUGS):
            table.put_item(Item={"name": slug, "restaurantcount": 10 * (i + 1)})
        import app as votingapp

        yield votingapp.app.test_client()


# --- authentication -------------------------------------------------------

PROTECTED = [("get", "/votes"), ("get", "/votes/data"), ("post", "/votes/vote/ihop")]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_no_credentials_is_401_with_challenge(client, method, path):
    r = getattr(client, method)(path, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"].startswith("Basic")
    assert b"Outback" not in r.data and b"outback" not in r.data


@pytest.mark.parametrize("method,path", PROTECTED)
def test_wrong_password_is_401(client, method, path):
    headers = {**basic("wrong"), "X-Requested-With": "fetch"}
    assert getattr(client, method)(path, headers=headers).status_code == 401


def test_wrong_password_does_not_change_votes(client):
    client.post("/votes/vote/ihop", headers={**basic("wrong"), "X-Requested-With": "fetch"})
    assert client.get("/votes/data", headers=basic(PASSWORD)).get_json()["ihop"] == 30


def test_right_password_is_200(client):
    assert client.get("/votes", headers=basic(PASSWORD)).status_code == 200


@pytest.mark.parametrize("password", [None, ""])
def test_unset_or_empty_password_denies_everyone(client, monkeypatch, password):
    if password is None:
        monkeypatch.delenv("VOTES_PASSWORD")
    else:
        monkeypatch.setenv("VOTES_PASSWORD", password)
    for creds in ({}, basic(""), basic("anything"), basic(PASSWORD)):
        assert client.get("/votes", headers=creds).status_code == 401
        assert client.get("/votes/data", headers=creds).status_code == 401


def test_responses_are_not_cacheable(client):
    assert client.get("/votes", headers=basic(PASSWORD)).headers["Cache-Control"] == "no-store"


# --- page content ---------------------------------------------------------


def test_page_lists_all_four_restaurants_with_counts(client):
    html = client.get("/votes", headers=basic(PASSWORD)).get_data(as_text=True)
    for name in NAMES:
        assert name in html
    for slug in SLUGS:
        assert f'data-slug="{slug}"' in html
    for count in ("10", "20", "30", "40"):
        assert f'data-votes="{count}"' in html
    assert 'aria-live="polite"' in html


def test_data_endpoint_returns_counts(client):
    r = client.get("/votes/data", headers=basic(PASSWORD))
    assert r.get_json() == {"outback": 10, "bucadibeppo": 20, "ihop": 30, "chipotle": 40}


# --- voting ---------------------------------------------------------------


def test_vote_increments_count(client):
    headers = {**basic(PASSWORD), "X-Requested-With": "fetch"}
    r = client.post("/votes/vote/chipotle", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"slug": "chipotle", "votes": 41}
    assert client.get("/votes/data", headers=basic(PASSWORD)).get_json()["chipotle"] == 41
    # the existing API sees the same number
    assert client.get("/api/chipotle").data == b"42"


def test_vote_requires_csrf_header_and_known_restaurant(client):
    assert client.post("/votes/vote/ihop", headers=basic(PASSWORD)).status_code == 400
    headers = {**basic(PASSWORD), "X-Requested-With": "fetch"}
    assert client.post("/votes/vote/pizza", headers=headers).status_code == 404
    assert client.get("/votes/vote/ihop", headers=headers).status_code == 405


# --- existing routes unchanged -------------------------------------------


def test_existing_routes_still_public_and_same_format(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/outback").data == b"11"
    assert client.get("/api/getvotes").get_data(as_text=True) == (
        '[{"name": "outback", "value": 11},{"name": "bucadibeppo", "value": 20},'
        '{"name": "ihop", "value": 30}, {"name": "chipotle", "value": 40}]'
    )
