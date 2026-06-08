"""Tests for the votes-web-page feature (feature: votes-web-page).

These tests exercise the additive /votes password-protected UI in app.py.
DynamoDB is always mocked (app.readvote / app.updatevote are patched) so the
suite never touches real AWS. Property-based tests use Hypothesis with a
minimum of 100 iterations each.

Run with:  pytest -q test_votes.py
"""

import os

# Provide a region and dummy credentials BEFORE importing app, because app.py
# constructs a boto3 DynamoDB resource at import time. These are never used to
# make real calls because readvote/updatevote are mocked in every test.
os.environ.setdefault("DDB_AWS_REGION", "us-west-2")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
# Default configured password for the majority of tests; individual tests that
# need a different value (unset/empty) override and restore it locally.
os.environ["VOTES_PASSWORD"] = "secret-pw"

import contextlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from unittest import mock  # noqa: E402

import flask  # noqa: E402
import pytest  # noqa: E402
from hypothesis import given, settings, HealthCheck, example  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

import app as appmod  # noqa: E402

ALL = appmod.RESTAURANTS
# Substrings that would indicate internal configuration leakage in an error body.
LEAK_TOKENS = [
    "votingapp-restaurants",
    "us-west-2",
    "dynamodb",
    "boto",
    "traceback",
    "region",
    "table",
]

PBT = settings(max_examples=100, deadline=None,
               suppress_health_check=[HealthCheck.function_scoped_fixture])

# Password text excluding NUL (cannot live in env vars) and surrogates (cannot
# be UTF-8 encoded). Real passwords never contain these.
PW_ALPHABET = st.characters(min_codepoint=1, blacklist_categories=("Cs",))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

@contextlib.contextmanager
def store_patch(counts, fail_read=False, fail_write=False):
    """Patch app.readvote / app.updatevote to operate on an in-memory dict.

    Failure messages deliberately embed config-like tokens so tests can prove
    those tokens never leak into HTTP error bodies.
    """
    store = dict(counts)

    def fake_readvote(restaurant):
        if fail_read:
            raise RuntimeError(
                "ddb read failed for table votingapp-restaurants in region us-west-2"
            )
        return str(store[restaurant])

    def fake_updatevote(restaurant, votes):
        if fail_write:
            raise RuntimeError(
                "ddb write failed for table votingapp-restaurants in region us-west-2"
            )
        store[restaurant] = votes
        return str(votes)

    with mock.patch.object(appmod, "readvote", fake_readvote), \
            mock.patch.object(appmod, "updatevote", fake_updatevote):
        yield store


@contextlib.contextmanager
def password_env(value):
    """Temporarily set (or unset, when value is None) VOTES_PASSWORD."""
    old = os.environ.get("VOTES_PASSWORD")
    if value is None:
        os.environ.pop("VOTES_PASSWORD", None)
    else:
        os.environ["VOTES_PASSWORD"] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("VOTES_PASSWORD", None)
        else:
            os.environ["VOTES_PASSWORD"] = old


def authed_client():
    client = appmod.app.test_client()
    with client.session_transaction() as sess:
        sess["votes_authed"] = True
    return client


def anon_client():
    return appmod.app.test_client()


def full_counts(values):
    """Map the four restaurants to the given 4-tuple/list of counts."""
    return {name: values[i] for i, name in enumerate(ALL)}


def assert_no_leak(body_text):
    lowered = body_text.lower()
    for token in LEAK_TOKENS:
        assert token not in lowered, "error body leaked config token: %r" % token


# --------------------------------------------------------------------------- #
# Property-based tests (one per design correctness property)
# --------------------------------------------------------------------------- #

# Feature: votes-web-page, Property 1: Authenticated grid renders the complete,
# correct restaurant set (exactly four rows, one per restaurant, each label
# co-located with its count cell, four vote controls each with an accessible
# label naming its restaurant).
# Validates: Requirements 1.3, 3.1, 3.2, 3.3, 4.1, 5.5
@PBT
@given(counts=st.lists(st.integers(min_value=0, max_value=10_000_000),
                       min_size=4, max_size=4))
