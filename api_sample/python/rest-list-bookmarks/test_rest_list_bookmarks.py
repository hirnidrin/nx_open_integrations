# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""
Offline tests for rest_list_bookmarks.py. No network, no server needed.

Run from this folder:  pytest -v
"""

import datetime as dt
import json

import pytest

import rest_list_bookmarks as sample


# ---------------------------------------------------------------------------
# parse_device_ids()
# ---------------------------------------------------------------------------

def test_parse_device_ids_splits_on_comma():
    assert sample.parse_device_ids("id1,id2,id3") == ["id1", "id2", "id3"]


def test_parse_device_ids_strips_whitespace_and_drops_empties():
    assert sample.parse_device_ids(" id1 , , id2 ,") == ["id1", "id2"]


def test_parse_device_ids_blank_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_device_ids("")
    with pytest.raises(sample.ApiError):
        sample.parse_device_ids(None)


# ---------------------------------------------------------------------------
# parse_time_bound()
# ---------------------------------------------------------------------------

def test_parse_time_bound_none_or_blank_is_none():
    assert sample.parse_time_bound(None, "--start") is None
    assert sample.parse_time_bound("", "--start") is None


def test_parse_time_bound_epoch_ms():
    assert sample.parse_time_bound("1750000000000", "--start") == 1750000000000


def test_parse_time_bound_iso8601_utc():
    ms = sample.parse_time_bound("2026-06-15T12:00:00Z", "--end")
    expected = int(dt.datetime(2026, 6, 15, 12, 0, 0,
                                tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert ms == expected


def test_parse_time_bound_naive_iso_treated_as_utc():
    ms = sample.parse_time_bound("2026-06-15T12:00:00", "--start")
    expected = int(dt.datetime(2026, 6, 15, 12, 0, 0,
                                tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert ms == expected


def test_parse_time_bound_invalid_raises_with_flag_name():
    with pytest.raises(sample.ApiError, match="--start"):
        sample.parse_time_bound("not-a-timestamp", "--start")


# ---------------------------------------------------------------------------
# parse_limit()
# ---------------------------------------------------------------------------

def test_parse_limit_none_or_blank_is_none():
    assert sample.parse_limit(None) is None
    assert sample.parse_limit("") is None


def test_parse_limit_valid():
    assert sample.parse_limit("5") == 5


def test_parse_limit_zero_or_negative_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_limit("0")
    with pytest.raises(sample.ApiError):
        sample.parse_limit("-1")


def test_parse_limit_non_integer_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_limit("abc")


# ---------------------------------------------------------------------------
# format_bookmarks_json()
# ---------------------------------------------------------------------------

def test_format_bookmarks_json_empty_array():
    assert sample.format_bookmarks_json([]) == "[]"


def test_format_bookmarks_json_pretty_prints_full_records():
    bookmarks = [{
        "name": "Break-in",
        "description": "Rear door forced open",
        "startTimeMs": 1750000000000,
        "durationMs": 5000,
        "tags": ["security", "alert"],
        "id": "bm1_srv1",
    }]

    out = sample.format_bookmarks_json(bookmarks)

    assert json.loads(out) == bookmarks  # full records, nothing dropped
    assert "\n" in out  # pretty-printed, not a single line


# ---------------------------------------------------------------------------
# resolve_config() / missing_fields()
# ---------------------------------------------------------------------------

def _args(**overrides):
    base = {"host": None, "user": None, "password": None, "device_ids": None,
            "start": None, "end": None, "limit": None}
    base.update(overrides)
    return sample.argparse.Namespace(**base)


def test_resolve_config_uses_env_vars(monkeypatch):
    monkeypatch.setenv("NX_SERVER_HOST", "https://env:7001")
    monkeypatch.setenv("NX_SERVER_USER", "admin")
    monkeypatch.setenv("NX_SERVER_PASSWORD", "pw")
    monkeypatch.setenv("NX_DEVICE_IDS", "id1,id2")
    config = sample.resolve_config(_args(), {})
    assert config["host"] == "https://env:7001"
    assert config["device_ids"] == ["id1", "id2"]


def test_resolve_config_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("NX_DEVICE_IDS", "env-id")
    config = sample.resolve_config(_args(device_ids="cli-id"), {})
    assert config["device_ids"] == ["cli-id"]


def test_resolve_config_parses_start_and_end():
    config = sample.resolve_config(
        _args(device_ids="id1", start="2026-06-01T00:00:00Z",
              end="2026-06-30T00:00:00Z"), {})
    assert config["start_ms"] is not None
    assert config["end_ms"] is not None
    assert config["start_ms"] < config["end_ms"]


def test_resolve_config_start_end_default_to_none():
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["start_ms"] is None
    assert config["end_ms"] is None


def test_resolve_config_parses_limit():
    config = sample.resolve_config(_args(device_ids="id1", limit="1"), {})
    assert config["limit"] == 1


def test_missing_fields_reports_all_missing():
    config = {"host": None, "user": None, "password": "pw", "device_ids": []}
    assert set(sample.missing_fields(config)) == {"host", "user", "device_ids"}


def test_missing_fields_none_missing():
    config = {"host": "h", "user": "u", "password": "p", "device_ids": ["id1"]}
    assert sample.missing_fields(config) == []


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeSession:
    """Serves queued responses per verb and records calls (incl. DELETE count)."""

    def __init__(self, post=None, get=None, delete=None):
        self.verify = None
        self._post, self._get, self._delete = post, get, delete
        self.post_url = self.post_json = None
        self.get_url = self.get_headers = None
        self.delete_url = None
        self.delete_calls = 0

    def post(self, url, json=None, timeout=None):
        self.post_url, self.post_json = url, json
        return self._post

    def get(self, url, headers=None, timeout=None):
        self.get_url, self.get_headers = url, headers
        return self._get

    def delete(self, url, headers=None, timeout=None):
        self.delete_url = url
        self.delete_calls += 1
        return self._delete


# ---------------------------------------------------------------------------
# NxServerClient.login()
# ---------------------------------------------------------------------------

def test_login_posts_credentials_and_stores_token():
    session = FakeSession(post=FakeResponse(200, {"token": "abc123"}))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)

    token = client.login()

    assert token == "abc123"
    assert session.post_url == "https://srv:7001/rest/v4/login/sessions"
    assert session.post_json == {"username": "admin", "password": "pw",
                                 "setCookie": False}


def test_login_unauthorized_raises():
    session = FakeSession(post=FakeResponse(401, text="bad"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    with pytest.raises(sample.AuthError):
        client.login()


def test_login_without_token_raises_apierror():
    session = FakeSession(post=FakeResponse(200, {"nope": 1}))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    with pytest.raises(sample.ApiError):
        client.login()


# ---------------------------------------------------------------------------
# NxServerClient.get_device_bookmarks()
# ---------------------------------------------------------------------------

def test_get_device_bookmarks_default_url_orders_newest_first():
    session = FakeSession(get=FakeResponse(200, [{"id": "bm1"}]))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    bookmarks = client.get_device_bookmarks("cam-1")

    assert bookmarks == [{"id": "bm1"}]
    assert session.get_url == (
        "https://srv:7001/rest/v4/devices/cam-1/bookmarks"
        "?_orderBy=creationTimeMs&order=desc")
    assert session.get_headers["Authorization"] == "Bearer abc123"


def test_get_device_bookmarks_includes_start_end_limit_when_given():
    session = FakeSession(get=FakeResponse(200, []))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    client.get_device_bookmarks("cam-1", start_ms=1000, end_ms=2000, limit=1)

    assert session.get_url == (
        "https://srv:7001/rest/v4/devices/cam-1/bookmarks"
        "?_orderBy=creationTimeMs&order=desc"
        "&startTimeMs=1000&endTimeMs=2000&limit=1")


def test_get_device_bookmarks_unauthorized_raises():
    session = FakeSession(get=FakeResponse(401, text="bad"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"
    with pytest.raises(sample.AuthError):
        client.get_device_bookmarks("cam-1")


def test_get_device_bookmarks_not_found_raises_apierror():
    session = FakeSession(get=FakeResponse(404, text="no such device"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"
    with pytest.raises(sample.ApiError):
        client.get_device_bookmarks("missing-cam")


def test_get_device_bookmarks_without_login_raises():
    client = sample.NxServerClient("https://srv:7001", "admin", "pw",
                                   session=FakeSession())
    with pytest.raises(sample.ApiError):
        client.get_device_bookmarks("cam-1")


def test_get_device_bookmarks_unwraps_reply_envelope():
    payload = {"reply": [{"id": "bm1"}]}
    session = FakeSession(get=FakeResponse(200, payload))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    bookmarks = client.get_device_bookmarks("cam-1")

    assert bookmarks == [{"id": "bm1"}]


# ---------------------------------------------------------------------------
# NxServerClient.logout()
# ---------------------------------------------------------------------------

def test_logout_deletes_session_and_clears_token():
    session = FakeSession(delete=FakeResponse(200, {}))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    client.logout()

    assert session.delete_calls == 1
    assert session.delete_url == "https://srv:7001/rest/v4/login/sessions/abc123"
    assert client.token is None


def test_logout_without_token_is_noop():
    session = FakeSession()
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.logout()
    assert session.delete_calls == 0
