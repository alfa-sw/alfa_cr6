# Ottimizzazioni browser e service page — RM587

Data: 16 luglio 2026

Progetti coinvolti: `alfa_cr6`, `devices`

Target di misura: macchina `192.168.12.54`

Browser embedded: QtWebEngine con Chromium 69

Il documento riassume l'attività di analisi, integrazione, ottimizzazione e
misura svolta il 15–16 luglio 2026. Include anche `devices@380a7ec`, precedente
all'intervento, perché costituisce il prerequisito lato pagina web della
soluzione finale distribuita e misurata.

## 1. Obiettivo

L'attività ha avuto quattro obiettivi:

1. ridurre il tempo percepito tra il tocco del pulsante di una testa e la
   visualizzazione della relativa service page;
2. evitare di distruggere e ricreare inutilmente QtWebEngine quando la pagina
   viene nascosta;
3. impedire che una pagina WebEngine nascosta continui a ricevere eventi dal
   WebSocket;
4. produrre misure ripetibili che separino server, trasferimento HTTP, parsing
   HTML, JavaScript, style, layout e paint.

La service page continua a essere ricaricata a ogni apertura, anche quando
l'URL è uguale a quello precedente. Questa è una scelta di correttezza: la
pagina è renderizzata lato server e contiene dati che possono essere cambiati
nel frattempo. Saltare `setUrl()` renderebbe più veloce la riapertura, ma
potrebbe mostrare livelli, pigmenti o configurazioni non aggiornati.

## 2. Evoluzione del lifecycle QtWebEngine

Sono state analizzate le seguenti iterazioni in `alfa_cr6`:

| Commit | Soluzione | Stato finale |
|---|---|---|
| `02e1ad5` | navigazione ad `about:blank` quando la pagina viene nascosta, per liberare DOM, JavaScript e WebSocket | superata |
| `e932392` | attesa del completamento di `about:blank` prima di lasciare la web view | superata |
| `d57edcf` | diagnostica e prove sul lifecycle di `browser_page` | intermedia |
| `6fa7722` | WebEngine residente; sospensione del solo WebSocket durante l'hide | adottata |
| `95f297b` | fallback ad `about:blank` per pagine interne prive degli hook WebSocket | adottata |

Il design finale conserva il `QWebEngineView` e il renderer, ma applica questo
contratto:

- su `hideEvent`, Qt invoca `window.alfaSuspendWS()`;
- su `showEvent`, Qt invoca `window.alfaResumeWS()`;
- se il caricamento termina quando la pagina è già nascosta, Qt sospende
  nuovamente il WebSocket;
- suspend e resume sono idempotenti lato JavaScript;
- una pagina interna senza hook viene portata ad `about:blank`;
- una pagina cliente esterna senza hook rimane residente e non viene blankata.

Il fallback interno protegge le versioni meno recenti di `devices` e le pagine
locali admin/settings che non espongono gli hook. Per queste pagine il beneficio
della residenza non è disponibile finché non implementano lo stesso contratto.

## 3. Ottimizzazioni implementate

### 3.1 WebEngine residente

Prima, uscire dalla pagina significava caricare `about:blank`. La riapertura
doveva ricostruire nuovamente il documento e ripartire da uno stato più freddo.

Ora la view rimane allocata. Vengono evitati:

- distruzione esplicita del documento al solo cambio pagina Qt;
- navigazione aggiuntiva verso `about:blank`;
- lavoro di lifecycle non necessario sul renderer;
- ritardi introdotti dall'attesa del completamento della pagina vuota.

La view residente non significa però pagina dati riutilizzata: `open_page()`
continua intenzionalmente a ricaricare l'URL richiesto.

### 3.2 Sospensione cooperativa del WebSocket

Nel progetto `devices`, commit `380a7ec`, sono stati introdotti:

- `window.alfaSuspendWS()`;
- `window.alfaResumeWS()`;
- memorizzazione degli argomenti necessari alla riconnessione;
- chiusura dei socket machine e labeler su suspend;
- gestione dei socket ancora in `CONNECTING` o `CLOSING`;
- gate che impedisce a una pagina nata nascosta di aprire il socket;
- supporto aggiuntivo a `visibilitychange` per la variante light.

