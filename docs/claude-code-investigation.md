# Claude Code — Analiza projekta `skill-financial-analyst`

**Datum:** 2026-07-17
**Obim:** Kompletna analiza svih 14 skripti (`scripts/*.py`, ~7900 linija) + 4 `.md` fajla.
**Cilj:** (1) Utvrditi šta svaka skripta radi i da li logika ispravno radi; (2) Proceniti da li bi pristup Interactive Brokers API-ju sa realnim podacima + L2 (dubina knjige naloga) pomogao.
**Metod:** Čitanje skripte po skripte + `py_compile` svih fajlova + empirijska demonstracija ROE/D-E bug-a sa realnim brojevima.

---

## Sadržaj
- [Rezime](#rezime)
- [Legenda ozbiljnosti](#legenda-ozbiljnosti)
- [Master lista bugova](#master-lista-bugova)
- [Sloj 1 — Infrastruktura](#sloj-1--infrastruktura)
- [Sloj 2 — Podaci](#sloj-2--podaci)
- [Sloj 3 — Analitički motori](#sloj-3--analitički-motori)
- [Sloj 4 — Kontekstni moduli](#sloj-4--kontekstni-moduli)
- [Sloj 5 — Workflow orkestratori](#sloj-5--workflow-orkestratori)
- [Poprečna rupa: free float / short interest](#poprečna-rupa-free-float--short-interest)
- [Relevantnost Interactive Brokers + L2](#relevantnost-interactive-brokers--l2)
- [Preporučen redosled ispravki](#preporučen-redosled-ispravki)

---

## Rezime

Projekat je **funkcionalan i arhitektonski zdrav** — sve skripte se kompajliraju bez sintaksnih grešaka, fallback lanci i keširanje su dobro osmišljeni, a rukovanje greškama je uglavnom graciozno. Ipak, postoji nekoliko **pravih bugova u kalibraciji i toku podataka** koji utiču na tačnost ocena i otpornost sistema.

Dva najozbiljnija (**ROE** i **Debt-to-Equity** u `scoring.py`) su **empirijski potvrđena**: najprofitabilnije velike kompanije (npr. AAPL sa ROE ~148%) dobijaju najgoru moguću ocenu za tu metriku.

Zajednički koren više bugova je **yfinance dvosmislenost "frakcija vs procenat"** (0.25 vs 25), koja se rešava krhkim `if`-heuristikama umesto poznavanjem šeme svakog polja.

**IB + L2 zaključak:** vrednost je **selektivna, ne univerzalna.** Projekat je pola cenovno/numerički (IB briljira, L2 dodaje potpuno novu sposobnost) i pola sentiment/alternativni podaci (IB nema veze). Najveća korist je u **portfolio review-u** (auto-import stvarnih pozicija i P&L-a) i **entry/exit-u** (stvarni zidovi likvidnosti iz L2 umesto S/R nagađanih sa grafikona).

---

## Legenda ozbiljnosti

| Oznaka | Značenje |
|--------|----------|
| 🔴 | Pravi bug — pogrešan rezultat ili tiho nefunkcionisanje |
| 🟡 | Bug/slabost umerenog uticaja — crash na ivici, degradacija, netačan prikaz |
| ⚪ | Kozmetički / mrtav kôd / nedoslednost sa dokumentacijom |

---

## Master lista bugova

| # | Skripta | Ozb. | Bug | Uticaj |
|---|---------|:----:|-----|--------|
| 1 | `scoring.py` | 🔴 | ROE `×100 if abs(roe)<1` greši za ROE>100% | AAPL/NVDA: 4/10 umesto 9/10 — **✅ ISPRAVLJENO** |
| 2 | `scoring.py` | 🔴 | D/E `if de>10` greši za nisko-zadužene firme | NVDA D/E 6.5 → 2/10 "ekstremno zadužen" — **✅ ISPRAVLJENO** |
| 3 | `technical_analysis.py` | 🟡 | MACD signal/histogram zamenjeni (positional `cols[1]`/`cols[2]`); `macd_bullish` ≡ `signal>0` umesto `line>signal` | Pogrešan crossover + zamenjen prikaz; ~0.19 kompozita — **✅ ISPRAVLJENO** |
| 4 | `data_fetchers.py` | 🟡 | Price fallback šupalj — samo yfinance vraćao DataFrame; polygon/AV/FMP nekompatibilni oblici | Nema tehnike kad yfinance padne — **✅ ISPRAVLJENO** |
| 5 | `macro_calendar.py` | 🔴 | Finnhub kalendar mrtav (`api_keys` vs `apis`); + hardkodovani datumi već približni; nema dedup/US-filter/precedence | Makro risk-flag-ovi nepouzdani, tiho degradiraju — **✅ Stage 1 ISPRAVLJENO** (Stage 2 za tačnost) |
| 6 | `data_fetchers.py` | 🟡 | `sec_edgar_filings` 2 mrtva poziva; + izmešten iz `fundamentals` (maskirao finnhub/fmp), pravi `document_url` | Trošenje poziva / lažna atribucija — **✅ ISPRAVLJENO** |
| 7 | `data_fetchers.py` | 🟡 | Hardkodovan UA email ignoriše config | SEC nema kontakt; UA sad iz config-a, baca ako nema — **✅ ISPRAVLJENO** |
| 8 | `data_fetchers.py` | 🟡 | `yfinance_analyst_ratings` čitao zastarelu šemu (firm/grade) | Prazne analitičar ocene bez Finnhub ključa — **✅ ISPRAVLJENO** |
| 9 | `data_fetchers.py` | 🟡 | AV rate-limit detekcija zastarela (`Information`) | Nejasna greška na limitu — **✅ ISPRAVLJENO** |
| 10 | `data_fetchers.py` | 🟡 | `yfinance_earnings`: mrtav `quarterly_earnings` fallback (sada `None`, ne crash) + `surprisePercent` frakcija tretirana kao procenat | Scoring `surprise_avg>5` nikad ne opali; nekonzistentno sa Finnhub — **✅ ISPRAVLJENO** |
| 11 | `entry_exit.py` | 🟡 | Sajzing = samo rizik-formula (nema capital/concentration/liquidity cap-a); izmišlja rizik na `stop>=entry`; string izlaz; pokvaren `.md` prikaz | Prikazivao poziciju od 500% računa — **✅ ISPRAVLJENO** |
| 12 | `run_portfolio_review.py` | 🟡 | `float()` u CSV parsiranju bez try/except | Loš broj ruši ceo review — **✅ ISPRAVLJENO** |
| 13 | `data_cache.py` | 🟡 | Formater čita drugu šemu ključeva nego producenti (tehnika, cena, R:R, insider, news, earnings, congress, dividends, TV) + `above_sma None→"Below"` (pogrešna tvrdnja) | Glavni `.md` artefakt prazan/netačan (ocene netaknute) — **✅ ISPRAVLJENO** |
| 14 | `data_cache.py` | 🟡 | `_fmt_pct` `abs<1` heuristika mis-scale | dividend_yield/ROE/payout do 100× pogrešni u `.md` — **✅ ISPRAVLJENO** |
| 15 | `technical_analysis.py` | ⚪ | `golden_cross`/`death_cross` su stanje, ne događaj | Duplira `above_sma`, pogrešan naziv |
| 16 | `api_config.py` | ⚪ | `enabled` flag se ignoriše | Dokumentacija govori da se postavi, kôd ne čita |
| 17 | `api_caller.py` | ⚪ | `time.sleep(delay)` pre svakog poziva, i prvog | Nepotrebno usporenje (AV 12s) |
| 18 | Poprečno | 🟡 | **Free float / short interest se nigde ne koristi** | Nema likvidnosnog/squeeze signala; sajzing ne zna float |
| 19 | `scoring.py` | 🔴 | Negativan P/B (`pb < 1`) boduje se 9/10 "deep value" | Negative-equity firma (FGMC −2075) dobija max fundamental — **✅ ISPRAVLJENO** |
| 20 | `scoring.py` | 🟡 | ROE bez gornjeg sanity capa (`>30 → 9/10`) | 1028% (artefakt negativnog imenioca) → 9/10 — **✅ ISPRAVLJENO** |
| 21 | `scoring.py` / `data_fetchers.py` | 🟡 | Nema SPAC / de-SPAC / insufficient-history detekcije | Fundamentals (PE/PB/ROE/margine) besmisleni za tek-spojene entitete |
| 22 | `data_cache.py` / `scoring.py` | ⚪ | FCF `-0.00B` + margin `0.0%` uz "negative" label | Prikaz/prag ivičnih vrednosti nedosledni |
| 23 | `run_deep_dive.py` | ⚪ | News link je Finnhub redirect (`finnhub.io/api/news?id=`), ne izvorni URL | Indirektni/ružni linkovi u KEY ARTICLES |

Detaljni opisi svih (uključujući sitnije nedoslednosti) slede po slojevima.

---

## Sloj 1 — Infrastruktura

### `api_config.py` — registar API-ja, ključevi, fallback lanci
**Uloga:** `API_REGISTRY` (14 API-ja sa tier/cost/rate-limit metapodacima), `FALLBACK_CHAINS`, učitavanje config-a, env-var overlay, provera dostupnosti.

- ⚪ **#16 — `enabled` flag se ignoriše.** `is_api_available()` proverava samo prisustvo ključa, ne i `enabled` polje. QUICKSTART govori korisniku da postavi `"enabled": true`, ali kôd to nikad ne čita. Nedoslednost dokumentacije i koda.
- ⚪ **`load_config()` env-var overlay za `secret_var`** radi `config["apis"].setdefault(...)` pretpostavljajući da `"apis"` ključ postoji. `init_config` ga uvek upiše, ali nije zaštićeno.
- ⚪ Rate-limit brojke su delom teorijske (npr. `polygon` 7200/day = 5/min×1440).

### `api_caller.py` — otporni pozivač sa fallback-om
**Uloga:** svaki poziv → proveri rate-limit → `time.sleep(delay)` → izvrši → loguj. `call_with_fallback` prolazi kroz lanac dok jedan ne uspe.

- ⚪ **#17 — `time.sleep(delay)` se izvršava pre SVAKOG poziva, uključujući prvi/jedini.** Za Alpha Vantage to je 12s čekanja i kad je to jedini poziv u satu. Bolje bi bilo pratiti vreme poslednjeg poziva po API-ju i spavati samo koliko preostaje do dozvoljenog intervala.
- Fallback logika i logovanje su korektni.

### `usage_tracker.py` — praćenje potrošnje, rate-limit, izveštaji
**Uloga:** thread-safe brojanje po danu/mesecu/minutu, JSONL log, dnevni izveštaji sa preporukama za plaćeni tier na >70%.

- 🟡 **Neuspeli pozivi se broje u kvotu.** `record_call` inkrementira dnevni/mesečni broj bez obzira na `success` → greške mogu lažno "potrošiti" AV-ovih 25/dan.
- ⚪ **Performanse:** u `print_daily_report`, `get_monthly_usage()` ponovo čita ceo log **za svaki** API sa mesečnim limitom (O(N×M)).
- ⚪ **Per-minutni prozor** (`_call_timestamps`) prati samo tekući proces (ne učitava se iz loga) — cross-process minutni limit se ne poštuje. U praksi OK za jedan run.

---

## Sloj 2 — Podaci

### `data_fetchers.py` — implementacije poziva za svih 14 izvora
- 🟡 **#6 — `sec_edgar_filings` pravi 2 bespotrebna HTTP poziva.** Prva dva zahteva (`r`, `r2`) se nikad ne koriste. (Ispravka ranije tvrdnje: `efts.sec.gov/LATEST/search-index` **postoji** i vraća JSON — backend EDGAR Full-Text Search-a — ali nije dokumentovan REST API i rezultat je ionako neiskorišćen.) **✅ ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki).
- 🟡 **#6a — Semantički mismatch + maskiranje:** `sec_edgar_filings` vraća listu filing-a (bez metrika), a bio registrovan pod `fundamentals` → na yfinance-padu "uspevao" i maskirao finnhub/fmp + davao lažni "✓". Uz to: nema 10-K/10-Q filtera (vraća sve forme), `primaryDocument` je samo ime fajla (ne URL). **✅ ISPRAVLJENO** (izmešten u `filings` kategoriju, dodat pravi `document_url`).
- 🟡 **#7 — Hardkodovan User-Agent** ignoriše config `user_agent_email`. SEC traži stvaran kontakt. **✅ ISPRAVLJENO** — UA se čita iz config-a (+env), baca `ValueError` ako nije podešen (bez placeholder-a); SEC je fallback pa `call_with_fallback` samo pređe dalje.
- 🔴 **NOVI nalaz (sibling #4): fundamentals fallback je nemapiran.** Samo `yfinance_fundamentals` emituje ključeve koje scoring čita; `finnhub_financials` (`{metrics}`) i `fmp_fundamentals` (`{profile}`) koriste svoje šeme → na yfinance-padu scoring dobija neutralne vrednosti bez obzira koji fallback "uspe". Ide uz #4 (normalizacija) — **zaseban visoko-prioritetan zadatak.**
- 🟡 **#8 — `yfinance_analyst_ratings` čita zastareo šema.** Traži `Firm`/`To Grade`/`Action`, ali moderni yfinance `.recommendations` vraća `[period, strongBuy, buy, hold, sell, strongSell]`. Rezultat: sva polja prazna. **✅ ISPRAVLJENO** (vidi Status ispravki).
- ⚪ **`sec_insider_trades` je pogrešno imenovan** — funkcija se zove "sec" ali zove Finnhub API.
- 🟡 **#9 — Alpha Vantage rate-limit detekcija zastarela.** AV sada vraća poruku pod ključem `"Information"`, a kôd gleda `"Note"`/`"Error Message"` → greška je nejasna ("Unknown"). Isto u `alpha_vantage_price_history` i `alpha_vantage_news_sentiment`.
- 🟡 **StockTwits API (`api.stocktwits.com/api/2`)** je danas uglavnom zaključan (403/429) → social_sentiment često pada iako je "bez ključa".
- 🟡 **#10 — `yfinance_earnings` koristi `t.quarterly_earnings`** koji je uklonjen u novijim verzijama yfinance → AttributeError u fallback grani.
- ⚪ **`yfinance_dividends`**: `divs.tail(8).to_dict()` daje Timestamp ključeve — potencijalni JSON serijalizacioni problem nizvodno (ublažen `default=str` u kešu).

### `rss_feeds.py` — katalog feed-ova + ekstrakcija tikera
- 🟡 **Ekstrakcija tikera je bučna po dizajnu.** Regex `\b[A-Z]{1,5}\b` + mala crna lista hvata sve velikim slovima (skraćenice, prve reči). Oslanja se na frekvenciju kroz izvore + kasniju yfinance validaciju u skeneru.
- 🟡 **Vremenska zona:** `datetime(*entry.published_parsed[:6])` je UTC, poredi se sa `datetime.now()` (lokalno). Kod granice `max_age_hours` može pogrešno uključiti/isključiti članke.
- ⚪ Nedatirani članci se uvek uključuju (`if pub_date and pub_date < cutoff` isključuje samo kad datum postoji).
- ⚪ Nedoslednost: dokumentacija kaže "20+/18 feed-ova", stvarno ih je 17.

### `data_cache.py` — keš (.md + .json po tikeru/danu)
Najbolje napisan fajl u projektu — atomičan rename JSON-a, kompresija DataFrame-ova, robusna serijalizacija (pandas/numpy). Ali:
- 🟡 **#14 — `_fmt_pct` heuristika `if abs(pct) < 1: pct *= 100` je opasna.** Mis-scale u OBA smera: već-procenat `dividendYield` (AAPL 0.32 → 32%) i vrednosti ≥1 (ROE 1.14 → 1.14%, payout 1.5 → 1.5%). **✅ ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki).
- 🟡 **#13 — Neslaganje ključeva fetcher/motor ↔ formater** (vidi [Status ispravki](#status-ispravki)). **✅ ISPRAVLJENO.**
- ⚪ **#22 — Formatiranje ivičnih vrednosti.** `Free Cash Flow $-0.00B` (negativno zaokruženo na −0.00B) i `Profit Margin 0.0%` uz label "Negative margins — losing money" (mali negativ zaokružen na 0.0% → prikaz i prag se ne slažu). Otkriveno na FGMC.

---

## Sloj 3 — Analitički motori

### `technical_analysis.py` — lokalni TA motor (pandas-ta + ručni fallback)
- 🟡 **#3 — MACD signal i histogram su ZAMENJENI kad se koristi `pandas-ta`.** `ta.macd()` vraća kolone `[MACD, MACDh (histogram), MACDs (signal)]`, ali kôd je dodeljivao `cols[1]→macd_signal`, `cols[2]→macd_histogram`. Posledica: `macd_bullish = line > macd_signal(=hist)` ≡ **`signal > 0`** umesto `line > signal` (crossover) → promašuje bearish-iznad-nule i bullish-ispod-nule. Ručni fallback je ISPRAVAN u dodeljivanju. Potvrđeno empirijski + iz instaliranog pandas-ta izvora + Codex CLI review. **✅ ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki).
- ⚪ **#15 — `golden_cross`/`death_cross` nisu "krstovi" nego trenutno stanje** (`sma_50 > sma_200`). Pravi zlatni krst je *presek* (skorašnji događaj). Ovako su samo negacija jedno drugog i dupliraju `above_sma`.
- ⚪ EMA koristi `adjust=True` (pandas default) umesto `adjust=False` → MACD se blago razlikuje od standardnog/TradingView.
- ⚪ Ručni RSI koristi prosto klizni prosek umesto Wilder smoothing-a → razlikuje se od pandas-ta RSI.
- ⚪ `compute_pivot_points` koristi `df.iloc[-2]` — pivoti su za dan pre poslednjeg, tj. jedan dan zastareli za EOD podatke.
- ⚪ **Dokumentacija precenjuje motor:** SKILL.md obećava Ichimoku, VWAP, Volume Profile, OBV, 6mo intraday — **ništa od toga nije implementirano** ovde.

### `scoring.py` — kompozitna ocena (40% fund / 30% tech / 30% sent)
- 🔴 **#1 — ROE bug za visok-ROE akcije.** `pct = roe*100 if abs(roe) < 1 else roe`. yfinance vraća ROE kao frakciju — AAPL ~`1.48` (148%). Pošto `abs(1.48) < 1` je False, ostaje `1.48` → tumači se kao **1.48% ROE** → ocena 4/10 "Low ROE — weak capital efficiency".

  **Empirijski potvrđeno:**
  ```
  ROE ulaz 1.48 (=148%) -> prikazano kao 1.5 | ocena 4/10 | 'Low ROE — weak capital efficiency'
  ```
- 🔴 **#2 — Debt-to-Equity bug za nisko-zadužene firme.** `de_ratio = de/100 if de>10 else de`. yfinance daje D/E kao procenat (×100). Firma sa D/E 0.08 → yfinance vrati `8` → nije `>10` → ostaje `8` → tumači se kao odnos 8.0 → ocena 2/10 "Extremely leveraged". Ispravno bi bilo **uvek** deliti sa 100.

  **Empirijski potvrđeno:**
  ```
  D/E ulaz 150 (=1.5) -> prikazano kao 1.5 | ocena 5/10 | 'High debt — elevated financial risk'   (OK)
  D/E ulaz 8   (=0.08) -> prikazano kao 8   | ocena 2/10 | 'Extremely leveraged'                    (BUG)
  ```
- 🔴 **#19 — Negativan P/B se boduje kao 9/10 "deep value" (`scoring.py:144`).** `if pb < 1:` hvata i negativne vrednosti; negativan P/B znači **negativan kapital** (negative shareholder equity / insolventnost), najgori mogući signal, a boduje se kao najbolji. Otkriveno na FGMC (de-SPAC): `PB −2075.0 → 9/10`. Diže fundamental score na osnovu smeća.
- 🟡 **#20 — ROE nema gornji sanity cap (`scoring.py:292`).** `pct > 30 → 9/10` bez granice; ROE od 1028% (FGMC) je artefakt **sićušnog/negativnog imenioca** (isti negative-equity koren kao #19), a dobija "Exceptional 9/10". Kombinovano sa #19: negative-equity entitet dobija **dva 9/10** iz iste pokvarene bilanse.
- 🟡 **#21 — Nema detekcije SPAC / de-SPAC / nedovoljne operativne istorije.** Ceo fundamental okvir (PE/PB/margine/ROE) je za operativne firme; za tek-spojeni entitet yfinance `.info` meša staru blank-check bilansu sa novom firmom → svi racia besmisleni. Sistem nema koncept "insufficient operating history → oslони se na tehniku/tok, obori fundamental confidence". Heuristika: naziv "Merger/Acquisition Corp", skok `sharesOutstanding`, IPO/merger datum < N meseci, negativan equity.
- ⚪ Heuristike frakcija-vs-procenat se ponavljaju svuda sa različitim pragovima (`<5`, `<1`, `>10`) — krhko; koren i dividend_yield problema.
- ⚪ `insider` se prosleđuje `_score_fundamental` ali se tamo nikad ne koristi (mrtav parametar); insider se koristi samo u sentiment faktoru.
- ⚪ `congress_trades` parsiranje: `isinstance(trades, list)` — ako Mboum vrati dict wrapper, tiho pada na neutralno 5.
- ✅ Dobro: `compute_quick_score` sa preraspodelom težina kad izvor nedostaje (ne vuče ka ravnih 5.0). Clamp 0-10, sektor modifikator ±0.5 — korektno.

### `entry_exit.py` — 3 ulaza / 3 izlaza / stop / R:R / sajzing
- 🟡 **#11 — Sajzing pozicije ignoriše kupovnu moć (i likvidnost).** `shares = int(max_loss / risk_per_share)` bez ograničenja na kapital → prikazivao poziciju od 500% računa bez upozorenja. **✅ ISPRAVLJENO** — `min(risk, capital, [concentration], [liquidity])`; capital cap (1× default) ubija 500%; ADV metrika iz `volume_avg_20`; `stop>=entry` više ne izmišlja rizik nego poništava sizing. Float ostaje za #18. Vidi [Status ispravki](#status-ispravki).
- ⚪ **Redosled operacija u računanju ulaza** (linije 171–173): `e_cons` se računa iz starog `e_mod`, pa se onda `e_mod` menja. Finalni `sorted(reverse=True)` garantuje opadajući redosled, ali ne i nameravan razmak/oznake (moderate/conservative se mogu zameniti).
- ⚪ **8% cap na stop se tiho gazi** pravilom "bar 1 ATR ispod conservative" — za volatilne akcije stvarni stop prelazi deklarisanih 8%.
- ✅ Dobro: zaštita od deljenja nulom u R:R, cap na 20x, `favorable = 2.0 ≤ rr ≤ 15.0`.

---

## Sloj 4 — Kontekstni moduli

### `macro_calendar.py` — earnings + ekonomski događaji + risk flags
- 🔴 **#5 — Finnhub kalendar je bio mrtav kôd** (`config.get("api_keys")` umesto `get_api_key("finnhub")`) → uvek prazno. **Dublje (iz adversarijalne revizije):** hardkodovani datumi su **već približni** (kôd sam kaže *"approximate"* za CPI), endpoint je **premium** (free tier → 403), i nedostajali su dedup, US filter i precedence. **✅ Stage 1 ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki). **Stage 2** (live BLS/Fed izvori za tačnost datuma) ostaje obavezan nastavak.
- ⚪ `earnings_dates` fallback poredi tz-aware indeks sa naivnim `datetime.now()` → TypeError koji se guta u `except` (primarni `calendar` put obično radi).

### `sector_rotation.py` — 11 sektorskih ETF-ova vs SPY
Najčistiji modul — batch download, relativna snaga po 1W/1M/3M, kompozit (0.4/0.35/0.25), modifikator ±0.5, in-memory keš 30 min. **Nema pravih bugova.**
- ⚪ 1W/1M/3M lookback je aproksimacija po broju trgovačkih dana — korektno za ovu vrstu signala.

---

## Sloj 5 — Workflow orkestratori

### `run_deep_dive.py` — Use Case 3 (flagship)
- 🟡 **#4 — Fallback lanac za cenu je bio kozmetički** — `compute_technicals` traži `price_data["data"]` kao DataFrame, a to je vraćao samo yfinance (polygon `results` lista, AV `time_series` dict, FMP `data` lista). Na yfinance-padu → `technicals=None`, tech_score 5.0, entry/exit grubi 2%-ATR. **✅ ISPRAVLJENO** — svi price fetcher-i sada vraćaju kanonski OHLCV DataFrame pod `"data"`. Vidi [Status ispravki](#status-ispravki). (Severity 🔴→🟡 per Codex: cena/current_price su preživljavali, degradirala se samo tehnika.)
- 🟡 **#13 — Neslaganje šeme ključeva u keširanom `.md`** (širi nego prvobitno procenjeno). `save_cache` dobija sirov fetcher/motor dict, a `_format_markdown` čita drugu šemu → prazno/N/A u tehnici (RSI/MACD/ATR/BB/S-R/Fibonacci), price zaglavlju, R:R (čitan sa pogrešnog mesta), insider, news, earnings, congress, dividends, TV oscilatorima. Dodatno `above_sma None→"Below"` je *pogrešna tvrdnja*, ne samo izostavljena. **Ocene NISU pogođene** (scoring/entry-exit čitaju sirov dict direktno). **✅ ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki).
- ⚪ **#23 — News link je Finnhub redirect, ne izvorni URL (`run_deep_dive.py:547`).** `a.get("url","")` iz Finnhub free-tier `company-news` vraća `finnhub.io/api/news?id=...` (302 redirect, radi u browseru ali nije pravi izvorni link). Nisko-prioritetno.
- ⚪ `_estimate_title_sentiment` koristi substring poklapanje → "miss" u "commission", "cut" u "prosecuted" → lažni bearish signali.
- ⚪ Mrtav kôd: `words = set(title.lower().split())` se izračuna a ne koristi; `_fmt_pct`/`_fmt_dollars` definisani a nigde pozvani.

### `run_daily_scanner.py` — Use Case 2
Solidan. `merge_candidates` sa rank-normalizacijom + bonusom za više izvora je pametan. StockTwits→ApeWisdom fallback radi. Filter kripto/šum razuman.
- ⚪ Nasleđena slabost: bučna ekstrakcija tikera (ublažena `count>=2` + cross-source).
- ⚪ `quick_screen` koristi period="3mo" → SMA200 nikad dostupan u brzom skeniranju (nema 200 barova).

### `run_portfolio_review.py` — Use Case 1 (najkompletniji)
Najbolje napisana workflow skripta — P&L-aware akcije, macro header, sektor izloženost, koncentracija upozorenja, deljeni formater za konzolu/markdown.
- 🟡 **#12 — `float(parts[1])` u CSV parsiranju nije u try/except** (i u header i no-header grani) → loše formatiran broj (npr. `$150.50`, slovo O umesto 0, `N/A`) ruši ceo review umesto graciozan skip. CLI grana **već ima** `try/except` — nedoslednost. **✅ ISPRAVLJENO** (vidi [Status ispravki](#status-ispravki)).
- ℹ️ Nasleđuje ROE/D-E bug iz scoring-a (prikazuje se u fundamentalnoj tabeli svake pozicije) i price→no-technicals gap.

---

## Poprečna rupa: free float / short interest

**#18 — Nijedna skripta ne uzima u obzir free float niti srodne metrike.** Potvrđeno pretragom — nedostaju:
- `floatShares`, `sharesOutstanding`, `impliedSharesOutstanding`
- `sharesShort`, `shortRatio`, `shortPercentOfFloat` (short interest / days-to-cover)
- `heldPercentInsiders`, `heldPercentInstitutions`

**yfinance ih sve već vraća u `.info`**, ali `yfinance_fundamentals()` ih ne čita. SKILL.md (Use Case 3, Phase C) *obećava* "short interest", ali kôd to ne implementira.

**Zašto je bitno:**
1. **Likvidnost / utrživost** — nizak float = tanka likvidnost, veći slippage, gap-ovi. Entry/exit iz ATR-a ne zna koliko je instrument utrživ.
2. **Position sizing (spaja se sa bug-om #11)** — za nisko-float akciju pozicija može biti ogroman % dnevnog volumena / float-a; ne proverava se nigde.
3. **Short squeeze signal potpuno odsutan** — `shortPercentOfFloat` + `shortRatio` su realan faktor koji sentiment blok uopšte ne meri.

**Gde bi se uključio:**
- `data_fetchers.py` → dodati 4-5 polja u `yfinance_fundamentals` (podatak već u `.info`).
- `scoring.py` → nizak float + visok short % = squeeze-faktor ili risk-flag.
- `entry_exit.py` → cap pozicije kao % od float-a / ADV-a; širi stop za nisko-float.
- `run_daily_scanner.py` → likvidnosni filter za odsecanje neutrživog microcap šuma.

---

## Relevantnost Interactive Brokers + L2

Projekat je pola **cenovno/numerički** (IB briljira) i pola **sentiment/alternativni podaci** (IB nema veze).

### Gde IB donosi veliku vrednost
| Oblast | Korist |
|--------|--------|
| **Portfolio review** | Auto-import stvarnih pozicija, realnog avg cost-a i live P&L direktno iz IB naloga (`reqPositions`/`reqAccountUpdates`). Nema više ručnog `TICKER:SHARES:AVG_COST`. Realna kupovna moć popravlja i sajzing-bug #11. **Najveća pojedinačna korist.** |
| **Entry/exit** | **L2 (`reqMktDepth`) daje STVARNE zidove likvidnosti** umesto S/R nagađanih sa grafikona. Potpuno nova sposobnost — kategorija `market_depth` sad ne postoji. |
| **Price / technicals** | Real-time barovi (`reqHistoricalData`/`reqMktData`) rešavaju fallback gap #4 i eliminišu yfinance 429 krhkost. IB/Reuters fundamentali dolaze kao čisti odnosi → **uklanja koren ROE/D-E bugova #1/#2**. |
| **Opcije** | Puni lanac sa grcima u real-time (bolje od yfinance). |

### Gde IB NE pomaže (pošteno rečeno)
- Reddit / StockTwits / Congress trades / RSS / quant analitičar ocene — IB ih nema.
- `macro_calendar` (ekonomski kalendar FOMC/CPI/NFP) — IB ne daje. Pravo rešenje je ispravka bug-a #5 ili namenski calendar API.
- `sector_rotation` — spor signal (nedeljni/mesečni), EOD dovoljno; L2 irelevantan.

### Uslovi
IB traži pokrenut **TWS/IB Gateway** + **plaćene market-data pretplate** (real-time L1 i L2 depth se naplaćuju po berzi). Zato IB ne zamenjuje besplatne izvore u celosti — zamenjuje/nadograđuje numeričku polovinu i dodaje L2.

---

## Preporučen redosled ispravki

Od najmanjeg (najniži rizik, najmanji zahvat) ka najvećem:

1. ~~**`run_portfolio_review.py`** — CSV `float()` u try/except (#12) 🟡~~ **✅ URAĐENO**
2. ~~**`data_cache.py`** — uskladiti ključeve fetcher/motor↔formater (#13) 🟡~~ **✅ URAĐENO**
3. ~~**`data_fetchers.py`** — ukloniti bespotrebne SEC pozive + koristiti config email + izmestiti u `filings` (#6, #7, #6a) 🟡~~ **✅ URAĐENO (opcija b)**
4. ~~**`entry_exit.py`** — cap sajzinga na kupovnu moć + ADV (#11) 🟡~~ **✅ URAĐENO** (float ostaje za #18)
5. ~~**`macro_calendar.py`** — `get_api_key` + precedence/coverage/observability (#5, Stage 1) 🔴~~ **✅ URAĐENO** (Stage 2 = live izvori, zaseban zadatak)
6. ~~**`technical_analysis.py`** — MACD kolone po imenu + validacija (#3) 🟡~~ **✅ URAĐENO** (fallback EMA/RSI accuracy = zaseban TA-task)
7. ~~**`data_fetchers.py`** — normalizovati sve price fetcher-e u zajednički DataFrame (#4) 🟡~~ **✅ URAĐENO**
8. ~~**`scoring.py`** — uvek `de/100` za Debt-to-Equity (#2) 🔴~~ **✅ URAĐENO**
9. ~~**`scoring.py`** — ispraviti ROE skaliranje (#1) 🔴~~ **✅ URAĐENO**

Paralelno / kao zasebne crte:
- **#18 (free float + short interest)** — likvidnosne/squeeze metrike + sajzing na % float/ADV.
- **Fundamental-enrichment** (zaseban zadatak, *odvojen* od #18) — dohvatiti valuation polja koja formater prikazuje ali `yfinance_fundamentals` ne dohvata: `enterpriseToEbitda`, `pegRatio`, `currentRatio`, `totalCash`, `totalDebt`, `forwardEps`. Sve postoji u yfinance `.info`.
- **Fundamentals fallback normalizacija** (sibling #4, visok prioritet) — mapirati `finnhub_financials` (`{metrics}`) i `fmp_fundamentals` (`{profile}`) na scoring šemu (`pe_ratio`, `revenue_growth`, `roe`...), da fallback posle yfinance-pada zaista hrani scoring, a ne neutralne vrednosti.
- **Ožičavanje `filings` kategorije** (odloženi deo opcije (a) iz #6a) — dodati fetch+prikaz filing-a u `run_deep_dive`, `is_api_available("sec_edgar") → NEEDS CONTACT` kad email nije podešen. Do tada je `filings` definisan ali nepozvan.
- **Macro calendar Stage 2** (obavezan nastavak #5 — Stage 1 ne popravlja netačne fallback datume) — live zvanični izvori redom: BLS ICS (CPI/Employment, sa cache + fixture test), Fed FOMC parser (last-known-good cache), holiday-aware OPEX generator, BEA GDP/PCE. FRED preskočiti dok ne zatreba.
- **TA-accuracy** (zaseban zadatak, iz #3 revizije) — uskladiti ručni fallback EMA sa pandas-ta (`presma`/SMA-seed + `talib=False`, warm-up semantika) i ručni RSI na Wilder smoothing umesto rolling mean. Bez toga fallback grana (bez pandas-ta) daje blago nestandardne vrednosti.
- **IB/L2 integracija** — veća nadogradnja (novi `ibkr` fetcher, `market_depth` kategorija, auto-import portfolija).

---

## Status ispravki

### ✅ Bug #12 — CSV parsiranje pada na neispravnom broju (2026-07-17)

**Rešenje:** uveden zajednički helper `_parse_number()` u `run_portfolio_review.py`, primenjen na sve tri putanje učitavanja (CSV sa header-om, CSV bez header-a, CLI `TICKER:SHARES:AVG_COST`). Zamenjuje 4 nezaštićena `float()` poziva.

Helper:
- strip-uje `$`, zareze-hiljade i razmake;
- tretira sentinele `N/A`/`NA`/`NULL`/`-`/`—` kao "nedostaje" (vraća `None`);
- odbacuje `inf`/`nan` preko `math.isfinite()` (jer ih `float()` tiho prihvata i truju nizvodne račune);
- baca `ValueError` samo na stvarno pokvaren ulaz (`1O0`), pa pozivalac razlikuje "nije uneto" od "smeće".

Pozivna mesta: `try/except (TypeError, ValueError)` → graciozan skip **samo tog reda** (uz upozorenje), plus validacija `shares > 0 and avg_cost > 0`. CLI zadržava fail-fast (`sys.exit`) jer je ručni unos.

**Ograničenje (svesno, dokumentovano):** zarez kao separator hiljada radi samo u *navodnicima* (`"485,000"`); neuokviren `485,000` CSV modul razbije na kolone pre parsiranja.

**Verifikacija:** `tests/test_csv_parsing.py` — **22/22 PASS**. Matrica: validan broj, `$150.50`, `N/A`, `1O0`, `nan`, `inf`, negativno, nula, i loš red između dva validna reda (potvrđeno da se preskače samo taj red, review se ne ruši). Pokretanje: `.venv/bin/python tests/test_csv_parsing.py`.

Izmenjeni fajlovi: `scripts/run_portfolio_review.py` (+`_parse_number`, 3 putanje), `tests/test_csv_parsing.py` (nov).

### ✅ Bug #13 — Formater keširanog `.md` čita pogrešnu šemu ključeva (2026-07-17)

**Obim (širi nego prvobitno):** ne samo tehnika i cena, nego i R:R (čitan iz pogrešnog mesta — top-level polje, trostruko pogrešno: lokacija, ključ kombinacija, i `ratio` umesto `rr_ratio`), insider (i container i polja po redu), news, earnings, congress, dividends, TV oscilatori (velika vs mala slova), i `above_sma None→"Below"` (pogrešna tvrdnja).

**Rešenje (Opcija A — presentation adapteri, jedan fajl, bez uticaja na scoring):**
- Dodati `_normalize_technical_view()` i `_normalize_price_view()` — mapiraju sirove ključeve (`rsi_14`→`rsi`, `macd_line`→`macd`, `atr_14`→`atr`, `bb_mid`→`bb_middle`, `bb_position`→`%B` (0–1 odnos), `support_resistance`→supports/resistances, `fibonacci`→retracements/extensions). Price view izračunava `previous_close`/`daily_change`/`avg_volume` iz OHLCV df-a (uz guard za df<2 reda / NaN / ne-df fallback), a 52-nedeljni iz `fundamentals` ili df-a.
- Tri-state helperi `_above_below`/`_yes_no`: `None → "N/A"` (ne lažno "Below"/"No").
- **Uklonjen** `volume_trend` (ne izmišlja se iz `volume_ratio` — odnos ≠ trend); umesto toga prikaz `volume_latest` + `volume_avg_20`.
- Dodat **raw Technical JSON blok** kao sigurnosna mreža (jedina sekcija bez njega).
- R:R čitan sa `ee["risk_reward"]` (obrazac iz `run_portfolio_review`), prikaz najboljih favorable kombinacija.
- Ključevi usklađeni: insider (`recent_transactions` + Finnhub polja `filingDate`/`transactionCode`/`share`/`transactionPrice`), news (`avg_sentiment`→label), earnings (`earnings` lista), congress (`congress_trades`), dividends (`dividend_rate`), TV oscilatori (mala slova).

**Ograničenje:** neprikupljena valuation polja (`ev_to_ebitda`, `peg_ratio`, `current_ratio`, `total_cash`, `total_debt`, `eps_ttm/forward`) ostaju N/A — prebačeno u zaseban **Fundamental-enrichment** zadatak (vidi Preporučen redosled).

**Verifikacija:** `tests/test_markdown_formatter.py` — **23/23 PASS**, koristi *stvarni* `compute_technicals()` + `compute_entry_exit()` izlaz (hvata budući schema drift), uključujući kratku istoriju (60 redova) gde `above_sma200` mora biti "N/A", ne "Below". #12 regresija i dalje 22/22. Pokretanje: `.venv/bin/python tests/test_markdown_formatter.py`.

Izmenjeni fajlovi: `scripts/data_cache.py` (+4 adaptera/helpera, ~10 sekcija formatera), `tests/test_markdown_formatter.py` (nov).

### ✅ Bugovi #6 / #7 / #6a — `sec_edgar_filings` cleanup + izmeštanje (opcija b) (2026-07-18)

**Rešenje (opcija b — funkcija čista/spremna, ali NE ožičena u workflow):**
- Obrisani mrtvi pozivi `r`, `r2` → funkcija sada pravi **2 HTTP poziva umesto 4** (a posle prvog, ticker mapa je keširana → svaki naredni tiker = 1 poziv).
- `_sec_user_agent()` — čita `apis.sec_edgar.user_agent_email` (+`SEC_EDGAR_USER_AGENT_EMAIL` env), sa `(... or "").strip()` (ne pada na `null`); **baca `ValueError`** ako kontakt nije podešen (bez placeholder-a — SEC je fallback, `call_with_fallback` samo pređe dalje).
- `_sec_ticker_map()` sa `@lru_cache(maxsize=1)` — rešava amplifikaciju preuzimanja `company_tickers.json` (~1MB) pri korelisanom yfinance padu (npr. portfolio od 20 pozicija).
- Pravi `document_url` (`edgar/data/{int(cik)}/{accession_bez_crtica}/{primaryDocument}`) + čuva `primary_document`, uz guard na dužine paralelnih nizova.
- **Izmešten iz `fundamentals`** (`get_fetchers` + `FALLBACK_CHAINS`) u novu **`filings`** kategoriju → prestaje maskiranje finnhub/fmp i lažna atribucija. `fundamentals` lanac je sad `[yfinance, finnhub, fmp]`.

**Korekcija ranije tvrdnje:** EFTS endpoint `efts.sec.gov/LATEST/search-index` **postoji** (backend EDGAR FTS-a) — ranije netačno nazvan "nepostojećim". Bitno je samo da je rezultat bio neiskorišćen.

**Nije rađeno (svesno, opcija b):** ožičavanje `filings` u `run_deep_dive`, `is_api_available → NEEDS CONTACT`, i finnhub/fmp fundamentals normalizacija — sve prebačeno u zasebne zadatke (vidi Preporučen redosled).

**Verifikacija:** `tests/test_sec_edgar.py` — **14/14 PASS** (mock, bez mreže): 2-poziva-umesto-4 + keširanje, UA nosi konfigurisan email, missing/`null` email → `ValueError` bez HTTP poziva, `document_url` konstrukcija, i registarsko ožičenje (`sec_edgar` van `fundamentals`, u `filings`). Regresije #12 (22/22) i #13 (23/23) prolaze.

Izmenjeni fajlovi: `scripts/data_fetchers.py` (+`_sec_user_agent`/`_sec_ticker_map`, rewrite `sec_edgar_filings`, `get_fetchers`), `scripts/api_config.py` (`FALLBACK_CHAINS`), `tests/test_sec_edgar.py` (nov).

### ✅ Bug #11 — Position sizing: multi-constraint model (2026-07-18)

**Rešenje:** `_compute_position_sizes` prepravljen sa čiste rizik-formule na **`min(risk, capital, [concentration], [liquidity])`** po ilustrativnom scenariju računa.
- **capital cap** (`floor(account × leverage_multiplier / entry)`, `leverage_multiplier=1.0` default = cash, uvek ON) → **ubija 500% bug**.
- **risk** i **capital** su MANDATORY: ako se rizik ne može proceniti (`stop >= entry`), sizing te ćelije se **poništava** (`shares=None`, `sizing_evaluated=False`, warning) umesto ranije izmišljene `entry*0.02` rizik-vrednosti.
- **concentration** (`max_position_fraction`, OFF po defaultu) i **liquidity** (`max_adv_participation_fraction`, hard cap samo ako je zadat) su OPCIONI. ADV = `technicals["volume_avg_20"]` (već lokalno).
- **`position_pct_of_adv`** računa se iz **konačnih** (post-cap) akcija; `adv_metrics_evaluated=False` ako ADV nedostaje.
- **Jedinice pinovane** (istorija fraction/percent bugova #1/#2/#14): `max_position_fraction`/`max_adv_participation_fraction` su **frakcije (0,1]** (25 → `ValueError`); `risk_pct` ostaje procenat radi legacy kompatibilnosti, odmah normalizovan. Izlaz `*_pct` = ljudski procenti.
- Izlaz su **brojevi** (ne stringovi): `shares, notional, portfolio_pct, risk_budget, planned_loss_at_stop, binding_constraints, constraints{shares,evaluated}, position_pct_of_adv`.
- **`data_cache` prikaz** popravljen (dvonivojska `{entry:{account:leaf}}` struktura + oznaka o ilustrativnom scenariju) — usput rešen i deo #13.

**Dizajn-odluke (iz adversarijalne revizije):** capital cap ≠ „buying power" (nema veze sa brokerom) → naziv/oznaka „illustrative standalone scenario"; nema univerzalnog ADV/concentration default-a (Flash Crash logika) → OFF/not_evaluated osim ako je konfigurisano; `stop` ne garantuje `max_loss` → `planned_loss_at_stop`. Float odložen za ceo #18 (float% sam je slab signal). Naziv multiplier-a `leverage_multiplier` (jasnije od `gross_exposure`, koji je portfolio-nivo termin).

**Verifikacija:** `tests/test_position_sizing.py` — **31/31 PASS**: capital-limited (500%→100%), risk-limited, concentration-limited, `stop>=entry`→`None` (ne capital-only), jedinice (`0.25` OK / `25`→`ValueError`), tie→oba u `binding`, ADV metrika samo uz konačan pozitivan ADV, `portfolio_pct` nikad > 100%×leverage. Regresije #12/#13/#6-7 sve prolaze.

Izmenjeni fajlovi: `scripts/entry_exit.py` (rewrite `_compute_position_sizes` + `_size_one`, params na `compute_entry_exit`), `scripts/data_cache.py` (prikaz), `tests/test_position_sizing.py` (nov).

### ✅ Bug #5 — Macro calendar Stage 1: containment + observability + Finnhub correctness (2026-07-18)

**Podela (dogovorena adversarijalno):** Stage 1 = *containment/observability/Finnhub correctness*; **ne** tvrdi da rešava tačnost free kalendara — to je Stage 2 (live izvori). Ključni uvid: dijagnoza (hardkodovani datumi već pogrešni) je *free-path* problem; ispravka ključa pomaže samo *paid* korisnicima.

**Stage 1 (urađeno):**
- **Ključ:** `get_api_key("finnhub", config)` umesto `config.get("api_keys")`; docstring jasno kaže da je Economic Calendar **premium**.
- **`_fetch_finnhub_calendar` → strukturiran rezultat** (`attempted/success/http_status/error_class/coverage_*`), ne bare lista — razlikuje "pokriveno, nema događaja" od auth/premium/rate-limit/network.
- **impact mapiranje** (`low/medium/high` + numeričko), **US country filter**, **HTTP klasifikacija** (401 auth / 403 premium / 429 rate_limit / 5xx provider).
- **Source-level precedence PRE exact dedup** — uspešan Finnhub pokriva makro (FOMC/CPI/JOBS) → **potiskuje** približne fallback događaje tih kategorija (revidiran live CPI zamenjuje pogrešan fallback, ne oba); **OPEX** ostaje iz fallback-a (Finnhub ga ne prati).
- **Coverage semantika:** eksplicitni `coverage_start/end` po izvoru (ne `max(event.date)`); warning kad `coverage_end < cutoff` (pokrivenost celog prozora, ne "posle poslednjeg datuma").
- **Hardkodovani događaji programski označeni** `source="hardcoded_fallback"`, `date_confidence="APPROXIMATE"` (odvojeno od `impact`); risk-flag kaže *"approximate fallback date; live calendar unavailable"*.
- **Observability:** jedna soft napomena po summary-ju na neuspeh (klasifikovan); `format` razlikuje *"coverage is complete"* od *"INCOMPLETE"*. `success + prazna lista = pokriveno` (≠ 403/network).

**Ne rađeno (svesno):** ručno "krpljenje" hardkodovanih datuma (pravi novu stale listu); tačnost dolazi iz Stage 2 live izvora.

**Verifikacija:** `tests/test_macro_calendar.py` — **28/28 PASS**, uključujući **kritični test** (live CPI revidiran datum + fallback drugi datum → samo live CPI ostaje, fallback CPI potisnut, OPEX zadržan). Sve regresije (#12/#13/#6-7/#11) prolaze.

Izmenjeni fajlovi: `scripts/macro_calendar.py` (helperi + rewrite `_fetch_finnhub_calendar`/`get_economic_events`/`get_macro_summary`/`format_macro_summary`), `tests/test_macro_calendar.py` (nov).

### ✅ Bug #3 — MACD signal/histogram swap (2026-07-18)

**Potvrda (tri sloja):** empirijski (`.venv` pandas-ta 0.4.71b0: kolone `MACD, MACDh, MACDs`; kôd čita `cols[1]`=histogram kao signal, `cols[2]`=signal kao histogram); iz **instaliranog izvora** (`pandas_ta/momentum/macd.py` dodaje `macd, histogram, signalma` tim redom; `ema.py` `presma=True`/TA-Lib); i **Codex CLI** review (CONFIRM ×5, "FIX PLAN: SOUND").

**Rešenje:**
- **Selekcija kolona po IMENU** (token `MACD`/`MACDh`/`MACDs`), ne po poziciji; **validacija** da su sve tri prisutne — na schema drift **ne** mapira tiho nego prijavi warning + postavi tri polja na `None`.
- **Ručna fallback grana netaknuta** — `ewm(adjust=False)` ne reprodukuje pandas-ta SMA-seeded/TA-Lib EMA, pa poravnanje grana i RSI Wilder idu u zaseban **TA-accuracy** zadatak.
- Severity **🔴→🟡**: MACD je 1 od 8 ravnopravnih tehničkih faktora; najgori swing faktora (3↔8) menja tech-score ~0.625, kompozit ~0.19 (30% težine). Kvari crossover i prikaz, ali sam ne dominira kompozitom.

**Verifikacija:** `tests/test_macd.py` — **12/12 PASS**: histogram-invarijanta (tolerantno `abs_tol=2e-4` zbog `_safe_last` zaokruživanja), `macd_bullish == line>signal`, **shuffle kolona → mapiranje po imenu drži**, **crossover ispod/iznad nule** (slučajevi koje je swap grešio), i missing-column → `None` bez rušenja. Sve regresije (#12/#13/#6-7/#11/#5) prolaze.

Izmenjeni fajlovi: `scripts/technical_analysis.py` (MACD blok), `tests/test_macd.py` (nov).

### ✅ Bugovi #1 / #2 — ROE / Debt-to-Equity jedinice (2026-07-18)

**Osnova — živa yfinance mapa jedinica** (povučeno iz `.info`: AAPL/NVDA/KO/O/JPM/MNST): rate/margin/growth polja su **frakcije** (`0.27`=27%); `debtToEquity` je **procenat odnosa** (`79.5`=0.795x); `dividendYield` je **već procenat** (`0.32`=0.32%).

**Smoking gun (živi):** `NVDA debtToEquity=6.555` → stari `de/100 if de>10` → `6.555>10` False → ostaje 6.555 → **2/10 "extremely leveraged"**; stvarni odnos je 0.066 (skoro bez duga). `NVDA returnOnEquity=1.14` → stari `abs<1` False → čita 1.14% → 4/10. Bug pogađa prave, istaknute firme.

**Rešenje:** eksplicitni konverteri bez heuristika — `_pct(frac)=frac*100` (ROE, revenueGrowth, earningsGrowth, profit/operating margins) i `_de_ratio(de)=de/100` (debtToEquity). **Behavior-preserving** za normalne firme (KO ROE 0.43→43, AAPL D/E 79.5→0.795 nepromenjeno); menja se samo mis-scored ivica (ROE≥100%, D/E reported ≤10, growth-frakcija ≥5).

**Obim (odvojeno):** `dividendYield` je suprotan slučaj (već procenat, NE ×100) → to je **#14** u display sloju (`data_cache._fmt_pct`), zaseban. Finnhub/FMP fundamentals koriste svoje jedinice i nisu normalizovani → **fundamentals-fallback normalizacija** zaseban zadatak; scoring u praksi vidi samo yfinance šemu, pa je fix na yfinance konvenciju ispravan.

**Codex CLI review** (log: `docs/codex-review/01-02-fundamental-units.md`): A/B/C sve CONFIRM; preporuka — dokumentovati/testirati granicu "važi dok scoring dobija yfinance šemu" (uneto u komentar helpera + testove).

**Verifikacija:** `tests/test_fundamental_units.py` — **18/18 PASS** sa stvarnim yfinance vrednostima (NVDA/AAPL/KO/MNST): edge fix + očuvanje ponašanja. Sve regresije prolaze.

Izmenjeni fajlovi: `scripts/scoring.py` (`_pct`/`_de_ratio` + 7 polja u `_score_fundamental`/`compute_quick_score`), `tests/test_fundamental_units.py` (nov).

### ✅ Bug #4 — Price fallback: kanonski OHLCV DataFrame (2026-07-18)

**Problem:** samo `yfinance` je vraćao `"data"` kao DataFrame; `polygon` (`results` lista), `alpha_vantage` (`time_series` dict), `fmp` (`data` lista) — nekompatibilni oblici. Na yfinance-padu `price_data.get("data")` je None/lista → `compute_technicals` pukne → `technicals=None` (tech_score 5.0, entry/exit 2%-ATR). "Otporni" lanac je bio kozmetički za tehniku.

**Rešenje:** svi price fetcher-i vraćaju **kanonski OHLCV DataFrame** pod `"data"` (`Open/High/Low/Close/Volume`, rastući `DatetimeIndex`) preko `_rows_to_ohlcv` (numeric coerce, dropna OHLC, `Volume.fillna(0)`, sort ascending, dedup datuma, **raise ako <2 reda** da fallback nastavi) + `_price_result` (`latest_close/volume` iz df-a). polygon `t`=epoch-ms; AV prefiksni string ključevi (+ dodato `Information` u rate-limit detekciju → delom rešava #9); FMP newest-first (sort ispravlja). yfinance netaknut. Nijedan drugi kôd nije konzumirao stare raw payload-e.

**Severity 🔴→🟡** (Codex): cena/current_price su preživljavali, degradirala se samo tehnika. AV `compact`=100 redova → SMA200 nedostupan na AV fallback-u (dokumentovana degradacija).

**Codex CLI review** (log: `docs/codex-review/04-price-fallback.md`, kroz fajl u 2 iteracije): CONFIRM pravca + dorade (severity, raw-payload, robustnost, gotchas), pa finalni **`SOUND`** (pozvan u pozadini da ne blokira).

**Verifikacija:** `tests/test_price_normalization.py` — **19/19 PASS**: svaki provajder → kanonski DataFrame, rastući indeks, `latest_close`=najnoviji, `compute_technicals` radi, garbage payload baca (fallback nastavlja). Sve regresije prolaze.

Izmenjeni fajlovi: `scripts/data_fetchers.py` (`_rows_to_ohlcv`/`_price_result` + polygon/AV/FMP), `tests/test_price_normalization.py` (nov).

### ✅ Bug #8 — yfinance analyst ratings zastarela šema (2026-07-18)

**Osnova — živa yfinance šema:** `.recommendations` je sada **agregirani brojevi** (kolone `period/strongBuy/buy/hold/sell/strongSell`, red `0m` = tekući); stari firm/grade/action prešli u `.upgrades_downgrades`. Stari fetcher (`.iloc[-1].get("Firm")`) → sve prazno + `total=rowcount` = smeće. Fallback za `analyst_ratings` posle finnhub → korisnici bez Finnhub ključa dobijali praznu analitičar ocenu.

**Rešenje:** vraća **istu count-šemu kao finnhub** (`buy/hold/sell/strong_buy/strong_sell/period/num_analysts`) → scoring radi, prikaz konzistentan. `_format_analyst_line` (yfinance grana) sada prikazuje brojeve. Update `data_sources`… n/a.

**Codex CLI review** (log: `docs/codex-review/08-*.md`, po AGENTS.md protokolu, `--sandbox read-only`): **CHANGES_REQUIRED → prihvaćeno → AGREED**. Dorade: (1) `0m` red se bira **eksplicitno** (`recs["period"].eq("0m")`, raise ako nije tačno jedan), ne `iloc[0]`; (2) counts-only; (3) 🟡; robusna koercija (`pd.to_numeric(coerce)`, **raise** na missing/negativno/ne-celobrojno — bez tihe nule da se schema break ne sakrije); sačuvan `period`.

**Verifikacija:** `tests/test_analyst_ratings.py` — **16/16 PASS** (`0m` nije prvi red, numpy brojevi, NaN/negativno/ne-celobrojno/nula → raise, schema break, formater). Sve regresije prolaze.

Izmenjeni fajlovi: `scripts/data_fetchers.py` (`yfinance_analyst_ratings`), `scripts/run_deep_dive.py` (`_format_analyst_line`), `tests/test_analyst_ratings.py` (nov), `tests/test_enhanced_report.py` (postojeći analyst-line test ažuriran na count-šemu — regres uhvaćen punim regresionim prolazom tokom #9 review-a).

### ✅ Bug #9 — Alpha Vantage rate-limit detekcija (2026-07-18)

**Problem:** AV vraća HTTP 200 i kad je throttlovan, sa razlogom u telu. Trenutni daily-limit je pod ključem **`Information`**; `alpha_vantage_price_history` je to već hvatao (#4), ali `alpha_vantage_news_sentiment` nije → na limitu prijavljivao `"Unknown"` (i pozivalac nije mogao da razlikuje "rate-limited" od "nema podataka").

**Rešenje:** zajednički helper `_av_error(data)` (prioritet `Information` > `Note` > `Error Message`), korišćen u oba AV fetcher-a.

**Codex CLI review** (log: `docs/codex-review/09-av-rate-limit.md`, `--sandbox read-only`): kôd sound; **CHANGES_REQUIRED → AGREED** — Codex je (po protokolu) tražio pun regresioni prolaz, koji je **uhvatio regres iz #8** (`test_enhanced_report` analyst-line test na staroj firm/grade šemi), sada ispravljen.

**Verifikacija:** `tests/test_av_error.py` — **9/9 PASS**; pun regresioni prolaz zelen.

Izmenjeni fajlovi: `scripts/data_fetchers.py` (`_av_error` + oba AV fetcher-a), `tests/test_av_error.py` (nov).

### ✅ Bug #10 — yfinance earnings šema + surprise jedinica (2026-07-18)

**Dva nalaza (živa yfinance šema):** (1) `.quarterly_earnings` sada vraća **`None`** (deprecation, ne AttributeError) → fallback grana mrtva ali bezbedna → uklonjena. (2) **Novo:** `.earnings_history` `surprisePercent` je **frakcija** (`0.0346` = 3.46%); stari kôd ga je prosleđivao kao procenat → `surprise_avg ≈ 0.03` → scoring `surprise_avg > 5` **nikad ne opali**, i nekonzistentno sa `finnhub_earnings` (koji daje procenat).

**Rešenje:** surprise% se **računa iz actual/estimate** (`(a-e)/abs(e)*100`, procenat, konzistentno sa Finnhub-om i scoring pragom), sa `pd.to_numeric`/`pd.notna` zaštitom (NaN/None/0 estimate → `None`, bez deljenja nulom). Uklonjen `quarterly_earnings` fallback. Čuvaju se čisti float/None.

**Codex CLI review** (log: `docs/codex-review/10-*.md`, `--sandbox read-only`): runda 1 **CLARIFY** (read-only sandbox blokirao Codex-ovo čitanje repo-a → dao inventar konzumenata inline), runda 2 **AGREED** — svi konzumenti `surprise_avg` očekuju procenat; nijedan ne traži frakciju. Pre-postojeći per-kvartal display key-mismatch (`surprise_pct` vs `surprisePercent`) ostaje zasebno skopiran (#13-class).

**Verifikacija:** `tests/test_yf_earnings.py` — **12/12 PASS** (procenat skala, beat/miss, numpy dtypes, NaN/0/None → `None`, empty → ValueError, `quarterly_earnings` se ne dira); pun regresioni prolaz zelen.

Izmenjeni fajlovi: `scripts/data_fetchers.py` (`yfinance_earnings`), `tests/test_yf_earnings.py` (nov).

### ✅ Bug #14 — `_fmt_pct` mis-scale + moderni yfinance jedinice/šema kontrakt (2026-07-18)

**Problem:** display helper `_fmt_pct` je pogađao jedinice po magnitudi (`if abs(pct)<1: pct*=100`) → mis-scale u **oba** smera na glavnom `.md`: već-procenat `dividendYield` (AAPL 0.32 → prikazano **32%**), i vrednosti ≥1 koje nisu skalirane (ROE 1.14288 → **1.14%**, payout 1.5 → **1.5%**). Isti frakcija/procenat problem kao #1/#2, samo u prikaznom sloju.

**Rešenje (Codex-AGREED opcija A — eksplicitan kontrakt, bez heuristike):**
- `_fmt_pct(frac)` → **uvek** `frac*100` (svaki caller je frakcija: revenueGrowth/earningsGrowth/profit-operating margins/ROE/ROA/payoutRatio). Novi `_fmt_pct_value(val)` → već-procenat, **neskalirano**, samo za `dividend_yield`. (Split je bio implementiran pre dogovora; zadržan.)
- **`requirements.txt`** floor podignut `yfinance>=0.2.36` → **`yfinance>=1.5.1`** — kôd ionako *već* hard-zahteva modernu šemu (#8 `.recommendations` agregat baca bez `period`; #10 konzumira `.earnings_history`), pa je stari floor lažno opisivao granicu kompatibilnosti. Value-based detekcija odbačena (2.6% je `0.026` frakcija ili `2.6` procenat — opsezi se preklapaju).
- **`data_fetchers.py`** — dodat "yfinance schema/units contract (producer boundary)" note u module docstring: agregirane recommendations, `.earnings_history`, `.info` rate/margin/growth/ROE/payout su FRAKCIJE, `dividendYield` je VEĆ PROCENAT; nizvodni `_fmt_pct` (×100) vs `_fmt_pct_value` (neskalirano) oslonac; stare verzije nepodržane.

**Codex CLI review** (log: `docs/codex-review/14-fmt-pct-units.md`, 5 poruka): runda 1 CHANGES_REQUIRED (verzija-kontrakt gap: `>=0.2.36` dozvoljava stari fraction-`dividendYield` install), runda 2 posle dokaza da je stari yfinance već slomljen drugde → **AGREED** na opciju A. Severity **⚪→🟡** (odluka-relevantni report brojevi do 100× pogrešni, ali bez uticaja na scoring-putanju).

**Verifikacija:** `tests/test_fmt_pct.py` — **11/11 PASS** (`_fmt_pct` fraction/high-ROE/payout>1/negative/None; `_fmt_pct_value` 2.6→2.60%, 0.32→0.32%; dividends integracija 2.60% + payout 64.80%, nema 260% mis-scale). Pun regresioni prolaz — **14/14 fajlova zeleno** (analyst_ratings 16, av_error 9, csv_parsing 22, enhanced_report 11, fmt_pct 11, fundamental_units 18, macd 12, macro_calendar 28, markdown_formatter 23, position_sizing 31, price_normalization 19, sec_edgar 14, yf_earnings 12, skill 21/24+3 skip), nula padova.

Izmenjeni fajlovi: `requirements.txt`, `scripts/data_fetchers.py` (module-docstring kontrakt), `tests/test_fmt_pct.py` (label). `scripts/data_cache.py` (`_fmt_pct`/`_fmt_pct_value` split) — landiran ranije.

### ✅ Bugovi #19 / #20 — Negative-equity denominator (P/B + ROE) (2026-07-18)

**Otkriveno na realnom runu** `run_deep_dive.py FGMC` (FG Merger II Corp — de-SPAC, spojen sa BOXABL): negative-equity entitet dobijao **dva 9/10** iz iste pokvarene bilanse — `PB −2075 → 9/10 "deep value"` i `ROE 1028% → 9/10 "exceptional"` → fundamental veštački naduvan (4.6/10).

**Koren:** cena je uvek > 0, pa `priceToBook <= 0 ⇔ shareholder equity < 0` (insolventnost / post-merger degeneracija). Isti negativan equity razbija i P/B (#19) i ROE = NetIncome/Equity (#20).

**Rešenje (Codex-AGREED, jedan guard za oba):**
- **#19 P/B** (`scoring.py`): grana `if pb <= 0: → 2, "Negative book value — negative shareholder equity (distressed / post-merger)"` PRE `pb < 1`. (`<=0` hvata i degeneričnu nulu; 2 = dno postojećeg raspona.)
- **#20 ROE** (`scoring.py`): kad je `pb_ratio <= 0` (negativan equity) → ROE `5, "ROE unreliable — negative equity base (denominator artifact)"` (neutralno, ne 9 i ne dupla kazna). **Bez** magnitude capa i **bez** `pb=None` grananja — pozitivan-sićušan equity već daje visok P/B (kažnjen tamo), a legitiman buyback-driven ROE (AAPL ~141% uz pozitivan equity) **ostaje 9/10**.
- `compute_quick_score` netaknut (ne koristi P/B/ROE — potvrđeno).

**Codex CLI review** (log: `docs/codex-review/19-20-distressed-denominator.md`, 4 poruke): runda 1 **AGREED** sa doradama — ROE=5 neutralno (ne nisko) da se izbegne dupla kazna; bez magnitude capa da AAPL/NVDA ne stradaju; P/B=2. Sve tri Codex-ove tvrdnje nezavisno verifikovane pre prihvatanja (compute_quick_score, AAPL ROE test, aritmetika). Severity **#19 🔴, #20 🟡**.

**Verifikacija:** `tests/test_distressed_denominator.py` — **15/15 PASS** (neg P/B→2, poz P/B nepromenjen, neg-equity ROE→5, AAPL poz-equity ROE→9, `pb=None`→postojeće, **aritmetika pinovana: FGMC fundamental 4.6→3.5**). Pun regresioni prolaz — **15/15 fajlova zeleno** (uklj. `fundamental_units` 18/18 gde AAPL/NVDA ROE ostaju 9), nula padova.

Izmenjeni fajlovi: `scripts/scoring.py` (P/B + ROE blok u `_score_fundamental`), `tests/test_distressed_denominator.py` (nov).

---

*Izveštaj generisan analizom skripte-po-skriptu. ROE/D-E bugovi (#1, #2) empirijski potvrđeni pokretanjem `_score_fundamental` sa realnim AAPL vrednostima.*
