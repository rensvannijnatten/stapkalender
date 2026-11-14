# Wandeltochten

Een eenvoudige, gratis gehoste webpagina met georganiseerde wandeltochten in Nederland en België, gesorteerd op afstand vanaf een thuisadres (standaard Zundert). Vervanger voor de Android-app "Wandeltochten".

- **Per dag**: kaart + lijst van één dag, gesorteerd op afstand, filter 30 / 60 km / alles.
- **Alle tochten**: alle tochten van vandaag tot 60 dagen vooruit.
- **Kalender**: maandoverzicht; groene dagen hebben tochten binnen 40 km.

## Hoe het werkt

```
GitHub Actions (elke nacht)
  └─ python -m scraper.main
       ├─ Wandelsport Vlaanderen  wandel.be/wandelkalender  (lijst + detailpagina's, coördinaten in JSON-LD)
       ├─ KWbN                    wandel.nl/sitemap.xml → detailpagina's  (geocoding via Nominatim)
       └─ Adeps                   open data ODWB "points-verts-de-ladeps" (CC BY)
  └─ commit site/data/tochten.json + data/*.json
  └─ publiceer site/ op GitHub Pages
```

| Map / bestand | Inhoud |
|---|---|
| `scraper/` | Python-scraper, één module per bron in `scraper/sources/` |
| `tests/` | pytest-tests met opgeslagen voorbeeldpagina's in `tests/fixtures/` |
| `site/` | De website (HTML/CSS/JS, geen build-stap) |
| `site/config.json` | Thuisadres en afstandsgrenzen |
| `site/data/tochten.json` | De tochten (wordt door de workflow bijgewerkt) |
| `data/geocache.json` | Cache van opgezochte adressen (elk adres één keer naar Nominatim) |
| `data/kwbn_cache.json` | Cache van KWbN-detailpagina's (alleen opnieuw ophalen als `lastmod` verandert) |

**Afspraken met de bronnen**
- Eigen User-Agent met link naar deze repo, maximaal 1 request per seconde per host, retries met backoff.
- wandel.nl: `/umbraco/` (de zoek-API) is via robots.txt verboden, daarom de sitemap.
- Meerdaagse KWbN-evenementen (bv. "za en zo", vierdaagses) worden overgeslagen.
- Valt een bron uit of levert die 0 tochten op, dan wordt de run rood (mail van GitHub). De andere bronnen worden wel bijgewerkt en van de kapotte bron blijven de vorige gegevens staan. Een lege `tochten.json` wordt nooit geschreven.

## Lokaal draaien

Vereist Python 3.12 of nieuwer.

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

Tests:

```bash
.venv/bin/python -m pytest
```

Tochten ophalen (duurt een paar minuten; de eerste keer zonder caches ±15 minuten):

```bash
.venv/bin/python -m scraper.main
```

Eén bron:

```bash
.venv/bin/python -m scraper.main --only adeps
```

Site bekijken op http://localhost:8000:

```bash
python3 -m http.server 8000 --directory site
```

(De site moet via een webserver geopend worden; dubbelklikken op `index.html` werkt niet omdat de browser dan `tochten.json` niet mag laden.)

## Thuisadres aanpassen

Standaard in `site/config.json`. Op de site zelf kan via de knop "Vanaf Zundert" tijdelijk een andere plaats gekozen worden; dat wordt alleen in die browser onthouden.

## Op GitHub zetten

1. Maak de repo `stapkalender` aan op GitHub en push `main`.
2. **GitHub Pages aanzetten**: *Settings → Pages → Build and deployment → Source: **GitHub Actions***.
3. **Schrijfrechten voor de workflow**: *Settings → Actions → General → Workflow permissions → **Read and write permissions*** (nodig om `tochten.json` te committen).
4. Start de eerste run handmatig (zie hieronder). Daarna draait hij elke nacht vanzelf.

De site staat daarna op `https://<gebruikersnaam>.github.io/stapkalender/`.

## Workflow handmatig starten

*Actions → "Tochten bijwerken en site publiceren" → **Run workflow***. Of met de GitHub CLI:

```bash
gh workflow run tochten.yml
```

Mail bij een mislukte run: GitHub stuurt die standaard naar wie de workflow het laatst heeft aangepast. Controleer *Settings (je profiel) → Notifications → Actions → "Send notifications for failed workflows only"*.

Let op: GitHub zet geplande workflows uit na 60 dagen zonder activiteit in de repo. Omdat de workflow elke nacht commit, gebeurt dat normaal niet.

## Bronvermelding

- Kaart: © OpenStreetMap-bijdragers
- Adeps Points Verts: open data van ODWB, licentie CC BY
- Tochtgegevens: wandel.be (Wandelsport Vlaanderen), wandel.nl (KWbN)