Il vantaggio principale non è un tempo di caricamento inferiore, ma la
possibilità di mantenere la WebEngine residente senza lasciare una pagina
nascosta collegata al fan-out degli eventi.

### 3.3 Variante `light_service_page`

CR6 apre le service page con:

```text
?light_service_page=1
```

La variante light:

- usa `bootstrap.min.css`;
- non carica Font Awesome;
- non carica Popper;
- evita l'include delle modali quando non necessario;
- riduce `config_json` ai soli campi usati dalla pagina;
- elimina dati di contesto non letti dal template;
- elimina l'include duplicato di `websocket_client.js`;
- corregge il markup della tabella;
- formatta lato server i valori già espressi in CC;
- salta il passaggio JavaScript di conversione CC → CC;
- evita riscritture DOM per il font quando la dimensione è quella normale.

Gli asset iniziali passano da 7 a 5.

### 3.4 Warm-up Jinja e riduzione del lavoro server

La cache dei template Jinja viene scaldata all'avvio di ciascun processo Flask.
I nomi usati per il warm-up coincidono con quelli usati dagli handler,
da `{% extends %}` e da `{% include %}`.

Sono state inoltre introdotte:

- una funzione condivisa per costruire i dati della service page;
- `joinedload(Pipe.pigment)` per evitare query N+1;
- formattazione di alcuni valori lato server;
- diagnostica separata per preparazione dati e rendering.

Il warm-up sposta parte del costo dalla prima richiesta all'avvio del processo.
Non accelera il primo utilizzo assoluto misurato da processo spento; rende invece
molto più breve la prima route richiesta dopo che il processo è disponibile.

### 3.5 Script in fondo alla pagina

Nella sola variante light, jQuery, Bootstrap, `ui_helpers.js` e
`websocket_client.js` sono stati spostati dopo il markup principale e prima
della chiusura di `body`.

La variante legacy mantiene gli script nell'`head`, preservando il comportamento
delle pagine non embedded.

Il vantaggio è che il parser può costruire prima il DOM visibile, senza fermarsi
sugli script esterni. L'ordine tra gli script è rimasto invariato, evitando
regressioni nelle dipendenze jQuery/Bootstrap.

### 3.6 Compressione gzip

È stato aggiunto un middleware locale Flask senza dipendenze esterne. Comprime:

- HTML;
- CSS;
- JavaScript;
- JSON/XML;
- SVG.

La compressione viene applicata solo quando:

- la risposta è HTTP 200;
- il client dichiara `Accept-Encoding: gzip`;
- il contenuto è comprimibile e supera la soglia minima;
- non esiste già un `Content-Encoding`;
- non si tratta di una range response o di una risposta `no-transform`.

Le risposte streaming non vengono materializzate. Fanno eccezione soltanto i
file statici finiti serviti dagli endpoint Flask `static` o `*.static`, per i
quali sono noti endpoint e `Content-Length`.

La risposta aggiunge `Vary: Accept-Encoding`, indebolisce un eventuale ETag
dopo la trasformazione e aggiorna `Content-Length`.

Il gzip è pienamente supportato da Chromium 69. Il vantaggio è elevato su teste
Ethernet e browser remoti; su loopback il beneficio di rete è più piccolo e va
bilanciato con il costo CPU. Il livello scelto è 4.

## 4. Ottimizzazioni valutate ma non implementate

