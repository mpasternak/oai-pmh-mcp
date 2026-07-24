"""Testy czystych parserów OAI-PMH (bez sieci, na fixture'ach)."""

import pytest

from oai_pmh_mcp import client
from oai_pmh_mcp.errors import OaiParseError, OaiProtocolError

# --- Identify -------------------------------------------------------------


def test_parse_identify_extracts_core_fields(fixture):
    ident = client.parse_identify(fixture("identify.xml"))
    assert ident.repository_name == "Wielkopolska Digital Library"
    assert ident.base_url == "https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml"
    assert ident.protocol_version == "2.0"
    assert ident.earliest_datestamp == "2003-12-01T00:00:00Z"
    assert ident.deleted_record == "persistent"
    assert ident.granularity == "YYYY-MM-DDThh:mm:ssZ"


def test_parse_identify_collects_multiple_admin_emails(fixture):
    ident = client.parse_identify(fixture("identify.xml"))
    assert ident.admin_emails == ["admin@wbc.poznan.pl", "support@wbc.poznan.pl"]


# --- ListRecords ----------------------------------------------------------


def test_parse_list_records_reads_record_and_flat_dc(fixture):
    result = client.parse_list_records(fixture("list_records_page1.xml"))
    first = result.items[0]
    assert first.header.identifier == "oai:www.wbc.poznan.pl:1"
    assert first.header.set_specs == ["rootCollection:books"]
    assert first.deleted is False
    assert first.metadata["title"] == ["Pan Tadeusz"]
    assert first.metadata["subject"] == ["poezja", "epopeja"]  # wielowartościowe


def test_parse_list_records_marks_deleted_record(fixture):
    result = client.parse_list_records(fixture("list_records_page1.xml"))
    deleted = result.items[1]
    assert deleted.header.identifier == "oai:www.wbc.poznan.pl:2"
    assert deleted.deleted is True
    assert deleted.metadata is None


def test_parse_list_records_surfaces_resumption_token_and_attrs(fixture):
    result = client.parse_list_records(fixture("list_records_page1.xml"))
    assert result.resumption_token == "TOKEN-PAGE-2"
    assert result.complete_list_size == 12000
    assert result.cursor == 0
    assert result.expiration_date == "2026-07-24T11:00:00Z"


def test_empty_resumption_token_means_end_of_list(fixture):
    # Strona 2 ma <resumptionToken> bez wartości -> koniec listy.
    result = client.parse_list_records(fixture("list_records_page2.xml"))
    assert result.resumption_token is None
    assert result.complete_list_size == 12000  # atrybuty nadal odczytane


def test_parse_list_records_keeps_raw_metadata_xml(fixture):
    result = client.parse_list_records(fixture("list_records_page1.xml"))
    raw = result.items[0].metadata_xml
    assert raw is not None
    assert "Pan Tadeusz" in raw


# --- GetRecord ------------------------------------------------------------


def test_parse_get_record_unescapes_entities(fixture):
    record = client.parse_get_record(fixture("get_record.xml"))
    assert record.metadata["title"] == ["Pan Tadeusz & inne utwory"]
    assert record.metadata["language"] == ["pol"]


# --- ListMetadataFormats --------------------------------------------------


def test_parse_metadata_formats(fixture):
    result = client.parse_list_metadata_formats(fixture("list_metadata_formats.xml"))
    prefixes = [f.prefix for f in result.items]
    assert prefixes == ["oai_dc", "mods"]
    assert result.items[0].metadata_namespace == "http://www.openarchives.org/OAI/2.0/oai_dc/"


# --- ListSets -------------------------------------------------------------


def test_parse_sets(fixture):
    result = client.parse_list_sets(fixture("list_sets.xml"))
    assert result.items[0].spec == "rootCollection"
    assert result.items[1].spec == "rootCollection:books"
    assert result.items[1].name == "Książki"


# --- Błędy ----------------------------------------------------------------


def test_protocol_error_raises_with_code(fixture):
    with pytest.raises(OaiProtocolError) as exc:
        client.parse_list_records(fixture("error_badArgument.xml"))
    assert exc.value.code == "badArgument"


def test_no_records_match_is_empty_success_not_error(fixture):
    # noRecordsMatch NIE jest błędem — to pusty, udany wynik.
    result = client.parse_list_records(fixture("error_noRecordsMatch.xml"))
    assert result.items == []
    assert result.resumption_token is None


def test_non_xml_response_raises_parse_error():
    with pytest.raises(OaiParseError):
        client.parse_list_records(b"<html><body>404 Not Found</body></html>")


def test_html_interstitial_gives_helpful_hint():
    # dLibra/WBC pod obciążeniem zwraca 200 + stronę HTML anty-bota.
    html = b"<!DOCTYPE html>\n<html><head><title>High Load - Verifying Browser</title>"
    with pytest.raises(OaiParseError) as exc:
        client.parse_list_records(html)
    assert "HTML" in str(exc.value)


# --- bezpieczeństwo parsera XML (XXE / billion laughs) --------------------


def test_external_entity_is_not_resolved(tmp_path):
    # XXE: encja zewnętrzna wskazująca lokalny plik NIE może zostać wczytana.
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET-XXE")
    payload = f"""<?xml version="1.0"?>
    <!DOCTYPE r [<!ENTITY xxe SYSTEM "file://{secret}">]>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <Identify><repositoryName>&xxe;</repositoryName></Identify>
    </OAI-PMH>""".encode()
    ident = client.parse_identify(payload)
    assert "TOPSECRET-XXE" not in ident.repository_name


def test_billion_laughs_does_not_blow_up():
    # Bomba encyjna nie może rozwinąć się do gigantycznego ciągu.
    bomb = b"""<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
      <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
    ]>
    <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
      <Identify><repositoryName>&lol4;</repositoryName></Identify>
    </OAI-PMH>"""
    ident = client.parse_identify(bomb)
    # encje nierozwinięte -> krótka (lub pusta) wartość, brak eksplozji pamięci
    assert len(ident.repository_name) < 1000


# --- regresja na prawdziwej odpowiedzi WBC --------------------------------


def test_parses_real_wbc_response_with_cdata_and_lang(fixture):
    # Prawdziwa odpowiedź dLibry/WBC: wartości w CDATA, atrybuty xml:lang,
    # długi resumptionToken. Zabezpiecza przed regresją na realnym XML.
    result = client.parse_list_records(fixture("wbc_real_listrecords.xml"))
    assert len(result.items) == 20
    assert result.resumption_token  # niepusty token kontynuacji
    first = result.items[0]
    assert first.metadata["title"]  # CDATA rozpakowane do zwykłego tekstu
    # xml:lang nie zaśmieca kluczy — używamy nazw lokalnych DC
    assert all(">" not in key for key in first.metadata)
