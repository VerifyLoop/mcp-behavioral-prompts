# Social Trends Intelligence — Piano di costruzione

Documento di **Fase 0 + Fase 1** della metodologia guided-coding, scritto per il branch
`claude/social-trends-mcp-plan-picE5`. La Fase 0 è la spec di prodotto in italiano leggibile
(cosa costruiamo e perché); la Fase 1 è il piano tecnico (come, in che ordine, con quali boundary).

Data: 2026-05-30. Status: **piano proposto, in attesa di OK per implementazione.**

Riferimento di stile e architettura: il progetto gemello `stem-solver` (server MCP custom che
incapsula la verifica deterministica, agente che fa solo orchestrazione, iterazione guidata da
eval run immutabili). Riusiamo gli stessi tre principi qui, adattati al dominio dei dati social.

---

## 0. TL;DR

Costruiamo **`social-trends-mcp`**: un *server MCP di aggregazione* (più una CLI per analisti e un
piccolo agente "skill-based") che mette davanti a Claude/Cursor una manciata di tool ad alto valore
per l'analisi dei trend social (TikTok, Instagram, Twitch, e altre 27+ piattaforme), normalizzando
in uno schema canonico i dati che arrivano da quattro upstream eterogenei:

| Upstream | Cosa dà | Come si collega | Auth |
|---|---|---|---|
| **Apify** | 34.000+ "Actors" di scraping (hashtag, audio, creator di tendenza) | Remote MCP `https://mcp.apify.com` (Streamable HTTP) | OAuth nel browser |
| **Bright Data (Web MCP)** | Sblocco geo/CAPTCHA, output Markdown già formattato per l'IA | `npx @brightdata/mcp` con env `GROUPS` | API token |
| **ScrapeCreators** | API unificata real-time su 27+ piattaforme, metadati profondi (regione creator, demografia audience) | `npx @scrape-creators/mcp` **oppure** CLI | header `x-api-key` |
| **Twitch CLI** | Dati ufficiali Twitch + `mock-api` per testare le automazioni senza bruciare quota | CLI ufficiale `twitch` | Client-ID + Secret |

Il valore non sta nel "chiamare le API" — sta nel **layer in mezzo**: deduplica, normalizzazione
cross-platform, breakdown geografico, governance di rate-limit e costo, e una CLI che gli analisti
possono usare senza aprire una chat. L'agente è solo orchestrazione; tutta la logica deterministica
(normalizzazione, ranking, dedup) vive nel server, esattamente come in `stem-solver`.

---

## 1. Contesto e problema

Nel 2026 l'analisi seria dei trend social richiede dati **real-time e granulari** (nazione per
nazione, regione del creator, demografia dell'audience). Le API ufficiali delle piattaforme sono
troppo restrittive o non espongono affatto questi tagli. Il protocollo **MCP (Model Context
Protocol)** è ormai lo standard de-facto per collegare un agente IA a qualsiasi fonte esterna in
modo uniforme; le **CLI** coprono il caso d'uso dell'analista/sviluppatore che automatizza fuori
dalla chat.

Il problema concreto che il programma risolve: oggi per rispondere a *"quali audio TikTok stanno
esplodendo in Italia e Germania questa settimana, e quali creator li stanno cavalcando?"* devi
orchestrare a mano tre o quattro servizi diversi, ognuno con schema, auth e rate-limit propri. Noi
incapsuliamo quell'orchestrazione dietro pochi tool puliti.

### Vincolo non negoziabile: legalità e ToS

Lo scraping di dati social tocca i Terms of Service delle piattaforme e (in UE) il GDPR. Regole del
progetto, da rispettare in ogni tool:

- **Solo dati pubblici.** Niente login-walled, niente dati personali oltre a metadati pubblici di
  account pubblici.
- **Si delega il rischio agli upstream specializzati** (Apify, Bright Data, ScrapeCreators) che
  gestiscono proxy/compliance come loro core business — noi non scriviamo scraper diretti.
- **Provenienza tracciata.** Ogni record normalizzato porta `source`, `fetched_at`, `upstream_run_id`.
- Niente PII aggregata o reidentificazione. Demografia solo a livello aggregato fornito dall'upstream.