| Possibile ottimizzazione | Impatto atteso | Decisione |
|---|---|---|
| inizializzare QtWebEngine all'avvio di CR6 | medio sulla sola prima apertura; nullo sulle successive | non implementata: anticipa CPU/RAM e può peggiorare l'avvio |
| non eseguire `setUrl()` quando l'URL è identico | molto alto sulla riapertura | scartata: mostrerebbe dati server-side potenzialmente obsoleti |
| una WebEngine residente per ogni testa | alto negli switch tra teste | non implementata: RAM e numero di renderer/socket crescono con le teste |
| shell HTML persistente con soli aggiornamenti AJAX/WS | alto sulle riaperture | possibile evoluzione, ma richiede un refactoring sostanziale della pagina |
| aggiungere gli hook anche ad admin/settings | medio sulle riaperture locali | possibile; oggi viene usato il fallback `about:blank` |
| `defer`/`async` sugli script | medio | non adottato: dipendenze e script inline rendono rischioso l'ordine su Chromium 69 |
| critical CSS o sostituzione di Bootstrap | medio/alto | non implementata: costo di manutenzione elevato |
| eliminare jQuery/Bootstrap JS | medio | possibile solo con una riscrittura della UI |
| bundle unico degli asset | basso/medio con HTTP/1.1 | non implementato: riduce richieste ma peggiora granularità della cache |
| asset statici precompressi o cache gzip server-side | medio a cache fredda e minore CPU | raccomandato come evoluzione del middleware |
| cache HTTP `immutable` con nomi versionati | medio sulle riaperture dopo restart | possibile; richiede versionamento affidabile degli asset |
| precaricamento della prossima service page | variabile | non implementato: non è noto quale testa verrà aperta e si consumerebbero risorse inutilmente |
| upgrade di QtWebEngine/Chromium | potenzialmente alto, oltre al beneficio di sicurezza | raccomandabile a lungo termine, ma richiede migrazione della piattaforma Qt |
| GPU/flag Chromium aggressivi | incerto | non adottati senza evidenza; alto rischio su hardware embedded |

## 5. Composizione esatta del confronto A/B

Il benchmark non ha confrontato “pacchetto produzione” contro “intero working
tree dev”.

Le varianti erano:

```text
OLD = CR6 identico + package devices originale installato in produzione

NEW = CR6 identico + package devices di produzione
      + sole modifiche selezionate per service page, gzip e WebSocket
```

In `NEW` erano presenti:

- `devices@380a7ec`, adattato alla versione installata;
- `http_compression.py`;
- integrazione gzip in `app.py`;
- lazy import in `alfa_flask/__init__.py`;
- spostamento degli script in fondo alla variante light;
- hook suspend/resume in `websocket_client.js`.

Non erano presenti:

- modifiche a `src/alfa_common/macro_processor.py`;
- modifiche a `src/alfa_old_lib/api.py`;
- documentazione e README;
- test e script di sviluppo;
- altre modifiche non pertinenti del working tree `devices`.

Durante entrambi i lati A/B, CR6 usava lo stesso `browser_page.py` con view
residente, fallback RM587 e strumentazione. Il confronto renderer isola quindi
le modifiche `devices`; non misura separatamente il passaggio da blanking a view
residente.

## 6. Metodologia

### 6.1 Ambiente

- macchina: `192.168.12.54`;
- istanza analizzata: testa 1;
- URL: `http://127.0.0.1:8081/service_page/?light_service_page=1`;
- QtWebEngine: Chromium 69;
- un campione freddo dopo `Network.clearBrowserCache`;
- cinque campioni caldi;
- reload comandato tramite Chrome DevTools Protocol;
- stessa applicazione CR6 e stesso hardware per OLD e NEW.

Il remote debugging è stato abilitato temporaneamente con:

```text
QTWEBENGINE_REMOTE_DEBUGGING=9222
```

Al termine è stato disabilitato. Il runtime `NEW` è stato ripristinato e i
quattro processi Flask sono stati verificati in esecuzione.

### 6.2 Significato delle metriche

| Metrica | Significato |
|---|---|
| `responseEnd` | HTML principale completamente ricevuto |
| `domInteractive` | DOM costruito e parser arrivato allo stato interattivo |
| `loadEventEnd` | evento `load` completato; “caricamento tecnico completo” |
| FCP | primo contenuto effettivamente dipinto |
| two frames complete | due `requestAnimationFrame` dopo il load; proxy prudenziale di pagina stabilizzata |
| parse | tempo `ParseHTML` sul renderer main thread |
| script | durata JavaScript riportata dal dominio Performance |
| style | ricalcolo degli stili |
| layout | calcolo geometrico del layout |
| paint | rasterizzazione dei contenuti modificati |

Il confronto relativo OLD/NEW è più affidabile del singolo valore assoluto:
la trace introduce un piccolo overhead ed è stata eseguita in blocchi, prima
NEW e poi OLD, senza alternare ogni campione.

## 7. Script usati

### 7.1 Benchmark Flask/HTTP

Sorgente:

```text
devices/scripts/benchmark_service_page.py
```

Esempio:

