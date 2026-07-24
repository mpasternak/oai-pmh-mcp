"""Modele danych OAI-PMH (dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Header:
    """Nagłówek rekordu: koperta protokołu."""

    identifier: str
    datestamp: str
    set_specs: list[str] = field(default_factory=list)
    deleted: bool = False


@dataclass
class Record:
    """Rekord: nagłówek + payload metadanych (lub brak, gdy usunięty)."""

    header: Header
    metadata: dict[str, list[str]] | None = None  # spłaszczony widok (oai_dc)
    metadata_xml: str | None = None  # surowy wewnętrzny XML <metadata>
    about: list[str] = field(default_factory=list)  # surowe bloki <about>

    @property
    def deleted(self) -> bool:
        return self.header.deleted


@dataclass
class RepositoryIdentity:
    repository_name: str
    base_url: str
    protocol_version: str
    admin_emails: list[str]
    earliest_datestamp: str
    deleted_record: str
    granularity: str


@dataclass
class MetadataFormat:
    prefix: str
    schema: str
    metadata_namespace: str


@dataclass
class SetInfo:
    spec: str
    name: str


@dataclass
class ListResult:
    """Wynik operacji listowej + stan paginacji (resumptionToken i atrybuty)."""

    items: list
    resumption_token: str | None = None
    complete_list_size: int | None = None
    cursor: int | None = None
    expiration_date: str | None = None