Questa sezione è un boundary, non un disclaimer: i tool che la violerebbero non entrano in V1.

---

## 2. Architettura ad alto livello

Mono-repo a tre componenti, sullo stampo di `stem-solver`:

- **`server/`** — il cuore: un processo **FastMCP** che espone i tool canonici (`trends.*`,
  `creator.*`, `audio.*`, `compare.*`) e che, sotto, fa da *client* verso gli upstream (Apify MCP,
  Bright Data MCP, ScrapeCreators API/CLI, Twitch CLI). Qui vivono normalizzazione, dedup, ranking,
  caching e budget governance.
- **`cli/`** — la CLI `social-trends` (Typer) per analisti: stessi tool del server, ma da terminale,
  output human-readable di default e `--json` per il piping. Wrappa anche i sotto-comandi utili degli
  upstream (login, mock-api Twitch).
- **`evaluation/`** — harness di valutazione: dataset di "domande di trend" con expected-shape,
  runner parallelizzato, e report immutabili committati in `evaluation/runs/`. Misura *recall delle
  fonti*, *freschezza* e *coerenza cross-platform*, non solo "ha risposto".

L'agente vero e proprio (un `LlmAgent` con skill — vedi §5) è opzionale in V1: il deliverable minimo
è server MCP + CLI. L'agente skill-based è il primo item di V2.

### I quattro boundary

Come in `stem-solver`, ragioniamo per punti di contatto netti:

1. **client → server MCP.** Un client MCP (Claude Desktop, Cursor, Claude Code) o la CLI chiama un
   tool canonico, es. `trends.hashtags(platform, country, window)`. Input validato Pydantic.
2. **server → upstream provider.** Il server sceglie il provider giusto per il tool (routing in
   `providers/registry.py`), chiama Apify MCP / Bright Data MCP / ScrapeCreators / Twitch, con
   retry+backoff e budget guard. Un tool può fare *fan-out* su più provider e fondere i risultati.
3. **server → cache/storage.** Risposte normalizzate cacheate (TTL per tipo di dato: trend volatili
   TTL corto, metadati creator TTL lungo). Provenienza salvata per ogni record.
4. **server ↔ evaluation.** L'eval runner importa i tool in-process (niente HTTP), inietta un
   *provider mock* (incluso il `mock-api` di Twitch) e confronta lo shape/contenuto della risposta
   con l'expected del dataset.

### Data flow (esempio: `trends.audio`)

```
   ingest: AudioTrendsRequest(platform=tiktok, country=IT, window=7d)
        │
        ▼
   resolve_provider("audio", platform) ──► REGISTRY ──► ScrapeCreators (primary)
        │                                              Apify actor (fallback/enrich)
        ▼
   budget_guard.check(estimated_cost)         ◄── rate-limit & $ governance
        │
        ▼
   fan_out: ScrapeCreators.tiktok_trending_sounds(country=IT)
            Apify.call("clockworks/tiktok-scraper", {...})   (opzionale enrich)
        │
        ▼
   normalize() ──► list[CanonicalTrend]  (dedup per audio_id, merge metriche, attach provenance)
        │
        ▼
   rank() ──► ordinamento per growth_rate, taglio top-N
        │
        ▼
   AudioTrendsResponse(items=[...], sources=[...], cost_estimate_usd, cache_hit)
```

---

## 3. Le quattro fonti — come ci colleghiamo (dettaglio verificato)

Tutto verificato contro la documentazione ufficiale a maggio 2026 (link in §9).

### 3.1 Apify — `https://mcp.apify.com`

Metodo raccomandato: **remote MCP server OAuth**, nessun token da incollare. Si aggiunge un custom
connector in Claude Desktop con URL `https://mcp.apify.com`; al primo uso il browser apre il login
Apify e autorizza. Note operative chiave:

- Transport: **Streamable HTTP**. La SSE è stata rimossa il **1 aprile 2026** — non usarla.
- Rate limit: **30 req/s per utente** (vale per Actor run, storage, doc query).
- In alternativa headless/server-side: header `Authorization: Bearer <APIFY_TOKEN>`.
- Per i trend social gli Actor utili sono gli scraper TikTok/Instagram (hashtag, sound, profile).

