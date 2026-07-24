"""Serwer MCP: rejestruje 7 narzędzi OAI-PMH i wybiera transport (stdio | http).

Każde narzędzie tworzy krótkotrwałego `OaiClient`, deleguje do `tools.*` i zwraca
tekst. Nazwy parametrów widoczne dla modelu są opisowe (`date_from`, `date_until`,
`set_spec`, `prefix`) i mapowane na argumenty protokołu OAI-PMH.
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from . import tools
from .client import OaiClient


def build_server() -> FastMCP:
    mcp = FastMCP("oai-pmh")

    @mcp.tool()
    async def identify(base_url: str, format: str = "text") -> str:
        """Tożsamość repozytorium OAI-PMH: nazwa, wersja protokołu, granularność
        dat, polityka rekordów usuniętych. Dobre na start (sanity-check hosta).

        base_url: pełny adres endpointu OAI-PMH (np.
            https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml).
        """
        async with OaiClient() as c:
            return await tools.identify(c, base_url, format=format)

    @mcp.tool()
    async def list_metadata_formats(
        base_url: str, identifier: str | None = None, format: str = "text"
    ) -> str:
        """Dostępne formaty metadanych (prefiksy): oai_dc, mods, marc… Opcjonalnie
        dla jednego rekordu (identifier)."""
        async with OaiClient() as c:
            return await tools.list_metadata_formats(
                c, base_url, identifier=identifier, format=format
            )

    @mcp.tool()
    async def list_sets(
        base_url: str, resumption_token: str | None = None, format: str = "text"
    ) -> str:
        """Kolekcje/zestawy repozytorium. setSpec bywa hierarchiczny (dwukropki,
        np. 'institution:faculty'). Może paginować (resumption_token)."""
        async with OaiClient() as c:
            return await tools.list_sets(
                c, base_url, resumption_token=resumption_token, format=format
            )

    @mcp.tool()
    async def list_identifiers(
        base_url: str,
        prefix: str = "oai_dc",
        date_from: str | None = None,
        date_until: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
        format: str = "text",
    ) -> str:
        """Same nagłówki rekordów (identyfikator, data, zestawy) — tani przegląd
        bez metadanych. date_from/date_until = OAI 'from'/'until' (ta sama
        granularność!). resumption_token jest argumentem ekskluzywnym."""
        async with OaiClient() as c:
            return await tools.list_identifiers(
                c,
                base_url,
                metadata_prefix=prefix,
                from_=date_from,
                until=date_until,
                set_=set_spec,
                resumption_token=resumption_token,
                format=format,
            )

    @mcp.tool()
    async def list_records(
        base_url: str,
        prefix: str = "oai_dc",
        date_from: str | None = None,
        date_until: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
        format: str = "text",
    ) -> str:
        """Jedna strona pełnych rekordów (metadane) + resumption_token do kolejnej
        strony. date_from/date_until = OAI 'from'/'until' (ta sama granularność).
        resumption_token jest argumentem ekskluzywnym (bez innych filtrów)."""
        async with OaiClient() as c:
            return await tools.list_records(
                c,
                base_url,
                metadata_prefix=prefix,
                from_=date_from,
                until=date_until,
                set_=set_spec,
                resumption_token=resumption_token,
                format=format,
            )

    @mcp.tool()
    async def get_record(
        base_url: str, identifier: str, prefix: str = "oai_dc", format: str = "text"
    ) -> str:
        """Pojedynczy rekord po identyfikatorze OAI (np. oai:host:123)."""
        async with OaiClient() as c:
            return await tools.get_record(
                c, base_url, identifier=identifier, metadata_prefix=prefix, format=format
            )

    @mcp.tool()
    async def harvest_records(
        base_url: str,
        prefix: str = "oai_dc",
        date_from: str | None = None,
        date_until: str | None = None,
        set_spec: str | None = None,
        resumption_token: str | None = None,
        max_records: int = 500,
        format: str = "text",
    ) -> str:
        """Masowe pobranie: automatycznie podąża za resumptionToken do max_records.
        Zwraca 'truncated' i (jeśli ucięto) token do wznowienia — podaj go jako
        resumption_token, by kontynuować. Rekordy usunięte liczą się do limitu."""
        async with OaiClient() as c:
            return await tools.harvest_records(
                c,
                base_url,
                metadata_prefix=prefix,
                from_=date_from,
                until=date_until,
                set_=set_spec,
                resumption_token=resumption_token,
                max_records=max_records,
                format=format,
            )

    return mcp


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oai-pmh-mcp",
        description="Uniwersalny serwer MCP dla protokołu OAI-PMH.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio (domyślny, lokalny) lub http (streamable-HTTP, zdalny).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host dla transportu http.")
    parser.add_argument("--port", type=int, default=8000, help="Port dla transportu http.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    mcp = build_server()
    if args.transport == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
