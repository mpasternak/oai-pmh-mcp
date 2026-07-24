"""Renderowanie modeli OAI-PMH do formatów `text` (token-lean) i `json`.

Format `xml` (surowy oryginał) obsługuje warstwa narzędzi — tu go nie ma, bo
parsery odrzucają kopertę protokołu.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .models import ListResult, Record, RepositoryIdentity

MULTIVALUE_SEP = "; "
RECORD_SEP = "\n---\n"


# --- reprezentacje pośrednie ---------------------------------------------


def _record_dict(rec: Record) -> dict:
    d: dict = {
        "identifier": rec.header.identifier,
        "datestamp": rec.header.datestamp,
        "sets": rec.header.set_specs,
        "deleted": rec.deleted,
    }
    if rec.deleted:
        d["metadata"] = None
    else:
        d["metadata"] = rec.metadata or {}
    if rec.about:
        d["about"] = rec.about
    return d


def _list_envelope(result: ListResult, key: str, items: list) -> dict:
    env: dict = {key: items}
    if result.resumption_token:
        env["resumption_token"] = result.resumption_token
    if result.complete_list_size is not None:
        env["complete_list_size"] = result.complete_list_size
    if result.cursor is not None:
        env["cursor"] = result.cursor
    if result.expiration_date:
        env["expiration_date"] = result.expiration_date
    return env


# --- text -----------------------------------------------------------------


def _kv_block(pairs: list[tuple[str, object]]) -> str:
    lines = []
    for key, value in pairs:
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = MULTIVALUE_SEP.join(str(v) for v in value)
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _record_text(rec: Record) -> str:
    pairs: list[tuple[str, object]] = [
        ("identifier", rec.header.identifier),
        ("datestamp", rec.header.datestamp),
        ("sets", rec.header.set_specs),
    ]
    if rec.deleted:
        pairs.append(("status", "deleted"))
    else:
        for field_name, values in (rec.metadata or {}).items():
            pairs.append((field_name, values))
    return _kv_block(pairs)


def _pagination_footer(result: ListResult) -> str:
    if not result.resumption_token:
        return ""
    parts = [f"resumption_token: {result.resumption_token}"]
    if result.complete_list_size is not None:
        pos = result.cursor if result.cursor is not None else "?"
        parts.append(f"(rekord {pos} z {result.complete_list_size})")
    if result.expiration_date:
        parts.append(f"token wygasa: {result.expiration_date}")
    return "\n".join(["---", " ".join(parts)])


def _list_text(result: ListResult, render_item, empty_msg: str) -> str:
    if not result.items:
        return empty_msg
    body = RECORD_SEP.join(render_item(i) for i in result.items)
    footer = _pagination_footer(result)
    return f"{body}\n{footer}" if footer else body


# --- API publiczne --------------------------------------------------------


def format_records(result: ListResult, fmt: str, truncated: bool | None = None) -> str:
    if fmt == "json":
        env = _list_envelope(result, "records", [_record_dict(r) for r in result.items])
        if truncated is not None:
            env["truncated"] = truncated
        return _json(env)
    body = _list_text(result, _record_text, "Brak rekordów (noRecordsMatch).")
    if truncated is not None:
        body = f"{body}\ntruncated: {str(truncated).lower()}"
    return body


def format_record(rec: Record, fmt: str) -> str:
    if fmt == "json":
        return _json(_record_dict(rec))
    return _record_text(rec)


def format_identifiers(result: ListResult, fmt: str) -> str:
    if fmt == "json":
        items = [
            {
                "identifier": h.identifier,
                "datestamp": h.datestamp,
                "sets": h.set_specs,
                "deleted": h.deleted,
            }
            for h in result.items
        ]
        return _json(_list_envelope(result, "identifiers", items))

    def render(h) -> str:
        pairs = [("identifier", h.identifier), ("datestamp", h.datestamp), ("sets", h.set_specs)]
        if h.deleted:
            pairs.append(("status", "deleted"))
        return _kv_block(pairs)

    return _list_text(result, render, "Brak identyfikatorów (noRecordsMatch).")


def format_identity(ident: RepositoryIdentity, fmt: str) -> str:
    if fmt == "json":
        return _json(asdict(ident))
    return _kv_block(
        [
            ("repository_name", ident.repository_name),
            ("base_url", ident.base_url),
            ("protocol_version", ident.protocol_version),
            ("admin_emails", ident.admin_emails),
            ("earliest_datestamp", ident.earliest_datestamp),
            ("deleted_record", ident.deleted_record),
            ("granularity", ident.granularity),
        ]
    )


def format_sets(result: ListResult, fmt: str) -> str:
    if fmt == "json":
        items = [{"spec": s.spec, "name": s.name} for s in result.items]
        return _json(_list_envelope(result, "sets", items))
    return _list_text(
        result,
        lambda s: _kv_block([("setSpec", s.spec), ("setName", s.name)]),
        "Brak zestawów.",
    )


def format_metadata_formats(result: ListResult, fmt: str) -> str:
    if fmt == "json":
        items = [
            {"prefix": f.prefix, "schema": f.schema, "namespace": f.metadata_namespace}
            for f in result.items
        ]
        return _json({"formats": items})
    return _list_text(
        result,
        lambda f: _kv_block(
            [("prefix", f.prefix), ("schema", f.schema), ("namespace", f.metadata_namespace)]
        ),
        "Brak formatów metadanych.",
    )


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