```bash
/opt/alfa40/venv/bin/python scripts/benchmark_service_page.py \
  --package-root /tmp/rm587_benchmark_packages/new \
  --config /opt/alfa40/conf/flask_conf.py \
  --instance-index 1 \
  --label new_1 \
  --warm-runs 15 \
  --log-file /opt/alfa40/rm587_service_page_benchmark_20260716.log
```

Lo script:

- importa una copia isolata OLD o NEW del package;
- misura inizializzazione Flask;
- misura prima route e route calde;
- confronta body gzip e identity;
- estrae dal documento gli asset iniziali;
- verifica che le rappresentazioni decompresse siano identiche;
- calcola byte trasferiti, mediana e p90.

### 7.2 Trace QtWebEngine

Sorgente completo:

```text
alfa_cr6/target_scripts/webengine_perf_trace.py
```

Checksum della versione usata:

```text
SHA-256 703eba231f40f6bbdca3b579b426ab1afa3ad413024ff4122b15f0fc86dc8130
```

Comando NEW:

```bash
/opt/alfa_cr6/venv/bin/python /opt/alfa_cr6/webengine_perf_trace.py \
  --samples 6 \
  --auto-reload \
  --clear-cache-first \
  --reload-pause-seconds 2 \
  --log-file /opt/alfa_cr6/webengine_perf_trace_final_20260716.log \
  --raw-trace-prefix /opt/alfa_cr6/webengine_perf_trace_final_20260716
```

Per OLD è stato usato lo stesso comando cambiando solamente prefisso e file di
log. Lo script usa CDP `Page`, `Network`, `Performance`, `Runtime` e `Tracing`,
ed è compatibile con gli eventi completi `X` e con le coppie begin/end `B`/`E`
emesse da Chromium 69.

## 8. Test di regressione

| Suite | Risultato | Ambiente |
|---|---:|---|
| gzip, statici, streaming, ETag, ordine script light/legacy | 9/9 passati | checkout `devices` |
| lifecycle WS, fallback e callback asincrone | 6/6 passati | virtualenv reale della 12.54 |
| compilazione collector | passata | `python3 -m py_compile` |
| verifica whitespace diff | passata | `git diff --check` |

Comando suite `devices`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover \
  -s tests/flask \
  -p 'test_gzip_and_light_assets.py' \
  -v
```

Comando suite CR6 usato nel container target:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/opt/alfa_cr6/venv/lib/python3.8/site-packages \
/opt/alfa_cr6/venv/bin/python -m unittest \
  test_browser_page_ws_lifecycle \
  -v
```

I test `devices` coprono in particolare:

- HTML dinamico compresso;
- file statici app e blueprint compressi;
- generatori streaming non bufferizzati;
- generatori `direct_passthrough=True` non consumati;
- ETag indebolito dopo compressione;
- `Vary: Accept-Encoding`;
- risposte piccole/identity non compresse;
- script light in fondo al `body`;
- script legacy ancora nell'`head`.

I test CR6 coprono:

- suspend → suspend → resume → resume;
- load terminato mentre la pagina è nascosta;
- fallback interno senza hook;
- pagina esterna senza hook residente;
- callback differita dopo ritorno alla visibilità;
- callback differita dopo cambio URL o sostituzione della view.

Il Python di sviluppo locale non contiene `redis`; per questo la suite CR6 è
stata eseguita nel virtualenv installato sulla macchina target.

## 9. Risultati Flask e trasferimento HTTP

I dati sono mediane di cinque processi separati; ogni processo esegue 15
richieste calde.

| Metrica | OLD | NEW | Variazione |
|---|---:|---:|---:|
| startup Flask | 3.533,56 ms | 3.791,67 ms | +7,3% |
| prima route dopo startup | 271,67 ms | 34,31 ms | **−87,4%** |
| route calda, mediana | 27,61 ms | 19,12 ms | **−30,8%** |
| route calda, p90 | 28,17 ms | 20,16 ms | **−28,4%** |
| HTML trasferito | 57.248 B | 12.429 B | **−78,3%** |
| trasferimento iniziale HTML + asset | 529.000 B | 90.559 B | **−82,9%** |
| startup + prima route | 3.805,23 ms | 3.825,98 ms | +0,5% |

Il warm-up Jinja rende molto più veloce la prima route, ma aumenta lo startup.
Il tempo “processo spento → prima route conclusa” rimane quindi quasi uguale.

## 10. Risultati QtWebEngine

### 10.1 Campione freddo