Nel nostro server, Apify è il provider per gli scraping "larghi" (hashtag/audio discovery) e per
l'enrichment quando ScrapeCreators non copre un taglio.

### 3.2 Bright Data — The Web MCP (`@brightdata/mcp`)

Server MCP che dà accesso web "sbloccato" (proxy, anti-CAPTCHA, geo) con **output Markdown già
pulito per l'IA**. Configurazione per *tool bundle* via env:

- `GROUPS` = lista di bundle separati da virgola (es. `GROUPS="social"` per i tool social,
  oppure `browser,advanced_scraping`).
- Priorità modalità: `PRO_MODE=true` (tutti i tool) → `GROUPS`/`TOOLS` (whitelist) → default *rapid
  mode* (toolkit base). Noi partiamo in whitelist (`GROUPS=social`) per superficie minima.

Bright Data è il provider per il **breakdown geografico reale** (vedere un trend "come lo vede" un
utente in un dato paese) e per i casi in cui gli altri vengono bloccati.

### 3.3 ScrapeCreators — API unificata + CLI + MCP

API real-time su **27+ piattaforme** (TikTok, Instagram, Twitch, YouTube, LinkedIn, …). Auth
semplice: singolo header **`x-api-key`**, niente OAuth dance, niente SDK. Tre modi di consumarla,
tutti ufficiali e mantenuti:

- **MCP server**: `npx @scrape-creators/mcp` — ogni endpoint diventa un tool first-class.
- **CLI**: `scrapecreators auth login`, poi ~110 comandi (`scrapecreators tiktok profile …`).
  Flag utili: `--clean` (toglie booleani/valori vuoti), `--output <file>`. C'è anche
  `scrapecreators agent add claude` per auto-iniettare la config MCP nell'agente.
- **Claude Code skill** first-party.

ScrapeCreators è il nostro **provider primario** per metadati profondi: regione del creator,
demografia dell'audience, metriche real-time. È quello con il miglior rapporto copertura/semplicità.

### 3.4 Twitch CLI

Strumento ufficiale `twitch`. Setup: `twitch configure -i <Client-ID> -s <Secret>`. Comandi:
`twitch api …` (chiamate reali), `twitch mock-api generate` + mock server su
`http://localhost:8080/mock` (sostituisce `https://api.twitch.tv/helix`).

> **Nota di realtà:** la Twitch API **non** espone un endpoint "trends" nativo, e la `mock-api` non
> lo simula. I "trend Twitch" li deriviamo noi da `Get Streams` / `Get Games` (top per spettatori) +
> i metadati profilo/stream di ScrapeCreators. Il valore della Twitch CLI per noi è doppio: (a)
> dati ufficiali affidabili su giochi/stream top, (b) il `mock-api` per testare le nostre
> automazioni **a costo zero e deterministico** — lo riusiamo come provider mock nell'eval (§6).

---

## 4. Tool canonici esposti dal server (V1)

Superficie minima e ad alto valore. Ogni tool è string/struct-in, struct-out, validato Pydantic, con
`source[]`, `cost_estimate_usd`, `cache_hit` nella risposta.

| Tool | Firma (semplificata) | Provider primario | Note |
|---|---|---|---|
| `trends.hashtags` | `(platform, country, window) -> Hashtag[]` | ScrapeCreators → Apify | growth_rate, volume |
| `trends.audio` | `(platform, country, window) -> AudioTrend[]` | ScrapeCreators → Apify | solo TikTok/IG in V1 |
| `creator.profile` | `(platform, handle) -> CreatorProfile` | ScrapeCreators | regione, audience demo |
| `creator.top` | `(platform, niche, country) -> CreatorRef[]` | ScrapeCreators | ranking per crescita |
| `twitch.top` | `(kind=games\|streams, country?) -> TwitchEntry[]` | Twitch CLI/API | dati ufficiali |
| `geo.view` | `(url, country) -> Markdown` | Bright Data | come appare in-country |
| `compare.crossplatform` | `(topic, platforms[], country) -> CrossReport` | fan-out | il tool "wow" |

`compare.crossplatform` è la ragione d'essere del progetto: prende un topic, lo cerca in parallelo su
più piattaforme via i provider giusti, normalizza in un unico report con presenza/volume/sentiment
per piattaforma e per paese.