def test_property1_authenticated_grid_renders_complete_set(counts):
    mapping = full_counts(counts)
    with store_patch(mapping):
        client = authed_client()
        page = client.get("/votes")
        assert page.status_code == 200
        html = page.get_data(as_text=True)

        for name in ALL:
            # Each restaurant row appears exactly once.
            assert html.count('data-restaurant="%s"' % name) == 1
            # Label co-located with a count cell keyed to the same restaurant.
            assert ('data-count-for="%s"' % name) in html
            # Exactly one vote control per restaurant with an accessible label.
            assert html.count('data-vote-for="%s"' % name) == 1
            assert ('aria-label="Vote for %s"' % name) in html

        # Exactly four vote controls / rows total.
        assert html.count('class="vote-button"') == 4
        assert html.count("data-restaurant=") == 4

        # The displayed count source (/votes/data) equals each stored count.
        data = client.get("/votes/data")
        assert data.status_code == 200
        rows = json.loads(data.get_data(as_text=True))
        returned = {r["name"]: r["value"] for r in rows}
        for name in ALL:
            assert returned[name] == mapping[name]


# Feature: votes-web-page, Property 2: Unauthenticated page exposes no counts or
# controls (only the password entry form).
# Validates: Requirements 2.1
@PBT
@given(session_value=st.one_of(st.none(), st.booleans(), st.text(max_size=20),
                               st.integers()),
       counts=st.lists(st.integers(min_value=0, max_value=1000),
                       min_size=4, max_size=4))
def test_property2_unauthenticated_exposes_nothing(session_value, counts):
    mapping = full_counts(counts)
    with store_patch(mapping):
        client = anon_client()
        # Any non-True session marker must NOT grant access.
        if session_value is not True:
            with client.session_transaction() as sess:
                if session_value is not None:
                    sess["votes_authed"] = session_value
            page = client.get("/votes")
            assert page.status_code == 200
            html = page.get_data(as_text=True)
            assert "vote-button" not in html
            assert "data-vote-for" not in html
            assert "aria-label=\"Vote for" not in html
            # No numeric vote count rendered anywhere.
            assert not re.search(r"data-count-for", html)
            for value in mapping.values():
                # The form must not echo any specific count value as a token.
                assert (">%d<" % value) not in html


# Feature: votes-web-page, Property 3: Correct password grants a session.
# Validates: Requirements 2.2
@PBT
@given(password=st.text(alphabet=PW_ALPHABET, min_size=1, max_size=256)
       .filter(lambda s: s.strip() != ""))
def test_property3_correct_password_grants_session(password):
    with password_env(password):
        assert appmod.verify_password(password) is True
        client = anon_client()
        resp = client.post("/votes/login", data={"password": password})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/votes")
        with client.session_transaction() as sess:
            assert sess.get("votes_authed") is True


# Feature: votes-web-page, Property 4: Any non-matching, empty, or
# whitespace-only password (including >256 chars) is denied with no session.
# Validates: Requirements 2.3, 2.7
@PBT
@given(configured=st.text(alphabet=PW_ALPHABET, min_size=1, max_size=128)
       .filter(lambda s: s.strip() != ""),
       submitted=st.text(alphabet=PW_ALPHABET, max_size=300))
@example(configured="correct", submitted="")
@example(configured="correct", submitted="     ")
@example(configured="correct", submitted="x" * 257)
def test_property4_wrong_password_denied(configured, submitted):
    # Only meaningful when the submission differs from the configured value.
    if submitted == configured:
        return
    with password_env(configured):
        assert appmod.verify_password(submitted) is False
        client = anon_client()
        resp = client.post("/votes/login", data={"password": submitted})
        assert resp.status_code == 401
        with client.session_transaction() as sess:
            assert sess.get("votes_authed") is None


# Feature: votes-web-page, Property 5: Fail closed when password is unset or
# empty (deny with 401, never mutate a count) for any session state.
# Validates: Requirements 2.6
@PBT
@given(session_value=st.one_of(st.none(), st.booleans(), st.text(max_size=20),
                               st.integers(), st.lists(st.integers(), max_size=3)),
       pw=st.sampled_from([None, "", "   ", "\t\n"]))
def test_property5_fail_closed(session_value, pw):
    mapping = full_counts([1, 2, 3, 4])
    with password_env(pw), store_patch(mapping) as store:
        # is_authenticated() is False regardless of session state.
        with appmod.app.test_request_context("/votes"):
            if session_value is not None:
                flask.session["votes_authed"] = session_value
            assert appmod.is_authenticated() is False

        client = anon_client()
        with client.session_transaction() as sess:
            if session_value is not None:
                sess["votes_authed"] = session_value

        assert client.get("/votes/data").status_code == 401
        vote = client.post("/votes/vote", json={"restaurant": "ihop"})
        assert vote.status_code == 401
        # No mutation occurred.
        assert store == mapping
        # /votes serves the login form (no grid/controls).
        page = client.get("/votes")
        assert "vote-button" not in page.get_data(as_text=True)


