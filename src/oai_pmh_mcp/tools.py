"""Warstwa narzędzi: orkiestracja fetch → parse → format.

Funkcje są niezależne od frameworka MCP (przyjmują klienta jako argument), więc
testuje się je z podstawionym transportem. `server.py` opakowuje je w narzędzia
FastMCP.

Zasady wspólne:
- `format` ∈ {text, json, xml}; `xml` zwraca surowy, nieparsowany oryginał.
- `resumption_token` jest argumentem *ekskluzywnym* (OAI-PMH §3.5): gdy podany,
  do repozytorium leci wyłącznie `resumptionToken`.
- Para dat `from_`/`until` musi mieć tę samą granularność.
"""

from __future__ import annotations

from . import client as client_module
from . import formatting
from .models import ListResult

VALID_FORMATS = {"text", "json", "xml"}

# Twarde limity chroniące przed DoS (złośliwy/wadliwy serwer OAI-PMH).
MAX_HARVEST_RECORDS = 10_000
MAX_HARVEST_PAGES = 1_000
MAX_HARVEST_BYTES = 50 * 1024 * 1024  # łączny limit pamięci harvestu (50 MB)


def _check_format(fmt: str) -> None:
    if fmt not in VALID_FORMATS:
        raise ValueError(f"Nieznany format {fmt!r}. Dozwolone: text, json, xml.")


def _granularity(date: str) -> str:
    return "day" if len(date) == 10 else "datetime"


def _validate_date_range(from_: str | None, until: str | None) -> None:
    if from_ and until and _granularity(from_) != _granularity(until):
        raise ValueError(
            "from_ i until muszą mieć tę samą granularność — oba 'YYYY-MM-DD' albo "
            "oba pełny 'YYYY-MM-DDThh:mm:ssZ'. Sprawdź granularity repozytorium "
            "przez narzędzie identify."
        )


def _selective_params(metadata_prefix, from_, until, set_) -> dict:
    return {
        "metadataPrefix": metadata_prefix,
        "from": from_,
        "until": until,
        "set": set_,
    }


async def _fetch_list(
    client, base_url, verb, metadata_prefix, from_, until, set_, resumption_token
) -> bytes:
    if resumption_token:
        params = {"resumptionToken": resumption_token}
    else:
        _validate_date_range(from_, until)
        params = _selective_params(metadata_prefix, from_, until, set_)
    return await client.fetch(base_url, verb, params)


# --- narzędzia ------------------------------------------------------------


async def identify(client, base_url: str, format: str = "text") -> str:
    _check_format(format)
    data = await client.fetch(base_url, "Identify", {})
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_identity(client_module.parse_identify(data), format)


async def list_metadata_formats(
    client, base_url: str, identifier: str | None = None, format: str = "text"
) -> str:
    _check_format(format)
    data = await client.fetch(base_url, "ListMetadataFormats", {"identifier": identifier})
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_metadata_formats(
        client_module.parse_list_metadata_formats(data), format
    )


async def list_sets(
    client, base_url: str, resumption_token: str | None = None, format: str = "text"
) -> str:
    _check_format(format)
    params = {"resumptionToken": resumption_token} if resumption_token else {}
    data = await client.fetch(base_url, "ListSets", params)
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_sets(client_module.parse_list_sets(data), format)


async def list_identifiers(
    client,
    base_url: str,
    metadata_prefix: str = "oai_dc",
    from_: str | None = None,
    until: str | None = None,
    set_: str | None = None,
    resumption_token: str | None = None,
    format: str = "text",
) -> str:
    _check_format(format)
    data = await _fetch_list(
        client, base_url, "ListIdentifiers", metadata_prefix, from_, until, set_, resumption_token
    )
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_identifiers(client_module.parse_list_identifiers(data), format)


async def list_records(
    client,
    base_url: str,
    metadata_prefix: str = "oai_dc",
    from_: str | None = None,
    until: str | None = None,
    set_: str | None = None,
    resumption_token: str | None = None,
    format: str = "text",
) -> str:
    _check_format(format)
    data = await _fetch_list(
        client, base_url, "ListRecords", metadata_prefix, from_, until, set_, resumption_token
    )
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_records(client_module.parse_list_records(data), format)


async def get_record(
    client,
    base_url: str,
    identifier: str,
    metadata_prefix: str = "oai_dc",
    format: str = "text",
) -> str:
    _check_format(format)
    data = await client.fetch(
        base_url, "GetRecord", {"identifier": identifier, "metadataPrefix": metadata_prefix}
    )
    if format == "xml":
        return data.decode("utf-8", errors="replace")
    return formatting.format_record(client_module.parse_get_record(data), format)


async def harvest_records(
    client,
    base_url: str,
    metadata_prefix: str = "oai_dc",
    from_: str | None = None,
    until: str | None = None,
    set_: str | None = None,
    resumption_token: str | None = None,
    max_records: int = 500,
    format: str = "text",
) -> str:
    """Auto-podąża za resumptionToken do `max_records`. Rekordy `deleted` liczą
    się do limitu. `format=xml` zwraca listę surowych odpowiedzi stron."""
    _check_format(format)
    if not resumption_token:
        _validate_date_range(from_, until)
    # Cap na absurdalne max_records (model mógłby poprosić o miliard).
    max_records = min(max(max_records, 1), MAX_HARVEST_RECORDS)

    records: list = []
    raw_pages: list[str] = []
    token = resumption_token
    last: ListResult | None = None
    pages = 0
    total_bytes = 0

    while True:
        data = await _fetch_list(
            client, base_url, "ListRecords", metadata_prefix, from_, until, set_, token
        )
        total_bytes += len(data)
        if format == "xml":
            raw_pages.append(data.decode("utf-8", errors="replace"))
        last = client_module.parse_list_records(data)
        pages += 1
        new_count = len(last.items)
        records.extend(last.items)
        token = last.resumption_token
        # Stop: brak tokenu; osiągnięto limit rekordów (NIE tniemy w środku strony
        # — dopuszczamy overshoot < 1 strona, by zwrócony token był spójny i nie
        # gubić rekordów przy wznowieniu); brak postępu (0 rekordów mimo tokenu =
        # złośliwy/wadliwy serwer); twardy limit stron; limit łącznej pamięci.
        if (
            not token
            or len(records) >= max_records
            or new_count == 0
            or pages >= MAX_HARVEST_PAGES
            or total_bytes >= MAX_HARVEST_BYTES
        ):
            break

    truncated = token is not None  # token nadal jest => zostało więcej rekordów

    if format == "xml":
        sep = "\n<!-- ===== następna strona OAI-PMH ===== -->\n"
        return sep.join(raw_pages)

    synth = ListResult(
        items=records,
        resumption_token=token if truncated else None,
        complete_list_size=last.complete_list_size if last else None,
        cursor=last.cursor if last else None,
        expiration_date=last.expiration_date if last else None,
    )
    return formatting.format_records(synth, format, truncated=truncated)
