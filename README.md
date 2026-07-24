# oai-pmh-mcp

[![CI](https://github.com/mpasternak/oai-pmh-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mpasternak/oai-pmh-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**Uniwersalny serwer [MCP](https://modelcontextprotocol.io/) dla protokołu
[OAI-PMH](https://www.openarchives.org/pmh/)** (Open Archives Initiative –
Protocol for Metadata Harvesting).

Pozwala dowolnemu klientowi MCP (Claude, ChatGPT, Cursor…) odpytywać **dowolne**
publiczne repozytorium OAI-PMH — biblioteki cyfrowe oparte o **dLibrę** (np.
[Wielkopolska Biblioteka Cyfrowa](https://www.wbc.poznan.pl)), a także DSpace,
EPrints, PubMed Central i inne — bez konfiguracji per-host. Adres repozytorium
(`base_url`) podaje się w każdym wywołaniu.

## Możliwości

Wierny wrapper sześciu czasowników OAI-PMH + wygodna nakładka do masowego
pobierania:

| Narzędzie | Rola |
|---|---|
| `identify` | tożsamość repozytorium (nazwa, wersja protokołu, granularność, polityka usuniętych) |
| `list_metadata_formats` | dostępne formaty metadanych (oai_dc, mods, marc…) |
| `list_sets` | kolekcje / zestawy |
| `list_identifiers` | same nagłówki rekordów (tani przegląd) |
| `list_records` | strona pełnych rekordów + token paginacji |
| `get_record` | pojedynczy rekord po identyfikatorze |
| `harvest_records` | auto-paginacja: pobiera wiele stron do limitu, z możliwością wznowienia |

Wyjście w trzech formatach (`format`): `text` (domyślny, oszczędny tokenowo),
`json` (maszynowy), `xml` (surowy oryginał).

## Instalacja

```bash
uvx oai-pmh-mcp        # uruchomienie bez instalacji (stdio)
# lub
uv tool install oai-pmh-mcp
```

## Konfiguracja klienta MCP

### Claude Code

```bash
claude mcp add oai-pmh -- uvx oai-pmh-mcp
```

### `mcp.json` (Cursor / inne)

```json
{
  "mcpServers": {
    "oai-pmh": { "command": "uvx", "args": ["oai-pmh-mcp"] }
  }
}
```

## Transport

Domyślnie **stdio**. Tryb zdalny **streamable-HTTP**:

```bash
oai-pmh-mcp --transport http --host 0.0.0.0 --port 8000
```

## Przykład

> „Sprawdź, jakie kolekcje ma `https://www.wbc.poznan.pl/dlibra/oai-pmh-repository.xml`
> i pokaż 5 najnowszych rekordów."

Model wywoła `identify` → `list_sets` → `list_records` i złoży odpowiedź.

## Rozwój

```bash
uv sync
uv run pytest            # testy jednostkowe (offline, fixture'y)
uv run pytest -m integration   # testy sieciowe (opcjonalne)
uv run ruff check .
```

## Zakres

OAI-PMH to protokół **metadanych** — serwer nie pobiera treści obiektów
(skanów, PDF-ów). To read-only, bez autoryzacji, bez cache.

## Bezpieczeństwo

- **Parsowanie XML jest hartowane** — parser nie rozwija encji ani nie sięga do
  sieci/DTD (ochrona przed XXE i „billion laughs" z niezaufanych repozytoriów).
- **`harvest_records` ma twarde limity** (max rekordów, max stron, przerwanie przy
  braku postępu) — złośliwy serwer nie zapętli klienta.
- **SSRF z natury narzędzia:** serwer pobiera dowolny `base_url` podany przez
  klienta (taki jest cel). Dozwolone są tylko schematy `http`/`https`. Jeśli
  wdrażasz wariant **zdalny (HTTP)** w sieci z zasobami wewnętrznymi, uruchom go w
  środowisku z ograniczeniem sieci wychodzącej — model mógłby wskazać adres
  wewnętrzny (np. endpoint metadanych chmury).

## Licencja

[MIT](LICENSE)
