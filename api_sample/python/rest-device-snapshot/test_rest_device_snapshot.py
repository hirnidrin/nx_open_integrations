# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""
Offline tests for rest_device_snapshot.py. No network, no server needed.

Run from this folder:  pytest -v
"""

import datetime as dt

import pytest

import rest_device_snapshot as sample


# ---------------------------------------------------------------------------
# parse_device_ids()
# ---------------------------------------------------------------------------

def test_parse_device_ids_splits_on_comma():
    assert sample.parse_device_ids("id1,id2,id3") == ["id1", "id2", "id3"]


def test_parse_device_ids_strips_whitespace_and_drops_empties():
    assert sample.parse_device_ids(" id1 , , id2 ,") == ["id1", "id2"]


def test_parse_device_ids_single_id():
    assert sample.parse_device_ids("only-one") == ["only-one"]


def test_parse_device_ids_blank_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_device_ids("  ,  ,")
    with pytest.raises(sample.ApiError):
        sample.parse_device_ids("")
    with pytest.raises(sample.ApiError):
        sample.parse_device_ids(None)


# ---------------------------------------------------------------------------
# parse_size()
# ---------------------------------------------------------------------------

def test_parse_size_none_or_blank_is_none():
    assert sample.parse_size(None) is None
    assert sample.parse_size("") is None


def test_parse_size_valid_passthrough():
    assert sample.parse_size("640x480") == "640x480"


def test_parse_size_invalid_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_size("not-a-size")
    with pytest.raises(sample.ApiError):
        sample.parse_size("640x")
    with pytest.raises(sample.ApiError):
        sample.parse_size("x480")


# ---------------------------------------------------------------------------
# parse_snapshot_timestamp()
# ---------------------------------------------------------------------------

def test_parse_snapshot_timestamp_none_or_blank_is_none():
    assert sample.parse_snapshot_timestamp(None) is None
    assert sample.parse_snapshot_timestamp("") is None


def test_parse_snapshot_timestamp_epoch_ms():
    assert sample.parse_snapshot_timestamp("1750000000000") == 1750000000000


def test_parse_snapshot_timestamp_iso8601_utc():
    ms = sample.parse_snapshot_timestamp("2026-06-15T12:00:00Z")
    expected = int(dt.datetime(2026, 6, 15, 12, 0, 0,
                                tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert ms == expected


def test_parse_snapshot_timestamp_naive_iso_treated_as_utc():
    ms = sample.parse_snapshot_timestamp("2026-06-15T12:00:00")
    expected = int(dt.datetime(2026, 6, 15, 12, 0, 0,
                                tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert ms == expected


def test_parse_snapshot_timestamp_invalid_raises():
    with pytest.raises(sample.ApiError):
        sample.parse_snapshot_timestamp("not-a-timestamp")


# ---------------------------------------------------------------------------
# epoch_ms_to_datetime()
# ---------------------------------------------------------------------------

def test_epoch_ms_to_datetime_round_trips_utc():
    ms = int(dt.datetime(2026, 6, 15, 12, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert sample.epoch_ms_to_datetime(ms) == dt.datetime(
        2026, 6, 15, 12, 0, 0, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# default_out_name()
# ---------------------------------------------------------------------------

def test_default_out_name_format():
    now = dt.datetime(2026, 6, 15, 12, 0, 0, tzinfo=dt.timezone.utc)
    name = sample.default_out_name("cam-1", "jpg", now=now)
    assert name == "snapshot-cam-1-2026-06-15T12-00-00.jpg"


def test_default_out_name_sanitizes_unsafe_characters():
    now = dt.datetime(2026, 6, 15, 12, 0, 0, tzinfo=dt.timezone.utc)
    name = sample.default_out_name("{a1b2/c3d4}", "png", now=now)
    assert name == "snapshot-_a1b2_c3d4_-2026-06-15T12-00-00.png"


# ---------------------------------------------------------------------------
# resolve_config() / missing_fields()
# ---------------------------------------------------------------------------

def _args(**overrides):
    base = {"host": None, "user": None, "password": None, "device_ids": None,
            "format": None, "size": None, "out_dir": None, "at": None}
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


def test_resolve_config_defaults_format_to_jpg():
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["format"] == "jpg"


def test_resolve_config_rejects_unsupported_format():
    with pytest.raises(sample.ApiError):
        sample.resolve_config(_args(device_ids="id1", format="bmp"), {})


def test_resolve_config_default_out_dir_is_cwd():
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["out_dir"] == "."


def test_resolve_config_uses_format_env_var(monkeypatch):
    monkeypatch.setenv("NX_SNAPSHOT_FORMAT", "png")
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["format"] == "png"


def test_resolve_config_uses_size_env_var(monkeypatch):
    monkeypatch.setenv("NX_SNAPSHOT_SIZE", "640x480")
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["size"] == "640x480"


def test_resolve_config_size_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("NX_SNAPSHOT_SIZE", "640x480")
    config = sample.resolve_config(_args(device_ids="id1", size="1920x1080"), {})
    assert config["size"] == "1920x1080"


def test_resolve_config_timestamp_defaults_to_none():
    config = sample.resolve_config(_args(device_ids="id1"), {})
    assert config["timestamp_ms"] is None


def test_resolve_config_parses_at_flag():
    config = sample.resolve_config(
        _args(device_ids="id1", at="2026-06-15T12:00:00Z"), {})
    expected = int(dt.datetime(2026, 6, 15, 12, 0, 0,
                                tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert config["timestamp_ms"] == expected


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
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.content = content

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
# NxServerClient.get_device_image()
# ---------------------------------------------------------------------------

def test_get_device_image_builds_url_without_size():
    session = FakeSession(get=FakeResponse(200, content=b"\xff\xd8jpeg-bytes"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    image = client.get_device_image("cam-1", fmt="jpg")

    assert image == b"\xff\xd8jpeg-bytes"
    assert session.get_url == (
        "https://srv:7001/rest/v4/devices/cam-1/image?timestampMs=-1&format=jpg")
    assert session.get_headers["Authorization"] == "Bearer abc123"


def test_get_device_image_includes_size_when_given():
    session = FakeSession(get=FakeResponse(200, content=b"bytes"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    client.get_device_image("cam-1", fmt="png", size="640x480")

    assert session.get_url == (
        "https://srv:7001/rest/v4/devices/cam-1/image"
        "?timestampMs=-1&format=png&size=640x480")


def test_get_device_image_uses_given_timestamp_ms():
    session = FakeSession(get=FakeResponse(200, content=b"bytes"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"

    client.get_device_image("cam-1", fmt="jpg", timestamp_ms=1750000000000)

    assert session.get_url == (
        "https://srv:7001/rest/v4/devices/cam-1/image"
        "?timestampMs=1750000000000&format=jpg")


def test_get_device_image_unauthorized_raises():
    session = FakeSession(get=FakeResponse(401, text="bad"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"
    with pytest.raises(sample.AuthError):
        client.get_device_image("cam-1")


def test_get_device_image_not_found_raises_apierror():
    session = FakeSession(get=FakeResponse(404, text="no such device"))
    client = sample.NxServerClient("https://srv:7001", "admin", "pw", session=session)
    client.token = "abc123"
    with pytest.raises(sample.ApiError):
        client.get_device_image("missing-cam")


def test_get_device_image_without_login_raises():
    client = sample.NxServerClient("https://srv:7001", "admin", "pw",
                                   session=FakeSession())
    with pytest.raises(sample.ApiError):
        client.get_device_image("cam-1")


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
    client.logout()  # should not raise or call delete
    assert session.delete_calls == 0
