"""Testy warstwy narzędzi (orkiestracja) z podstawionym klientem."""

import json

import pytest

from oai_pmh_mcp import tools
from tests.conftest import load_fixture


class FakeClient:
    """Podstawiony transport: zwraca kolejne nagrane odpowiedzi, zapisuje wywołania."""

    def __init__(self, *response_files):
        self._responses = [load_fixture(f) for f in response_files]
        self.calls = []

    async def fetch(self, base_url, verb, params):
        self.calls.append((verb, dict(params)))
        return self._responses.pop(0)


class LoopingClient:
    """Złośliwy serwer: zawsze oddaje token, ale zero rekordów (pętla)."""

    def __init__(self, response_file):
        self._data = load_fixture(response_file)
        self.calls = 0

    async def fetch(self, base_url, verb, params):
        self.calls += 1
        return self._data


BASE = "https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml"


async def test_identify_text():
    client = FakeClient("identify.xml")
    out = await tools.identify(client, BASE, format="text")
    assert "repository_name: Wielkopolska Digital Library" in out


async def test_list_records_xml_returns_raw_unparsed():
    client = FakeClient("list_records_page1.xml")
    out = await tools.list_records(client, BASE, format="xml")
    assert out.lstrip().startswith("<?xml")  # surowy oryginał, bez interpretacji
    assert "<OAI-PMH" in out


async def test_list_records_json():
    client = FakeClient("list_records_page1.xml")
    data = json.loads(await tools.list_records(client, BASE, format="json"))
    assert data["records"][0]["identifier"] == "oai:www.wbc.poznan.pl:1"


async def test_resumption_token_is_exclusive_argument():
    # Gdy podano token, do repozytorium leci TYLKO resumptionToken (+verb).
    client = FakeClient("list_records_page2.xml")
    await tools.list_records(
        client, BASE, metadata_prefix="oai_dc", set_="books", resumption_token="TOKEN-PAGE-2"
    )
    verb, params = client.calls[0]
    assert params == {"resumptionToken": "TOKEN-PAGE-2"}
    assert "metadataPrefix" not in params and "set" not in params


async def test_harvest_follows_token_across_pages():
    client = FakeClient("list_records_page1.xml", "list_records_page2.xml")
    out = await tools.harvest_records(client, BASE, max_records=500, format="text")
    # 3 rekordy razem (2 ze strony 1 z usuniętym + 1 ze strony 2)
    assert "oai:www.wbc.poznan.pl:1" in out
    assert "oai:www.wbc.poznan.pl:3" in out
    assert "truncated: false" in out.lower()
    assert len(client.calls) == 2  # podążył za tokenem


async def test_harvest_truncates_at_max_records():
    client = FakeClient("list_records_page1.xml")
    out = await tools.harvest_records(client, BASE, max_records=2, format="json")
    data = json.loads(out)
    assert data["truncated"] is True
    assert len(data["records"]) == 2
    assert data["resumption_token"] == "TOKEN-PAGE-2"  # token do wznowienia
    assert len(client.calls) == 1  # nie pobrał kolejnej strony


async def test_date_granularity_mismatch_rejected():
    client = FakeClient("list_records_page1.xml")
    with pytest.raises(ValueError):
        await tools.list_records(client, BASE, from_="2020-01-01", until="2020-12-31T00:00:00Z")


async def test_invalid_format_rejected():
    client = FakeClient("identify.xml")
    with pytest.raises(ValueError):
        await tools.identify(client, BASE, format="yaml")


async def test_harvest_terminates_on_token_without_records():
    # DoS: serwer zwraca token, ale 0 rekordów. Harvest MUSI się zatrzymać.
    client = LoopingClient("list_records_token_no_records.xml")
    out = await tools.harvest_records(client, BASE, max_records=500, format="text")
    assert client.calls < 5  # nie zapętlił się w nieskończoność
    assert "truncated" in out.lower()


async def test_harvest_caps_absurd_max_records():
    # DoS: model prosi o miliard rekordów -> twardy górny limit.
    client = FakeClient("list_records_page1.xml", "list_records_page2.xml")
    # nie powinno rzucić ani próbować nieograniczenie; kończy na wyczerpaniu stron
    out = await tools.harvest_records(client, BASE, max_records=10**9, format="text")
    assert "oai:www.wbc.poznan.pl:3" in out
