"""Testy integracyjne uderzające w prawdziwe repozytorium (WBC).

Domyślnie pomijane (`-m 'not integration'` w pyproject). Uruchom świadomie:
    uv run pytest -m integration
"""

import pytest

from oai_pmh_mcp import tools
from oai_pmh_mcp.client import OaiClient

pytestmark = pytest.mark.integration

WBC = "https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml"


# WBC bywa wolne — hojny timeout, by test integracyjny nie łapał ReadTimeout.
TIMEOUT = 90.0


async def test_identify_against_wbc():
    async with OaiClient(timeout=TIMEOUT) as c:
        out = await tools.identify(c, WBC, format="text")
    assert "repository_name:" in out


async def test_list_records_first_page_against_wbc():
    async with OaiClient(timeout=TIMEOUT) as c:
        out = await tools.list_records(c, WBC, format="text")
    assert "identifier:" in out
