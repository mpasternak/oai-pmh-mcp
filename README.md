# oai-pmh-mcp

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

## Licencja

[MIT](LICENSE)