# Feature: votes-web-page, Property 6: Unauthenticated vote requests never
# mutate state (401, all counts unchanged).
# Validates: Requirements 2.4, 4.7
@PBT
@given(restaurant=st.one_of(st.sampled_from(ALL), st.text(max_size=20)),
       counts=st.lists(st.integers(min_value=0, max_value=1000),
                       min_size=4, max_size=4))
def test_property6_unauthenticated_no_mutation(restaurant, counts):
    mapping = full_counts(counts)
    with store_patch(mapping) as store:
        client = anon_client()  # no session
        resp = client.post("/votes/vote", json={"restaurant": restaurant})
        assert resp.status_code == 401
        assert store == mapping


# Feature: votes-web-page, Property 7: A successful vote increments the target
# by exactly one (stored n+1, status 200, returned value n+1).
# Validates: Requirements 4.2, 4.3, 3.4
@PBT
@given(restaurant=st.sampled_from(ALL),
       n=st.integers(min_value=0, max_value=10_000_000))
def test_property7_successful_increment(restaurant, n):
    mapping = full_counts([0, 0, 0, 0])
    mapping[restaurant] = n
    with store_patch(mapping) as store:
        client = authed_client()
        resp = client.post("/votes/vote", json={"restaurant": restaurant})
        assert resp.status_code == 200
        body = json.loads(resp.get_data(as_text=True))
        assert body["restaurant"] == restaurant
        assert body["value"] == n + 1
        assert store[restaurant] == n + 1


# Feature: votes-web-page, Property 8: Voting changes only the targeted
# restaurant; the other three are unchanged.
# Validates: Requirements 4.4
@PBT
@given(target=st.sampled_from(ALL),
       counts=st.lists(st.integers(min_value=0, max_value=1_000_000),
                       min_size=4, max_size=4))
def test_property8_only_target_changes(target, counts):
    mapping = full_counts(counts)
    before = dict(mapping)
    with store_patch(mapping) as store:
        client = authed_client()
        resp = client.post("/votes/vote", json={"restaurant": target})
        assert resp.status_code == 200
        for name in ALL:
            if name == target:
                assert store[name] == before[name] + 1
            else:
                assert store[name] == before[name]


# Feature: votes-web-page, Property 9: Invalid restaurant names are rejected
# with 400 and no mutation.
# Validates: Requirements 4.6
@PBT
@given(name=st.text(max_size=40).filter(lambda s: s not in ALL),
       counts=st.lists(st.integers(min_value=0, max_value=1000),
                       min_size=4, max_size=4))
def test_property9_invalid_name_rejected(name, counts):
    mapping = full_counts(counts)
    with store_patch(mapping) as store:
        client = authed_client()
        resp = client.post("/votes/vote", json={"restaurant": name})
        assert resp.status_code == 400
        assert store == mapping


# Feature: votes-web-page, Property 10: Write failures return 500 without
# mutation or config leakage.
# Validates: Requirements 4.5, 6.6
@PBT
@given(restaurant=st.sampled_from(ALL),
       counts=st.lists(st.integers(min_value=0, max_value=1_000_000),
                       min_size=4, max_size=4))
def test_property10_write_failure_500_no_leak(restaurant, counts):
    mapping = full_counts(counts)
    with store_patch(mapping, fail_write=True) as store:
        client = authed_client()
        resp = client.post("/votes/vote", json={"restaurant": restaurant})
        assert resp.status_code == 500
        # No mutation (write raised before storing).
        assert store == mapping
        assert_no_leak(resp.get_data(as_text=True))


# Feature: votes-web-page, Property 11: Read failures hide all counts behind an
# error message (no numbers, no config leakage).
# Validates: Requirements 3.5, 6.6
@PBT
@given(counts=st.lists(st.integers(min_value=0, max_value=1_000_000),
                       min_size=4, max_size=4))
def test_property11_read_failure_hides_counts(counts):
    mapping = full_counts(counts)
    with store_patch(mapping, fail_read=True):
        client = authed_client()
        resp = client.get("/votes/data")
        assert resp.status_code == 500
        body = resp.get_data(as_text=True)
        # No numeric count values present.
        for value in mapping.values():
            assert str(value) not in body or value == 0  # 0 may appear incidentally
        assert re.search(r"\d{2,}", body) is None  # no multi-digit count leaked
        assert_no_leak(body)


# --------------------------------------------------------------------------- #
# Example / unit tests
# --------------------------------------------------------------------------- #

def test_env_sourcing_of_password():
    # Set / unset / empty cases for get_configured_password (Req 2.5).
    with password_env("hunter2"):
        assert appmod.get_configured_password() == "hunter2"
        assert appmod.votes_password_is_configured() is True
    with password_env(None):
        assert appmod.get_configured_password() is None
        assert appmod.votes_password_is_configured() is False
    with password_env(""):
        assert appmod.get_configured_password() == ""
        assert appmod.votes_password_is_configured() is False