| Metrica | OLD | NEW | Variazione |
|---|---:|---:|---:|
| `responseEnd` | 393 ms | 100 ms | **−74,6%** |
| DOM interattivo | 688 ms | 331 ms | **−51,9%** |
| caricamento tecnico completo (`loadEventEnd`) | 729 ms | 359 ms | **−50,8%** |
| primo contenuto visibile (FCP) | 864 ms | 543 ms | **−37,2%** |
| due frame dopo il load | 1.372 ms | 762 ms | **−44,5%** |
| parsing HTML | 122,28 ms | 106,89 ms | −12,6% |
| JavaScript | 176,75 ms | 148,46 ms | −16,0% |
| style | 24,39 ms | 17,17 ms | −29,6% |
| layout | 19,11 ms | 12,39 ms | −35,2% |
| paint | 2,87 ms | 4,12 ms | +1,25 ms |

L'aumento percentuale del paint freddo non è significativo: la differenza
assoluta è circa 1,25 ms. Il miglioramento deriva soprattutto da risposta,
costruzione del documento, JavaScript, style e layout.

### 10.2 Campioni caldi — media di cinque aperture

| Metrica | OLD | NEW | Variazione |
|---|---:|---:|---:|
| `responseEnd` | 139,0 ms | 142,0 ms | +2,2% |
| DOM interattivo | 326,8 ms | 284,4 ms | **−13,0%** |
| caricamento tecnico completo (`loadEventEnd`) | 365,6 ms | 305,8 ms | **−16,4%** |
| primo contenuto visibile (FCP) | 606,0 ms | 462,0 ms | **−23,8%** |
| due frame dopo il load | 752,2 ms | 662,0 ms | **−12,0%** |
| parsing HTML | 81,58 ms | 55,46 ms | **−32,0%** |
| JavaScript | 113,43 ms | 92,65 ms | **−18,3%** |
| style | 26,21 ms | 16,46 ms | **−37,2%** |
| layout | 17,38 ms | 9,04 ms | **−48,0%** |
| paint | 3,87 ms | 3,88 ms | invariato |

### 10.3 Campioni caldi — mediana e variabilità

| Metrica | OLD mediana | NEW mediana | OLD intervallo | NEW intervallo |
|---|---:|---:|---:|---:|
| `loadEventEnd` | 352 ms | 306 ms | 329–446 ms | 293–316 ms |
| FCP | 548 ms | 459 ms | 511–837 ms | 419–525 ms |
| due frame dopo load | 660 ms | 691 ms | 606–1.006 ms | 602–695 ms |

Il proxy “due frame” è più rumoroso: la mediana NEW è 31 ms superiore, mentre
la media è 90 ms inferiore perché OLD contiene aperture molto lente. FCP e load,
che rappresentano meglio il tempo percepito e il caricamento tecnico, migliorano
sia come valore centrale sia come stabilità.

## 11. Interpretazione

1. **A freddo il gzip e la pagina light sono determinanti.** Il trasferimento
   iniziale scende dell'82,9% e `responseEnd` scende da 393 a 100 ms.

2. **A caldo la rete non è più il collo di bottiglia.** `responseEnd` rimane
   sostanzialmente uguale, mentre parsing, JavaScript, style e layout
   diminuiscono. Il beneficio caldo deriva quindi soprattutto dalla pagina
   alleggerita e dagli script collocati dopo il markup.

3. **Il paint puro non è il problema.** Costa circa 4 ms sia OLD sia NEW.
   Il tempo percepito è dominato dal lavoro precedente al primo paint e dalla
   disponibilità della main thread.

4. **La nuova pagina è più stabile.** Il FCP caldo passa da un intervallo
   511–837 ms a 419–525 ms.

5. **Il tempo caldo rappresentativo per l'operatore è circa 0,46 secondi fino
   al primo contenuto e circa 0,31 secondi fino al completamento del load.**

## 12. Raccomandazioni

Priorità suggerite:

1. consolidare in commit separati gzip/script-in-fondo e relativa suite;
2. mantenere OLD/NEW e i log allegati come baseline RM587;
3. misurare almeno una macchina con teste Ethernet fisiche;
4. valutare cache/precompressione degli asset statici per eliminare il costo
   gzip ripetuto lato server;
