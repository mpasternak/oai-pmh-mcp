"""Testy renderowania modeli do text / json."""

import json

from oai_pmh_mcp import client, formatting
from tests.conftest import load_fixture


def records():
    return client.parse_list_records(load_fixture("list_records_page1.xml"))


def test_text_records_use_key_value_blocks():
    out = formatting.format_records(records(), "text")
    assert "identifier: oai:www.wbc.poznan.pl:1" in out
    assert "title: Pan Tadeusz" in out
    assert "subject: poezja; epopeja" in out  # wielowartościowe łączone
    assert "\n---\n" in out  # rekordy rozdzielone


def test_text_marks_deleted_record():
    out = formatting.format_records(records(), "text")
    assert "status: deleted" in out


def test_text_records_footer_shows_pagination():
    out = formatting.format_records(records(), "text")
    assert "resumption_token: TOKEN-PAGE-2" in out
    assert "12000" in out  # completeListSize widoczny dla modelu


def test_json_records_roundtrip():
    data = json.loads(formatting.format_records(records(), "json"))
    assert data["records"][0]["metadata"]["title"] == ["Pan Tadeusz"]
    assert data["records"][0]["identifier"] == "oai:www.wbc.poznan.pl:1"
    assert data["records"][1]["deleted"] is True
    assert data["resumption_token"] == "TOKEN-PAGE-2"
    assert data["complete_list_size"] == 12000


def test_text_identity():
    ident = client.parse_identify(load_fixture("identify.xml"))
    out = formatting.format_identity(ident, "text")
    assert "repository_name: Wielkopolska Digital Library" in out
    assert "granularity: YYYY-MM-DDThh:mm:ssZ" in out


def test_json_identity():
    ident = client.parse_identify(load_fixture("identify.xml"))
    data = json.loads(formatting.format_identity(ident, "json"))
    assert data["repository_name"] == "Wielkopolska Digital Library"
    assert data["admin_emails"] == ["admin@wbc.poznan.pl", "support@wbc.poznan.pl"]


def test_text_sets():
    sets = client.parse_list_sets(load_fixture("list_sets.xml"))
    out = formatting.format_sets(sets, "text")
    assert "rootCollection:books" in out
    assert "Książki" in out


def test_text_metadata_formats():
    fmts = client.parse_list_metadata_formats(load_fixture("list_metadata_formats.xml"))
    out = formatting.format_metadata_formats(fmts, "text")
    assert "oai_dc" in out
    assert "mods" in out
