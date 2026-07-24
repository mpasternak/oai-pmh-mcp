# oai-pmh-mcp — projekt (spec)

- **Data:** 2026-07-24
- **Status:** zatwierdzony do wdrożenia
- **Autor:** Michał Pasternak (+ Claude)

## 1. Cel i zakres

`oai-pmh-mcp` to **uniwersalny serwer MCP dla protokołu OAI-PMH** (Open Archives
Initiative – Protocol for Metadata Harvesting). Pozwala dowolnemu klientowi MCP
(LLM) odpytywać **dowolne** publiczne repozytorium OAI-PMH — biblioteki cyfrowe
oparte o dLibrę (np. Wielkopolska Biblioteka Cyfrowa), DSpace, EPrints, PubMed
Central i inne — bez konfiguracji per-host.

Serwer jest jednocześnie **wiernym cienkim wrapperem** sześciu czasowników
protokołu **oraz** dostarcza wygodną nakładkę do interaktywnej eksploracji i
budowania raportów/wyciągów (podejście „C" z brainstormingu).

### Motywacja

Na dzień pisania speca nie istnieje żaden publiczny, generyczny serwer MCP dla
OAI-PMH (zweryfikowano — projekt `oxenstierna` z wcześniejszych wyników
wyszukiwania nie istnieje; `AI-Riksarkivet/ra-mcp` jest realny, ale dotyczy
full-text search po transkrypcjach, nie OAI-PMH). Nisza jest wolna.

### Non-goals (świadome YAGNI)

- **Pobieranie treści** obiektów cyfrowych (skany, PDF-y, IIIF). OAI-PMH służy
  wyłącznie do metadanych. Treść dLibry/IIIF to osobny, przyszły temat.
- **Operacje zapisu.** Protokół jest read-only.
- **Autoryzacja / uwierzytelnianie.** Celujemy w repozytoria publiczne.
- **Cache / trwałe składowanie.** Serwer jest bezstanowy.

## 2. Architektura

Cztery warstwy o rozdzielonych odpowiedzialnościach, każda testowalna osobno:

```
┌─ transport ──────────────────────────────────────────────┐
│ server.py — aplikacja FastMCP; wybór stdio | HTTP         │
│             jednym argumentem/env, jeden entrypoint       │
├─ narzędzia (tools) ──────────────────────────────────────┤
│ tools.py — 7 narzędzi MCP; walidują parametry, wołają     │
│            klienta, renderują wynik formatterem           │
├─ klient OAI-PMH ─────────────────────────────────────────┤
│ client.py — buduje URL (base_url+verb+params), GET (httpx)│
│             parsuje XML, wykrywa <error>, oddaje token    │
│ models.py — Header, Record, RepositoryIdentity, MetadataFormat,
│             SetInfo, ListResult                           │
│ errors.py — typy wyjątków ↔ kody błędów OAI-PMH           │
├─ formatowanie ───────────────────────────────────────────┤
│ formatting.py — Record/lista → text | json | xml          │
└──────────────────────────────────────────────────────────┘
```

### Decyzja: własny cienki parser

OAI-PMH parsujemy **samodzielnie** (`httpx` + `lxml`) za wąskim interfejsem
klienta. Uzasadnienie: Dublin Core (`oai_dc`) jest płaski (15 powtarzalnych
elementów), a protokół ma tylko 6 czasowników i jeden mechanizm paginacji —
to niewiele kodu. Izolacja za interfejsem `OaiClient` pozwala w przyszłości
podmienić parser na Sickle/pyoai/własny fork bez ruszania warstwy narzędzi.
Unikamy w ten sposób wiązania się dziś ze starzejącą się zależnością (Sickle).

### Pliki

```
oai-pmh-mcp/
├── pyproject.toml            # uv, zależności, entry point, metadane
├── README.md
├── LICENSE                   # MIT (do potwierdzenia z userem przy publikacji)
├── .pre-commit-config.yaml   # ruff (lint + format)
├── .github/workflows/ci.yml  # matryca Python × testy
├── src/oai_pmh_mcp/
│   ├── __init__.py
│   ├── server.py             # FastMCP app + wybór transportu + CLI
│   ├── tools.py              # 7 narzędzi MCP
│   ├── client.py             # OaiClient: HTTP + parsowanie XML + token
│   ├── models.py             # dataclasses
│   ├── formatting.py         # render text|json|xml
│   └── errors.py             # wyjątki
└── tests/
    ├── conftest.py
    ├── fixtures/             # nagrane odpowiedzi XML (WBC + inne)
    ├── test_client.py
    ├── test_formatting.py
    ├── test_tools.py
    └── test_integration.py   # opcjonalne, sieć, skippable
```

## 3. Narzędzia MCP (7)

Wierne 6 czasowników + 1 nakładka. Wspólne parametry: `base_url` (wymagany),
`metadata_prefix` (domyślnie `"oai_dc"`), `from_`/`until` (daty ISO), `set_`,
`resumption_token`, `format` (`"text"` | `"json"` | `"xml"`, domyślnie `text`).

| Narzędzie | Czasownik OAI | Rola |
|---|---|---|
| `identify` | Identify | tożsamość repo: nazwa, `baseURL`, wersja protokołu, e-mail admina, `earliestDatestamp`, `deletedRecord`, `granularity`. Też sanity-check hosta. |
| `list_metadata_formats` | ListMetadataFormats | dostępne prefiksy (oai_dc, mods, marc…); opcjonalny `identifier` |
| `list_sets` | ListSets | kolekcje/zestawy; może paginować |
| `list_identifiers` | ListIdentifiers | *same nagłówki* (identifier, datestamp, setSpec, status) — tani przegląd |
| `list_records` | ListRecords | jedna strona pełnych rekordów + `resumption_token` |
| `get_record` | GetRecord | jeden rekord po `identifier` (wymagany) |
| `harvest_records` | ListRecords (pętla) | **nakładka**: auto-podąża za `resumptionToken` do `max_records` (domyślnie 500), zwraca rekordy + `truncated` + ostatni token do kontynuacji |

### Parametry `harvest_records`

`base_url`, `metadata_prefix="oai_dc"`, `from_`, `until`, `set_`,
`max_records=500`, `format="text"`. Pętla po stronie serwera podąża za
`resumptionToken` aż do wyczerpania **lub** osiągnięcia `max_records`
(wtedy `truncated=True` i zwracany ostatni token, by model mógł kontynuować).

## 4. Format wyjścia

Format dobrany do czasownika, sterowany parametrem `format`:

- **`text`** (domyślny, token-lean): listy rekordów jako bloki `pole: wartość`
  rozdzielone `---`; pola wielowartościowe łączone. Dublin Core jest płaski,
  więc `klucz: wartość` w zupełności wystarcza i jest tańszy tokenowo niż JSON.
  `GetRecord` → pełny komplet pól w tym samym stylu.
- **`json`**: ustrukturyzowany dict (koperta protokołu + payload metadanych),
  gdy klient chce parsować maszynowo.
- **`xml`**: surowy oryginał odpowiedzi repozytorium — dla pól spoza Dublin
  Core i debugowania. Zero utraty wierności.

Każdy wynik listowy zawiera `resumption_token` (jeśli jest) — **nieprzezroczysty**,
oddawany modelowi dosłownie do kolejnego wywołania.

## 5. Przepływ danych i paginacja

```
narzędzie → walidacja params
          → client.request(base_url, verb, params)
          → httpx GET (timeout, User-Agent)
          → parse XML
          → jeśli <error code=...>  → typed error (lub pusty wynik dla noRecordsMatch)
          → w innym wypadku          → obiekty (Header/Record/…)
          → formatter(format)        → string
```

`resumptionToken`: warstwa klienta **nie interpretuje** tokenu — surfacuje go w
`ListResult.resumption_token`. Narzędzia listowe oddają go modelowi; model podaje
w kolejnym wywołaniu jako `resumption_token`. Uwaga protokolarna: gdy podano
`resumptionToken`, **nie wolno** wysyłać innych argumentów doboru
(`metadataPrefix`, `from`, `until`, `set`) — klient to egzekwuje.

## 6. Obsługa błędów

- **Sieć** (timeout / DNS / 4xx / 5xx): czytelny komunikat, nie stacktrace —
  „Nie udało się połączyć z {base_url}: {powód}". Domyślny timeout ~30 s,
  nagłówek `User-Agent: oai-pmh-mcp/<wersja>". Rozmiar odpowiedzi z rozsądnym
  limitem.
- **Błędy protokołu OAI-PMH** — 8 kodów, mapowanych na czytelny komunikat z
  kodem i opisem:
  - `badArgument`, `badVerb`, `badResumptionToken`, `cannotDisseminateFormat`,
    `idDoesNotExist`, `noSetHierarchy`, `noMetadataFormats` → błąd narzędzia.
  - **`noRecordsMatch` → pusty, ale udany wynik** (nie błąd — normalne przy
    zawężaniu po dacie/zestawie).
- **Odpowiedź nie-XML** (np. strona HTML 404, redirect na login): „Odpowiedź
  spod {url} nie jest poprawnym XML OAI-PMH".
- **Rekordy usunięte** (`status="deleted"` w nagłówku): reprezentowane jawnie
  (nagłówek bez metadanych, flaga `deleted=True`).

## 7. Testy (TDD)

- **pytest**; unit-testy klienta na **nagranych fixture'ach XML** (prawdziwe
  odpowiedzi z WBC i paru innych, zapisane w `tests/fixtures/`) — zero sieci w
  unitach.
- Pokrycie per czasownik: happy path, kontynuacja po `resumptionToken`, każdy
  kod błędu, rekord usunięty, `noRecordsMatch`.
- Formatter: `text` / `json` / `xml` dla pojedynczego rekordu i dla listy;
  pola wielowartościowe; znaki specjalne/encje XML.
- `harvest_records`: łączenie wielu stron + ucięcie na `max_records`
  (`truncated=True` + token).
- `test_integration.py`: kilka testów na prawdziwym endpoincie (WBC),
  oznaczonych `@pytest.mark.integration` i skippable (bez sieci w CI domyślnie).

## 8. Pakowanie i publikacja

- **uv + pyproject.toml**, Python **3.11+** (baseline; CI matryca 3.11–3.13).
- Entry point konsolowy: `oai-pmh-mcp` → `oai_pmh_mcp.server:main`.
- Zależności runtime: `mcp` (FastMCP), `httpx`, `lxml`.
- Dev: `pytest`, `pytest-asyncio` (jeśli async), `ruff`.
- Transport: `main()` wybiera stdio (domyślnie) lub streamable-HTTP przez
  argument CLI / env (`--transport http --host --port`).
- Publikacja jako **GitHub `mpasternak/oai-pmh-mcp`**; przed publicznym pushem
  audyt skillem `oss-github-publisher` (licencja, CI, sekrety, PII, metadane).

## 9. Kryteria akceptacji

1. `identify(base_url=WBC)` zwraca poprawną tożsamość repozytorium.
2. `list_records` zwraca stronę rekordów i działający `resumption_token`.
3. Podanie tokenu w kolejnym wywołaniu pobiera następną stronę.
4. `harvest_records(max_records=N)` łączy strony i poprawnie sygnalizuje ucięcie.
5. `noRecordsMatch` daje pusty, udany wynik; pozostałe kody błędów — czytelny błąd.
6. `format=xml` zwraca surowy, niezmodyfikowany XML.
7. Serwer startuje w trybie stdio i (opcjonalnie) HTTP z jednego entrypointu.
8. Testy jednostkowe przechodzą offline (fixture'y), lint (ruff) czysty.
