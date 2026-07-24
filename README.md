# oai-pmh-mcp

[![CI](https://github.com/mpasternak/oai-pmh-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mpasternak/oai-pmh-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/oai-pmh-mcp.svg)](https://pypi.org/project/oai-pmh-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

[![Install in Claude Desktop](https://img.shields.io/badge/Install_in-Claude_Desktop-D97757?style=for-the-badge&logo=anthropic&logoColor=white)](https://github.com/mpasternak/oai-pmh-mcp/releases/latest/download/oai-pmh-mcp.mcpb)
[![Install in Cursor](https://img.shields.io/badge/Install_in-Cursor-000000?style=for-the-badge&logo=cursor&logoColor=white)](https://cursor.com/en/install-mcp?name=oai-pmh-mcp&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJvYWktcG1oLW1jcCJdfQ==)
[![Install in VS Code](https://img.shields.io/badge/Install_in-VS_Code-0098FF?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect?url=vscode:mcp/install?%7B%22name%22%3A%22oai-pmh-mcp%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22oai-pmh-mcp%22%5D%7D)

> Nothing to configure — the repository address is passed at tool-call time, so a
> single installation handles any number of repositories.

**A universal [MCP](https://modelcontextprotocol.io/) server for the
[OAI-PMH](https://www.openarchives.org/pmh/) protocol** (Open Archives Initiative –
Protocol for Metadata Harvesting).

It lets any MCP client (Claude, ChatGPT, Cursor…) query **any** public OAI-PMH
repository — digital libraries built on **dLibra** (e.g. the
[Wielkopolska Digital Library](https://www.wbc.poznan.pl)), as well as DSpace,
EPrints, PubMed Central and others — with no per-host configuration. The
repository address (`base_url`) is supplied on every call.

## Features

A faithful wrapper around the six OAI-PMH verbs plus a convenient layer for bulk
harvesting:

| Tool | Role |
|---|---|
| `identify` | repository identity (name, protocol version, granularity, deleted-record policy) |
| `list_metadata_formats` | available metadata formats (oai_dc, mods, marc…) |
| `list_sets` | collections / sets |
| `list_identifiers` | record headers only (cheap overview) |
| `list_records` | a page of full records + pagination token |
| `get_record` | a single record by identifier |
| `harvest_records` | auto-pagination: fetches multiple pages up to a limit, resumable |

Output in three formats (`format`): `text` (default, token-efficient),
`json` (machine-readable), `xml` (raw original).

## Installation

```bash
uvx oai-pmh-mcp        # run without installing (stdio)
# or
uv tool install oai-pmh-mcp
```

## MCP client configuration

### Claude Code

```bash
claude mcp add oai-pmh -- uvx oai-pmh-mcp
```

### `mcp.json` (Cursor / others)

```json
{
  "mcpServers": {
    "oai-pmh": { "command": "uvx", "args": ["oai-pmh-mcp"] }
  }
}
```

## Transport

Defaults to **stdio**. Remote mode uses **streamable-HTTP**:

```bash
oai-pmh-mcp --transport http --host 0.0.0.0 --port 8000
```

## Example

> "Check what collections `https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml`
> has and show the 5 most recent records."

The model will call `identify` → `list_sets` → `list_records` and assemble the answer.

![Claude exploring the Wielkopolska Digital Library over OAI-PMH: it confirms the
endpoint with Identify, walks the 116 sets, and surfaces 18th-century Masonic
prints from the Masonica collection](docs/screenshot1.png)

*One prompt, pointed at the [Wielkopolska Digital Library](https://www.wbc.poznan.pl).
`identify` confirms the endpoint — OAI-PMH 2.0, records back to 2003-12-01,
`deletedRecord: persistent`. `list_sets` returns all 116 sets and finds the
interesting ones under `rootCollection:wbc:Mirabilium`. `list_records` then reads
out **Masonica** (267 records): the Grand Lodge of Hamburg library, confiscated
during the war and now held in Poznań — including a 1782 exposé of Masonic
ritual and the by-laws of a London lodge that met in the Half-Moon Tavern on
Cheapside.*

Nothing about that repository is hardcoded — the same tools answer the same way
for any OAI-PMH endpoint you name.

## Development

```bash
uv sync
uv run pytest            # unit tests (offline, fixtures)
uv run pytest -m integration   # network tests (optional)
uv run ruff check .
```

## Scope

OAI-PMH is a **metadata** protocol — the server does not fetch object content
(scans, PDFs). It is read-only, without authentication, without caching.

## Security

- **XML parsing is hardened** — the parser does not expand entities or reach out
  to the network/DTD (protection against XXE and "billion laughs" from untrusted
  repositories).
- **`harvest_records` has hard limits** (max records, max pages, abort on lack of
  progress) — a malicious server cannot trap the client in a loop.
- **SSRF by design:** the server fetches any `base_url` supplied by the client
  (that is the point). Only the `http`/`https` schemes are allowed. If you deploy
  the **remote (HTTP)** variant on a network with internal resources, run it in an
  environment with restricted outbound networking — the model could point at an
  internal address (e.g. a cloud metadata endpoint).

## License

[MIT](LICENSE)
