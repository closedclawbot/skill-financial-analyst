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
| 1 | `scoring.py` | 🔴 | ROE `×100 if abs(roe)<1` greši za ROE>100% | AAPL: 4/10 umesto 9/10 — **POTVRĐENO** |
| 2 | `scoring.py` | 🔴 | D/E `if de>10` greši za nisko-zadužene firme | D/E 0.08 → 2/10 "ekstremno zadužen" — **POTVRĐENO** |
| 3 | `technical_analysis.py` | 🔴 | MACD signal/histogram zamenjeni (pandas-ta grana) | `macd_bullish` skoro uvek pogrešan |
| 4 | `run_deep_dive.py` | 🔴 | Price fallback lanac šupalj — samo yfinance daje upotrebljiv oblik | Nema tehnike kad yfinance padne |
| 5 | `macro_calendar.py` | 🔴 | Finnhub kalendar mrtav (`api_keys` vs `apis`) | Makro događaji samo hardkodovani, zastareli posle 2026. |
| 6 | `data_fetchers.py` | 🟡 | `sec_edgar_filings` 2 bespotrebna poziva + lažni URL | Trošenje HTTP poziva |
| 7 | `data_fetchers.py` | 🟡 | Hardkodovan UA `contact@example.com` | SEC 403 rizik |
| 8 | `data_fetchers.py` | 🟡 | `yfinance_analyst_ratings` zastareo šema | Prazne analitičar ocene |
| 9 | `data_fetchers.py` | 🟡 | AV rate-limit detekcija zastarela (`Information`) | Nejasna greška na limitu |
| 10 | `data_fetchers.py` | 🟡 | `yfinance_earnings` koristi uklonjeni `quarterly_earnings` | AttributeError u fallback grani |
| 11 | `entry_exit.py` | 🟡 | Sajzing ignoriše kupovnu moć i float | Može prikazati poziciju od 500% računa |
| 12 | `run_portfolio_review.py` | 🟡 | `float()` u CSV parsiranju bez try/except | Loš broj ruši ceo review — **✅ ISPRAVLJENO** |
| 13 | `data_cache.py` | 🟡 | Formater čita drugu šemu ključeva nego producenti (tehnika, cena, R:R, insider, news, earnings, congress, dividends, TV) + `above_sma None→"Below"` (pogrešna tvrdnja) | Glavni `.md` artefakt prazan/netačan (ocene netaknute) — **✅ ISPRAVLJENO** |
| 14 | `data_cache.py` | ⚪ | `_fmt_pct` `abs<1` heuristika mis-scale | Pogrešno prikazan dividend_yield |
| 15 | `technical_analysis.py` | ⚪ | `golden_cross`/`death_cross` su stanje, ne događaj | Duplira `above_sma`, pogrešan naziv |
| 16 | `api_config.py` | ⚪ | `enabled` flag se ignoriše | Dokumentacija govori da se postavi, kôd ne čita |
| 17 | `api_caller.py` | ⚪ | `time.sleep(delay)` pre svakog poziva, i prvog | Nepotrebno usporenje (AV 12s) |
| 18 | Poprečno | 🟡 | **Free float / short interest se nigde ne koristi** | Nema likvidnosnog/squeeze signala; sajzing ne zna float |

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
- 🟡 **#6 — `sec_edgar_filings` pravi 2 bespotrebna HTTP poziva.** Prva dva zahteva (`r`, `r2`) se nikad ne koriste; prvi URL (`efts.sec.gov/LATEST/search-index`) nije ni pravi endpoint. Koriste se samo `company_tickers.json` i `submissions`.
- 🟡 **Semantički mismatch:** `sec_edgar_filings` vraća listu filing-a, a registrovan je pod `fundamentals` lancem. Ako yfinance fundamentals padne, dobija se lista 10-K/10-Q dokumenata umesto finansijskih pokazatelja.
- 🟡 **#7 — Hardkodovan User-Agent `contact@example.com`** umesto korisnikovog email-a iz config-a (`user_agent_email`). SEC blokira generičke UA → 403 rizik.
- 🟡 **#8 — `yfinance_analyst_ratings` čita zastareo šema.** Traži `Firm`/`To Grade`/`Action`, ali moderni yfinance `.recommendations` vraća `[period, strongBuy, buy, hold, sell, strongSell]`. Rezultat: sva polja prazna.
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
- ⚪ **#14 — `_fmt_pct` heuristika `if abs(pct) < 1: pct *= 100` je opasna.** Za yfinance dividend_yield (posle promene 2024. čas frakcija 0.005, čas procenat 0.5) pogrešno skalira — 0.9% postane 90%.
- 🟡 **#13 — Neslaganje ključeva fetcher/motor ↔ formater** (vidi [Status ispravki](#status-ispravki)). **✅ ISPRAVLJENO.**