5. aggiungere hook suspend/resume alle pagine admin/settings solo se il loro
   tempo di riapertura diventa rilevante;
6. valutare in un'attività separata l'upgrade di QtWebEngine, soprattutto per
   ragioni di sicurezza e compatibilità.

## Appendice A — file di prova e log originali

File conservati nel repository:

```text
target_scripts/webengine_perf_trace.py
doc/rm587_browser_optimization/service_page_http_benchmark_20260716.txt
doc/rm587_browser_optimization/webengine_perf_trace_old_20260716.txt
doc/rm587_browser_optimization/webengine_perf_trace_new_20260716.txt
```

Checksum:

```text
5a73ac4e9d45d1f8423f2c4a7e4b5994af71f5a12000559e4906e66b1c5c6495  service_page_http_benchmark_20260716.txt
acf190a3c0b0eb6eb8a64e06947c4ec502dae2b7e322555586695cc591a93509  webengine_perf_trace_old_20260716.txt
11dbeca83b54f0957d64a633776f4b6e0a698f0e48a9c90440dfa977ced236ad  webengine_perf_trace_new_20260716.txt
703eba231f40f6bbdca3b579b426ab1afa3ad413024ff4122b15f0fc86dc8130  webengine_perf_trace.py
```

## Appendice B — log QtWebEngine NEW

```text
webengine_trace sample=1 response_ms=100 dom_interactive_ms=331 fcp_ms=543 load_ms=359 frames_done_ms=762 script_ms=148.46 style_ms=17.17 layout_ms=12.39 paint_ms=4.12 composite_ms=2.69
webengine_trace sample=2 response_ms=137 dom_interactive_ms=275 fcp_ms=419 load_ms=300 frames_done_ms=695 script_ms=84.16 style_ms=16.46 layout_ms=8.66 paint_ms=3.57 composite_ms=1.11
webengine_trace sample=3 response_ms=147 dom_interactive_ms=307 fcp_ms=471 load_ms=316 frames_done_ms=695 script_ms=96.21 style_ms=16.29 layout_ms=11.6 paint_ms=4.85 composite_ms=2.58
webengine_trace sample=4 response_ms=137 dom_interactive_ms=291 fcp_ms=525 load_ms=314 frames_done_ms=691 script_ms=108.67 style_ms=16.27 layout_ms=7.31 paint_ms=2.88 composite_ms=0.64
webengine_trace sample=5 response_ms=153 dom_interactive_ms=282 fcp_ms=436 load_ms=306 frames_done_ms=602 script_ms=92.87 style_ms=15.4 layout_ms=10.34 paint_ms=4.56 composite_ms=1.35
webengine_trace sample=6 response_ms=136 dom_interactive_ms=267 fcp_ms=459 load_ms=293 frames_done_ms=627 script_ms=81.34 style_ms=17.89 layout_ms=7.31 paint_ms=3.56 composite_ms=0.91
WEBENGINE_TRACE_SUMMARY_JSON {"cold": {"dom_interactive_ms": 331, "first_contentful_paint_ms": 543, "layout_duration_ms": 12.39, "load_event_ms": 359, "response_end_ms": 100, "script_duration_ms": 148.46, "style_duration_ms": 17.17, "trace_composite_ms": 2.69, "trace_paint_ms": 4.12, "trace_parse_ms": 106.89, "two_frames_complete_ms": 762}, "warm_median": {"dom_interactive_ms": 282, "first_contentful_paint_ms": 459, "layout_duration_ms": 8.66, "load_event_ms": 306, "response_end_ms": 137, "script_duration_ms": 92.87, "style_duration_ms": 16.29, "trace_composite_ms": 1.11, "trace_paint_ms": 3.57, "trace_parse_ms": 54.65, "two_frames_complete_ms": 691}, "warm_samples": 5}
```

## Appendice C — log QtWebEngine OLD