---

## 5. Skill dell'agente (opzionale V1 / primo item V2)

Se/quando aggiungiamo l'agente, riusiamo il *pattern skill* di `stem-solver`: un solo `LlmAgent` che
si specializza via system-prompt addendum + tool whitelist, con dispatch ibrido (esplicito o auto).

- **`trend_scout`** — discovery larga (hashtag/audio emergenti). Whitelist: `trends.*`, `geo.view`.
- **`creator_intel`** — dossier su un creator/nicchia. Whitelist: `creator.*`, `compare.*`.
- **`cross_platform_analyst`** — il report comparato. Whitelist: tutti.
- **`live_pulse`** — focus Twitch/live. Whitelist: `twitch.*`, `creator.profile`.

Le metriche di qualità di queste skill le definisce l'eval (§6), non l'impressione.

---

## 6. Evaluation — iterare misurando

Stesso DNA di `stem-solver`: pochi casi difficili, in parallelo, con run immutabili committati. Qui
"giusto" non è una verifica simbolica ma uno **shape+content check** più un giudice opzionale.

- **Dataset** (`evaluation/datasets/*.jsonl`): ~5 query per skill, con `expected_shape` (campi
  obbligatori, almeno N sorgenti distinte, freschezza < window) e, dove possibile, `expected_facts`
  verificabili (es. "il gioco X è nei top 10 Twitch in questa finestra").
- **Provider mock**: l'eval gira con upstream mockati — incluso il **`mock-api` di Twitch** — così i
  run sono deterministici, gratis e ripetibili. Un set "live" separato (opt-in, costoso) valida
  contro le API reali.
- **Metriche**: `source_recall` (quante fonti attese ha toccato), `freshness` (età max dei record),
  `cross_consistency` (i numeri concordano tra provider entro tolleranza), `cost_usd`, `latency_ms`.
- **Giudice LLM** (opt-in): valuta utilità/azionabilità del report 1-5 su dimensioni fisse, vede la
  trace completa dei tool_call.
- **Output**: `evaluation/runs/<utc>__<commit>__<set>.json`, immutabile, committato — unica fonte di
  verità per i diff cross-branch.

---

## 7. Config di esempio (riferimento per chi integra)

Estratto `claude_desktop_config.json` per collegare gli upstream direttamente (utile in dev, prima
che il nostro server li incapsuli):

```jsonc
{
  "mcpServers": {
    "apify":          { "url": "https://mcp.apify.com" },          // OAuth nel browser
    "scrapecreators": { "command": "npx", "args": ["@scrape-creators/mcp"],
                        "env": { "SCRAPECREATORS_API_KEY": "<x-api-key>" } },
    "brightdata":     { "command": "npx", "args": ["@brightdata/mcp"],
                        "env": { "API_TOKEN": "<token>", "GROUPS": "social" } },
    "social-trends":  { "command": "poetry",
                        "args": ["--directory", "server", "run", "social-trends-mcp",
                                 "serve", "--transport", "stdio"] }   // il NOSTRO server
  }
}
```

CLI rapida per gli upstream (dev/test):

```bash
scrapecreators auth login            # login sicuro
scrapecreators agent add claude      # auto-inietta la config MCP
npm install -g apify-cli && apify call <actor>   # automazioni Apify
twitch configure -i <Client-ID> -s <Secret>      # auth Twitch
twitch mock-api generate && twitch mock-api start # mock server :8080
```

---

## 8. Piano di build per fasi

Ogni fase è un PR auto-contenuto, verde su CI (ruff strict, mypy strict, pytest), sul branch
`claude/social-trends-mcp-plan-picE5`.

- **Fase 1 — Scheletro server.** Riusa lo scaffold FastMCP di questo repo (`config`, `logging`,
  `app`, `serve --transport stdio|http`). Aggiunge `health_check`, `providers/registry.py`,
  schemi canonici Pydantic (`CanonicalTrend`, `CreatorProfile`, …). Niente provider reale ancora.
- **Fase 2 — Provider ScrapeCreators.** Primo upstream end-to-end: `creator.profile`,
  `trends.hashtags`. Client `x-api-key`, retry/backoff, normalizzazione, provenienza. Test con
  fixture registrate (no rete in CI).