def test_login_correct_password_sets_session_and_redirects():
    with password_env("good-pass"):
        client = anon_client()
        resp = client.post("/votes/login", data={"password": "good-pass"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/votes")
        with client.session_transaction() as sess:
            assert sess.get("votes_authed") is True


@pytest.mark.parametrize("bad", ["wrong", "", "   ", "GOOD-PASS"])
def test_login_bad_password_denied_no_session(bad):
    with password_env("good-pass"):
        client = anon_client()
        resp = client.post("/votes/login", data={"password": bad})
        assert resp.status_code == 401
        html = resp.get_data(as_text=True)
        assert "vote-button" not in html  # still the login form
        with client.session_transaction() as sess:
            assert sess.get("votes_authed") is None


def test_logout_clears_session():
    client = authed_client()
    resp = client.get("/votes/logout")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("votes_authed") is None


def test_authenticated_votes_page_headers():
    # 200 + Content-Type: text/html (Req 1.1, 1.2).
    with store_patch(full_counts([0, 0, 0, 0])):
        client = authed_client()
        resp = client.get("/votes")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/html")


def test_votes_page_uses_semantic_markup():
    # Req 5.4: semantic elements present.
    with store_patch(full_counts([0, 0, 0, 0])):
        client = authed_client()
        html = client.get("/votes").get_data(as_text=True)
        for token in ["<table", "<thead", "<tbody", "<main", "<button",
                      'scope="col"', 'aria-label="Vote for']:
            assert token in html


def test_routing_exclusivity_non_votes_paths_do_not_serve_page():
    # Req 1.5: only /votes serves the page; '/' and /api/* must not.
    client = authed_client()
    home = client.get("/")
    assert "votes-grid" not in home.get_data(as_text=True)
    assert "vote-button" not in home.get_data(as_text=True)


def test_unset_password_serves_login_form_only():
    # Req 2.6 / 2.1: password unset -> login form, no grid even with a session.
    with password_env(None), store_patch(full_counts([5, 6, 7, 8])):
        client = anon_client()
        with client.session_transaction() as sess:
            sess["votes_authed"] = True
        html = client.get("/votes").get_data(as_text=True)
        assert "vote-button" not in html
        assert "Password" in html


# --------------------------------------------------------------------------- #
# Legacy-route regression tests (Requirement 1.4) - existing routes unchanged
# --------------------------------------------------------------------------- #

def test_legacy_home_route_unchanged():
    client = appmod.app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Welcome to the Voting App" in body
    for path in ["/api/outback", "/api/bucadibeppo", "/api/ihop",
                 "/api/chipotle", "/api/getvotes", "/api/getheavyvotes"]:
        assert path in body


@pytest.mark.parametrize("restaurant", ALL)
def test_legacy_api_increment_routes_unchanged(restaurant):
    # The legacy /api/<restaurant> routes increment the count by 1 and return
    # the new value as a bare string. This regression test confirms that exact
    # (unchanged) behavior is preserved.
    mapping = full_counts([10, 20, 30, 40])
    original = mapping[restaurant]
    with store_patch(mapping) as store:
        client = appmod.app.test_client()
        resp = client.get("/api/%s" % restaurant)
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == str(original + 1)
        assert store[restaurant] == original + 1


def test_legacy_getvotes_shape_unchanged():
    mapping = full_counts([1, 2, 3, 4])
    with store_patch(mapping):
        client = appmod.app.test_client()
        resp = client.get("/api/getvotes")
        assert resp.status_code == 200
        rows = json.loads(resp.get_data(as_text=True))
        names = [r["name"] for r in rows]
        assert names == ["outback", "bucadibeppo", "ihop", "chipotle"]
        by_name = {r["name"]: r["value"] for r in rows}
        for name in ALL:
            assert by_name[name] == mapping[name]


def test_legacy_api_routes_remain_unauthenticated():
    # /api/* must work with no session at all (Req 1.4).
    mapping = full_counts([0, 0, 0, 0])
    with store_patch(mapping):
        client = appmod.app.test_client()  # no session
        assert client.get("/api/getvotes").status_code == 200
        assert client.get("/api/outback").status_code == 200


def test_api_cors_header_present():
    # Existing CORS on /api/* preserved (Req 1.4).
    mapping = full_counts([0, 0, 0, 0])
    with store_patch(mapping):
        client = appmod.app.test_client()
        resp = client.get("/api/getvotes", headers={"Origin": "https://example.com"})
        assert "Access-Control-Allow-Origin" in resp.headers