```text
webengine_trace sample=1 response_ms=393 dom_interactive_ms=688 fcp_ms=864 load_ms=729 frames_done_ms=1372 script_ms=176.75 style_ms=24.39 layout_ms=19.11 paint_ms=2.87 composite_ms=1.37
webengine_trace sample=2 response_ms=138 dom_interactive_ms=304 fcp_ms=548 load_ms=342 frames_done_ms=660 script_ms=108.63 style_ms=25.79 layout_ms=13.22 paint_ms=3.91 composite_ms=5.86
webengine_trace sample=3 response_ms=146 dom_interactive_ms=317 fcp_ms=589 load_ms=359 frames_done_ms=651 script_ms=103.02 style_ms=28.96 layout_ms=20.8 paint_ms=5.03 composite_ms=2.29
webengine_trace sample=4 response_ms=138 dom_interactive_ms=408 fcp_ms=837 load_ms=446 frames_done_ms=1006 script_ms=165.25 style_ms=23.57 layout_ms=11.86 paint_ms=3.87 composite_ms=1.93
webengine_trace sample=5 response_ms=136 dom_interactive_ms=293 fcp_ms=545 load_ms=329 frames_done_ms=606 script_ms=97.2 style_ms=25.45 layout_ms=22.61 paint_ms=3.31 composite_ms=13.91
webengine_trace sample=6 response_ms=137 dom_interactive_ms=312 fcp_ms=511 load_ms=352 frames_done_ms=838 script_ms=93.03 style_ms=27.3 layout_ms=18.39 paint_ms=3.24 composite_ms=1.59
WEBENGINE_TRACE_SUMMARY_JSON {"cold": {"dom_interactive_ms": 688, "first_contentful_paint_ms": 864, "layout_duration_ms": 19.11, "load_event_ms": 729, "response_end_ms": 393, "script_duration_ms": 176.75, "style_duration_ms": 24.39, "trace_composite_ms": 1.37, "trace_paint_ms": 2.87, "trace_parse_ms": 122.28, "two_frames_complete_ms": 1372}, "warm_median": {"dom_interactive_ms": 312, "first_contentful_paint_ms": 548, "layout_duration_ms": 18.39, "load_event_ms": 352, "response_end_ms": 138, "script_duration_ms": 103.02, "style_duration_ms": 25.79, "trace_composite_ms": 2.29, "trace_paint_ms": 3.87, "trace_parse_ms": 74.4, "two_frames_complete_ms": 660}, "warm_samples": 5}
```

## Appendice D — estratto log benchmark Flask/HTTP

```text
service_page_benchmark label=old_assets startup_wall_ms=3542.12 cold_wall_ms=269.45 cold_cpu_ms=268.96 warm_median_ms=27.77 warm_p90_ms=28.03 warm_cpu_median_ms=27.6 gzip=False gzip_bytes=57248 identity_bytes=57248 saved_percent=0.0 assets=7 cold_transfer_bytes=529000 cold_transfer_identity_bytes=529000 cold_transfer_saved_percent=0.0 light=False
service_page_benchmark label=new_assets startup_wall_ms=3818.36 cold_wall_ms=34.83 cold_cpu_ms=34.81 warm_median_ms=19.72 warm_p90_ms=19.85 warm_cpu_median_ms=19.71 gzip=True gzip_bytes=12429 identity_bytes=49322 saved_percent=74.8 assets=5 cold_transfer_bytes=90559 cold_transfer_identity_bytes=367525 cold_transfer_saved_percent=75.36 light=True
BENCHMARK_SUMMARY {"cold_new_median_ms": 34.31, "cold_old_median_ms": 271.67, "cold_reduction_percent": 87.37, "cold_speedup": 7.92, "cold_transfer_new_bytes": 90559, "cold_transfer_old_bytes": 529000, "cold_transfer_ratio": 5.84, "cold_transfer_reduction_percent": 82.88, "first_ever_new_ms": 3825.98, "first_ever_old_ms": 3805.23, "samples_per_variant": 5, "startup_increase_ms": 258.11, "startup_increase_percent": 7.3, "startup_new_median_ms": 3791.67, "startup_old_median_ms": 3533.56, "warm_html_new_bytes": 12429, "warm_html_old_bytes": 57248, "warm_html_reduction_percent": 78.29, "warm_new_median_ms": 19.12, "warm_old_median_ms": 27.61, "warm_p90_new_ms": 20.16, "warm_p90_old_ms": 28.17, "warm_p90_reduction_percent": 28.43, "warm_reduction_percent": 30.75, "warm_speedup": 1.44}
```

Il log Flask/HTTP completo, incluse le cinque esecuzioni OLD e NEW e i payload
JSON degli asset, è conservato nel file indicato nell'Appendice A.