- **Fase 3 — CLI analisti.** `social-trends` (Typer): stessi tool, `--json`, login helper.
- **Fase 4 — Caching + budget guard.** TTL per tipo di dato, `cost_estimate_usd`, rate-limit per
  provider (Apify 30 req/s ecc.).
- **Fase 5 — Provider Twitch + eval harness.** `twitch.top` + integrazione `mock-api` come provider
  mock. Primo `evaluation/` con dataset e run immutabili.
- **Fase 6 — Apify + Bright Data.** `trends.audio` (enrich Apify), `geo.view` (Bright Data Markdown).
- **Fase 7 — `compare.crossplatform`.** Il tool di fan-out che fonde tutto. Eval dedicato.
- **Fase 8 (V2) — Agente skill-based.** Le quattro skill di §5 con dispatch ibrido + giudice LLM.

Definition of Done per fase: tool/feature implementato, test con coverage gate, doc inline,
almeno un eval run committato dalla Fase 5 in poi.

---

## 9. Stack tecnico

- **Python 3.12+, Poetry, FastMCP** (`mcp[cli]`) — coerente con questo repo e con `stem-solver`.
- **Pydantic v2** per ogni schema; **Typer + Rich** per la CLI; **httpx** per i client upstream.
- **pytest / pytest-asyncio / pytest-cov**, **ruff** strict, **mypy** strict, **pre-commit**.
- Upstream via Node: `npx @scrape-creators/mcp`, `npx @brightdata/mcp`, `apify-cli`, `twitch-cli`.
- Locale-only in V1, ma ingegnerizzato per Cloud Run (server MCP come container con transport HTTP),
  esattamente come la roadmap cloud di `stem-solver`.

---

## 10. Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| ToS/GDPR sullo scraping | Solo dati pubblici; rischio delegato agli upstream specializzati; provenienza tracciata (§1) |
| Costi che esplodono (run a pagamento) | `budget_guard` + `cost_estimate_usd` per tool; cache aggressiva; eval su mock |
| Rate-limit upstream (Apify 30 req/s) | Throttling per provider nel registry; backoff; fan-out limitato |
| Schema upstream che cambia | Normalizzazione isolata in un layer; fixture-test che falliscono al primo drift |
| Twitch senza endpoint "trends" | Derivato da Get Streams/Games + ScrapeCreators; aspettativa documentata (§3.4) |
| Freschezza dei dati | TTL corti per dati volatili; `freshness` come metrica di eval di prima classe |

---

## 11. Domande aperte (da chiudere prima della Fase 1)

1. **Repo di destinazione**: questo piano vive in `mcp-behavioral-prompts/docs/`. L'implementazione
   va qui (questo repo è uno scaffold MCP riutilizzabile) o in un repo nuovo dedicato?
2. **Quali API key sono già disponibili** (ScrapeCreators, Apify, Bright Data, Twitch app)? La
   Fase 2 si sblocca solo con la chiave ScrapeCreators.
3. **Paesi/piattaforme prioritari per V1** (il brief cita IT/DE, TikTok/IG/Twitch) — confermare lo
   scope per non costruire tool che non servono subito.
4. **Agente skill-based**: dentro V1 o rimandato a V2 come proposto qui?

---

### Fonti (verificate maggio 2026)

- Apify MCP — docs: <https://docs.apify.com/platform/integrations/mcp> ·
  Claude Desktop: <https://docs.apify.com/platform/integrations/claude-desktop> ·
  repo: <https://github.com/apify/apify-mcp-server> · endpoint: <https://mcp.apify.com>
- ScrapeCreators — docs: <https://docs.scrapecreators.com/> ·
  CLI: <https://github.com/ScrapeCreators/scrapecreators-cli> · sito: <https://scrapecreators.com/>
- Bright Data Web MCP — repo: <https://github.com/brightdata/brightdata-mcp> ·
  npm: <https://www.npmjs.com/package/@brightdata/mcp>
- Twitch CLI — docs: <https://dev.twitch.tv/docs/cli/> ·
  mock-api: <https://dev.twitch.tv/docs/cli/mock-api-command> ·
  repo: <https://github.com/twitchdev/twitch-cli>