---

## Sloj 3 — Analitički motori

### `technical_analysis.py` — lokalni TA motor (pandas-ta + ručni fallback)
- 🔴 **#3 — MACD signal i histogram su ZAMENJENI kad se koristi `pandas-ta`.** `ta.macd()` vraća kolone redom `[MACD, MACDh (histogram), MACDs (signal)]`, ali kôd dodeljuje `cols[1]→macd_signal` i `cols[2]→macd_histogram`. Znači `macd_signal` zapravo drži histogram (mali broj oko nule). Posledica: `macd_bullish = macd_line > macd_signal` upoređuje liniju sa histogramom → signal skoro uvek pogrešan. **Ručni fallback (bez pandas-ta) je ISPRAVAN** — bug se javlja baš kad korisnik instalira pandas-ta. Utiče na tehnički faktor #3.
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
- ⚪ Heuristike frakcija-vs-procenat se ponavljaju svuda sa različitim pragovima (`<5`, `<1`, `>10`) — krhko; koren i dividend_yield problema.
- ⚪ `insider` se prosleđuje `_score_fundamental` ali se tamo nikad ne koristi (mrtav parametar); insider se koristi samo u sentiment faktoru.
- ⚪ `congress_trades` parsiranje: `isinstance(trades, list)` — ako Mboum vrati dict wrapper, tiho pada na neutralno 5.
- ✅ Dobro: `compute_quick_score` sa preraspodelom težina kad izvor nedostaje (ne vuče ka ravnih 5.0). Clamp 0-10, sektor modifikator ±0.5 — korektno.

### `entry_exit.py` — 3 ulaza / 3 izlaza / stop / R:R / sajzing
- 🟡 **#11 — Sajzing pozicije ignoriše kupovnu moć (i float).** `shares = int(max_loss / risk_per_share)` bez ograničenja na `account/entry`. Za skupu akciju sa malim rizikom po akciji, trošak može biti npr. 500% računa, a izveštaj mirno pokaže `pct_of_portfolio: 500%` bez upozorenja. Treba capovati na raspoloživi kapital (i idealno na % float-a / ADV-a).
- ⚪ **Redosled operacija u računanju ulaza** (linije 171–173): `e_cons` se računa iz starog `e_mod`, pa se onda `e_mod` menja. Finalni `sorted(reverse=True)` garantuje opadajući redosled, ali ne i nameravan razmak/oznake (moderate/conservative se mogu zameniti).
- ⚪ **8% cap na stop se tiho gazi** pravilom "bar 1 ATR ispod conservative" — za volatilne akcije stvarni stop prelazi deklarisanih 8%.
- ✅ Dobro: zaštita od deljenja nulom u R:R, cap na 20x, `favorable = 2.0 ≤ rr ≤ 15.0`.

---

## Sloj 4 — Kontekstni moduli

