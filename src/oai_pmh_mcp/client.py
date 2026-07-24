"""Klient OAI-PMH: czyste parsery XML + asynchroniczny transport HTTP.

Parsery (`parse_*`) są funkcjami czystymi — przyjmują bajty odpowiedzi i zwracają
modele. Dzięki temu testuje się je offline, na nagranych fixture'ach. Transport
(`OaiClient`) dokłada HTTP: budowanie URL, timeout, User-Agent, obsługę 503 +
Retry-After i ekskluzywność resumptionToken.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

import httpx
from lxml import etree

from . import __version__
from .errors import OaiHttpError, OaiParseError, OaiProtocolError
from .models import (
    Header,
    ListResult,
    MetadataFormat,
    Record,
    RepositoryIdentity,
    SetInfo,
)

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_EMPTY_LIST = dict(
    resumption_token=None, complete_list_size=None, cursor=None, expiration_date=None
)

# Hartowany parser: bez rozwijania encji (XXE / billion laughs), bez sieci i bez
# DTD. Chroni przy parsowaniu XML z dowolnych, niezaufanych repozytoriów.
_SAFE_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    dtd_validation=False,
    huge_tree=False,
)


# --- parsowanie (czyste funkcje) -----------------------------------------


def _looks_like_html(data: bytes) -> bool:
    return data.lstrip()[:200].lower().startswith((b"<!doctype html", b"<html"))


def _parse_root(data: bytes) -> etree._Element:
    if _looks_like_html(data):
        raise OaiParseError(
            "Repozytorium zwróciło stronę HTML zamiast XML OAI-PMH — prawdopodobnie "
            "limit zapytań lub weryfikacja przeglądarki (anty-bot). Spróbuj później."
        )
    try:
        root = etree.fromstring(data, _SAFE_PARSER)
    except etree.XMLSyntaxError as exc:
        raise OaiParseError(f"Odpowiedź nie jest poprawnym XML: {exc}") from exc
    if etree.QName(root).localname != "OAI-PMH":
        raise OaiParseError("Odpowiedź nie jest dokumentem OAI-PMH (brak <OAI-PMH>).")
    return root


def _error(root: etree._Element) -> tuple[str | None, str]:
    el = root.find("oai:error", NS)
    if el is None:
        return None, ""
    return el.get("code"), (el.text or "").strip()


def _raise_on_error(root: etree._Element) -> None:
    code, msg = _error(root)
    if code:
        raise OaiProtocolError(code, msg)


def _text(parent: etree._Element, tag: str) -> str:
    el = parent.find(f"oai:{tag}", NS)
    return el.text.strip() if el is not None and el.text else ""


def _container(root: etree._Element, verb: str) -> etree._Element:
    el = root.find(f"oai:{verb}", NS)
    if el is None:
        raise OaiParseError(f"Brak oczekiwanego elementu <{verb}> w odpowiedzi.")
    return el


def _parse_resumption(container: etree._Element) -> dict:
    el = container.find("oai:resumptionToken", NS)
    if el is None:
        return dict(_EMPTY_LIST)
    token = (el.text or "").strip() or None  # pusta wartość = koniec listy
    cls = el.get("completeListSize")
    cursor = el.get("cursor")
    return dict(
        resumption_token=token,
        complete_list_size=int(cls) if cls not in (None, "") else None,
        cursor=int(cursor) if cursor not in (None, "") else None,
        expiration_date=el.get("expirationDate"),
    )


def _parse_header(h: etree._Element) -> Header:
    return Header(
        identifier=_text(h, "identifier"),
        datestamp=_text(h, "datestamp"),
        set_specs=[s.text.strip() for s in h.findall("oai:setSpec", NS) if s.text],
        deleted=h.get("status") == "deleted",
    )


def _flatten_metadata(inner: etree._Element) -> dict[str, list[str]]:
    """Spłaszcza payload metadanych do {klucz: [wartości]}.

    Dla oai_dc klucz = nazwa lokalna elementu DC (title, creator…). Dla formatów
    zagnieżdżonych (mods) używa ścieżki nazw lokalnych rozdzielonej ' > '.
    """
    md: dict[str, list[str]] = {}

    def walk(el: etree._Element, prefix: str) -> None:
        children = [c for c in el if isinstance(c.tag, str)]
        name = etree.QName(el).localname
        path = f"{prefix} > {name}" if prefix else name
        if children:
            for child in children:
                walk(child, path)
        else:
            text = (el.text or "").strip()
            if text:
                md.setdefault(path, []).append(text)

    for child in (c for c in inner if isinstance(c.tag, str)):
        walk(child, "")
    return md


def _parse_record(rec: etree._Element) -> Record:
    header = _parse_header(_container_child(rec, "header"))
    md_el = rec.find("oai:metadata", NS)
    metadata = None
    metadata_xml = None
    if md_el is not None and len(md_el):
        inner = md_el[0]
        metadata_xml = etree.tostring(inner, encoding="unicode")
        metadata = _flatten_metadata(inner)
    about = [
        etree.tostring(a[0], encoding="unicode") for a in rec.findall("oai:about", NS) if len(a)
    ]
    return Record(header=header, metadata=metadata, metadata_xml=metadata_xml, about=about)


def _container_child(parent: etree._Element, tag: str) -> etree._Element:
    el = parent.find(f"oai:{tag}", NS)
    if el is None:
        raise OaiParseError(f"Brak elementu <{tag}> w rekordzie.")
    return el


def parse_identify(data: bytes) -> RepositoryIdentity:
    root = _parse_root(data)
    _raise_on_error(root)
    ident = _container(root, "Identify")
    return RepositoryIdentity(
        repository_name=_text(ident, "repositoryName"),
        base_url=_text(ident, "baseURL"),
        protocol_version=_text(ident, "protocolVersion"),
        admin_emails=[e.text.strip() for e in ident.findall("oai:adminEmail", NS) if e.text],
        earliest_datestamp=_text(ident, "earliestDatestamp"),
        deleted_record=_text(ident, "deletedRecord"),
        granularity=_text(ident, "granularity"),
    )


def _parse_list(data: bytes, verb: str, item_tag: str, builder) -> ListResult:
    root = _parse_root(data)
    code, msg = _error(root)
    if code == "noRecordsMatch":
        return ListResult(items=[], **_EMPTY_LIST)
    if code:
        raise OaiProtocolError(code, msg)
    container = _container(root, verb)
    items = [builder(el) for el in container.findall(f"oai:{item_tag}", NS)]
    return ListResult(items=items, **_parse_resumption(container))


def parse_list_records(data: bytes) -> ListResult:
    return _parse_list(data, "ListRecords", "record", _parse_record)


def parse_list_identifiers(data: bytes) -> ListResult:
    return _parse_list(data, "ListIdentifiers", "header", _parse_header)


def parse_get_record(data: bytes) -> Record:
    root = _parse_root(data)
    _raise_on_error(root)
    container = _container(root, "GetRecord")
    return _parse_record(_container_child(container, "record"))


def parse_list_metadata_formats(data: bytes) -> ListResult:
    def build(mf: etree._Element) -> MetadataFormat:
        return MetadataFormat(
            prefix=_text(mf, "metadataPrefix"),
            schema=_text(mf, "schema"),
            metadata_namespace=_text(mf, "metadataNamespace"),
        )

    return _parse_list(data, "ListMetadataFormats", "metadataFormat", build)


def parse_list_sets(data: bytes) -> ListResult:
    def build(s: etree._Element) -> SetInfo:
        return SetInfo(spec=_text(s, "setSpec"), name=_text(s, "setName"))

    return _parse_list(data, "ListSets", "set", build)


# --- transport HTTP -------------------------------------------------------

USER_AGENT = f"oai-pmh-mcp/{__version__}"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES_503 = 3
MAX_RETRY_WAIT = 60.0


class OaiClient:
    """Asynchroniczny transport: buduje żądanie OAI-PMH i zwraca surowe bajty."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self._sleep = sleep

    async def __aenter__(self) -> OaiClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, base_url: str, verb: str, params: dict) -> bytes:
        """GET base_url z parametrami OAI-PMH; honoruje 503 + Retry-After."""
        scheme = urlsplit(base_url).scheme.lower()
        if scheme not in ("http", "https"):
            raise OaiHttpError(
                f"Niedozwolony schemat URL {scheme!r} — dozwolone tylko http/https "
                f"(base_url: {base_url})."
            )
        query = {"verb": verb, **{k: v for k, v in params.items() if v is not None}}
        attempts = 0
        while True:
            try:
                # Strumieniowo: liczymy bajty na bieżąco i przerywamy po limicie,
                # by złośliwy serwer nie zbuforował gigabajtów do RAM.
                async with self._client.stream("GET", base_url, params=query) as resp:
                    if resp.status_code == 503 and attempts < MAX_RETRIES_503:
                        attempts += 1
                        await self._sleep(_retry_after_seconds(resp))
                        continue
                    if resp.status_code >= 400:
                        raise OaiHttpError(
                            f"Nie udało się połączyć z {base_url}: HTTP {resp.status_code}"
                        )
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > MAX_RESPONSE_BYTES:
                            raise OaiHttpError(
                                f"Odpowiedź z {base_url} przekracza limit {MAX_RESPONSE_BYTES} B."
                            )
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.HTTPError as exc:
                raise OaiHttpError(f"Nie udało się połączyć z {base_url}: {exc}") from exc


def _retry_after_seconds(resp: httpx.Response) -> float:
    raw = resp.headers.get("Retry-After", "")
    try:
        return max(0.0, min(float(raw), MAX_RETRY_WAIT))
    except ValueError:
        return 5.0  # nagłówek w formacie daty lub brak — rozsądny domyślny odstęp
