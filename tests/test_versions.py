"""Slice 15: the version notice. The service reports its version and what changed since the
version a device last ran, read from CHANGELOG.md."""
from pathlib import Path

from service.versions import parse_changelog, version_key, whats_new
from server_helpers import make_server, Device

CHANGELOG = Path(__file__).parent / "fixtures" / "changelog.md"


def test_versions_compare_by_number_not_text():
    assert version_key("v0.10.0") > version_key("0.9.1")
    assert version_key("v1.2.0-3-gabc123") == (1, 2, 0)
    assert version_key("dev") is None


def test_changelog_is_parsed_newest_first_without_unreleased():
    entries = parse_changelog(CHANGELOG.read_text())
    assert [e["version"] for e in entries] == ["0.3.0", "0.2.0", "0.1.0"]
    assert entries[1]["notes"] == ["Second test change", "Second test fix"]
    assert entries[1]["date"] == "2026-02-20"


def test_whats_new_lists_only_the_versions_the_device_has_not_seen():
    """Scenario: what's new lists only the versions the device has not seen"""
    entries = parse_changelog(CHANGELOG.read_text())
    assert [e["version"] for e in whats_new(entries, since="0.1.0", current="0.2.0")] == ["0.2.0"]
    assert [e["version"] for e in whats_new(entries, since="0.1.0", current="0.3.0")] == \
        ["0.3.0", "0.2.0"]
    assert whats_new(entries, since="0.2.0", current="0.2.0") == []
    # an unknown "since" (a build from a branch) gets only the current version's notes
    assert [e["version"] for e in whats_new(entries, since="dev", current="0.2.0")] == ["0.2.0"]


def test_service_reports_its_version_and_whats_new(database_url):
    """Scenario: what's new lists only the versions the device has not seen"""
    app, _, mailer = make_server(database_url, app_version="0.2.0", changelog=CHANGELOG)
    client = Device(app, mailer).client
    assert client.get("/v1/health").json()["app_version"] == "0.2.0"
    body = client.get("/v1/whats-new", params={"since": "0.1.0"}).json()
    assert body["version"] == "0.2.0"
    assert [e["version"] for e in body["entries"]] == ["0.2.0"]
    assert body["entries"][0]["notes"] == ["Second test change", "Second test fix"]


def test_missing_changelog_is_not_an_error(database_url, tmp_path):
    app, _, mailer = make_server(database_url, app_version="0.2.0",
                                 changelog=tmp_path / "none.md")
    body = Device(app, mailer).client.get("/v1/whats-new", params={"since": "0.1.0"}).json()
    assert body["entries"] == []