### `macro_calendar.py` — earnings + ekonomski događaji + risk flags
- 🔴 **#5 — Finnhub kalendar je mrtav kôd.** `key = config.get("api_keys", {}).get("finnhub")`. Ali `load_config()` vraća `{"apis": {"finnhub": {"api_key": ...}}}` — ne postoji ključ `"api_keys"`. Zato je `key` **uvek None** → `_fetch_finnhub_calendar` uvek vraća praznu listu. Trebalo bi `get_api_key("finnhub")`.
- 🟡 **Hardkodovani datumi idu samo do kraja 2026.** Pošto je Finnhub grana mrtva, posle 2026. nema više nijednog makro događaja. Neki CPI/Jobs datumi su procene.
- ⚪ `earnings_dates` fallback poredi tz-aware indeks sa naivnim `datetime.now()` → TypeError koji se guta u `except` (primarni `calendar` put obično radi).

### `sector_rotation.py` — 11 sektorskih ETF-ova vs SPY
Najčistiji modul — batch download, relativna snaga po 1W/1M/3M, kompozit (0.4/0.35/0.25), modifikator ±0.5, in-memory keš 30 min. **Nema pravih bugova.**
- ⚪ 1W/1M/3M lookback je aproksimacija po broju trgovačkih dana — korektno za ovu vrstu signala.

---

## Sloj 5 — Workflow orkestratori

### `run_deep_dive.py` — Use Case 3 (flagship)
- 🔴 **#4 — Fallback lanac za cenu je praktično kozmetički.** `compute_technicals` traži `price_data["data"]` kao pandas DataFrame — a to vraća **samo yfinance**. Polygon vraća `results` (lista), Alpha Vantage `time_series` (dict), FMP `data` (lista). Ako yfinance padne (429) i cenu posluži fallback → `price_df` je None/lista → TA pukne → `technicals=None`. Cela "otporna" priča za `price_history` je šuplja nizvodno. (Ne ruši se — tech_score padne na 5.0, entry/exit koristi grubi 2%-ATR — ali je degradirano.)
- 🟡 **#13 — Neslaganje šeme ključeva u keširanom `.md`** (širi nego prvobitno procenjeno). `save_cache` dobija sirov fetcher/motor dict, a `_format_markdown` čita drugu šemu → prazno/N/A u tehnici (RSI/MACD/ATR/BB/S-R/Fibonacci), price zaglavlju, R:R (čitan sa pogrešnog mesta), insider, news, earnings, congress, dividends, TV oscilatorima. Dodatno `above_sma None→"Below"` je *pogrešna tvrdnja*, ne samo izostavljena. **Ocene NISU pogođene** (scoring/entry-exit čitaju sirov dict direktno). **✅ ISPRAVLJENO** — vidi [Status ispravki](#status-ispravki).
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
3. **`data_fetchers.py`** — ukloniti bespotrebne SEC pozive + koristiti config email (#6, #7) 🟡
4. **`entry_exit.py`** — cap sajzinga na kupovnu moć + % float/ADV (#11, spaja se sa #18) 🟡
5. **`macro_calendar.py`** — `get_api_key("finnhub")` umesto `config.get("api_keys")` (#5) 🔴
6. **`technical_analysis.py`** — ispraviti redosled MACD kolona (#3) 🔴
7. **`run_deep_dive.py`** — normalizovati sve price fetcher-e u zajednički DataFrame (#4) 🔴
8. **`scoring.py`** — uvek `de/100` za Debt-to-Equity (#2) 🔴
9. **`scoring.py`** — ispraviti ROE skaliranje (#1) 🔴

Paralelno / kao zasebne crte:
- **#18 (free float + short interest)** — likvidnosne/squeeze metrike + sajzing na % float/ADV.
- **Fundamental-enrichment** (zaseban zadatak, *odvojen* od #18) — dohvatiti valuation polja koja formater prikazuje ali `yfinance_fundamentals` ne dohvata: `enterpriseToEbitda`, `pegRatio`, `currentRatio`, `totalCash`, `totalDebt`, `forwardEps`. Sve postoji u yfinance `.info`.
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

---

*Izveštaj generisan analizom skripte-po-skriptu. ROE/D-E bugovi (#1, #2) empirijski potvrđeni pokretanjem `_score_fundamental` sa realnim AAPL vrednostima.*
