# Strategia test hardware-free per alfa_cr6

L'obiettivo della suite e' intercettare in sviluppo le regressioni di logica,
sincronizzazione e sicurezza del flusso, lasciando alla macchina reale soltanto
le verifiche che dipendono da caratteristiche fisiche.

## Esecuzione

Suite rapida, adatta a ogni modifica:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  /opt/alfa_cr6/venv/bin/python3 -m alfa_CR6_test.hardware_free_suite -v
```

Suite estesa con websocket end-to-end su interfaccia loopback:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  /opt/alfa_cr6/venv/bin/python3 -m alfa_CR6_test.hardware_free_suite \
  --network -v
```

Dopo l'installazione del package gli stessi comandi sono disponibili tramite
`alfa_CR6_test_hardware_free`.

L'emulatore mantiene i tempi originali per default. Per accelerare soltanto
movimenti, lifter, fotocellule e dispensazione durante un E2E:

```bash
alfa_CR6_emulator --time-scale 0.01
```

La variante seleziona le stesse teste fisiche usate dall'applicazione:

```bash
alfa_CR6_emulator --machine-variant CR4 --time-scale 0.05
alfa_CR6_emulator --machine-variant CRX60 --time-scale 0.05
alfa_CR6_emulator --machine-variant CRX80 --time-scale 0.05
```

In alternativa `--machine-variant` eredita `MACHINE_VARIANT`. CR6 resta il
default. Le mappe avviate sono CR4 `A/F/C/D`, CR6 `A/F/B/E/C/D`, CRX60
`A/B/C` e CRX80 `A/B/C/G`.

Heartbeat websocket e tempi di rete non vengono scalati.

Non usare `unittest discover` sull'intera directory: nel repository sono
presenti anche utility storiche denominate `test_*.py` che accedono a
periferiche reali durante l'import (per esempio lo scanner barcode). L'entry
point usa intenzionalmente una lista esplicita di moduli sicuri.

La lista e' protetta da un meta-test: ogni `test_*.py`, incluse le
sottodirectory, deve essere classificato esattamente una volta come core,
network oppure escluso con una motivazione. Un nuovo modulo dimenticato nel
runner, un'esclusione senza motivo o una voce riferita a un file rimosso fanno
fallire la suite. I moduli esclusi non vengono importati durante il controllo.

## Copertura sostitutiva della macchina

| Area | Verifica automatica | Sostituto hardware |
|---|---|---|
| Testa CR6 | bit delle 11 fotocellule, 4 taglie, stabilizzazione e contact bounce | maschere sensori e clock virtuale |
| Attuatori | lock uscita, timeout watchdog, spegnimento automatico e rifiuto del doppio avvio | log comandi della testa fake |
| Lifecycle testa | supervisione congiunta watchdog/websocket, propagazione guasti, cancellazione e restart | coroutine controllate e websocket fake/loopback |
| Carosello | occupazione posizioni, trasferimento A-B, timeout e arresto rulli | teste e jar fake |
| Sicurezze logiche | pannello aperto e allarme 923 bloccano il movimento | interlock impostabili |
| Tintometro | refresh pigmenti/package, sync, reserve e pesi effettivi | risposte REST in memoria |
| Formula | ripartizione grammi/ml tra piu' teste, disponibilita' e retry | teste pigmento fake |
| Barcode formula | Yoko singolo/doppio, porta USB fisica corretta/errata, lettore mancante, rumore, letture spurie e valide ma assenti dal DB | enumerazione/eventi `evdev` fake e SQLite temporaneo |
| Barcode shuttle | routing separato, lettori scambiati, package noti/ignoti, deduplica normalizzata, rumore e retry dopo risposta REST vuota o eccezione | secondo Yoko, enumerazione USB e package REST fake |
| Barcode CRX | dialoghi manuali shuttle/formula, retry degli input errati e varianti CRX40/60/80 | UI offscreen e testa REST fake |
| E2E ordine-dispensazione | creazione ordine e jar SQLite, filtro barcode, validazione volume, sequenze CR4, CR6, CRX60 e CRX80, guasti barcode/movimento/dispensazione, recovery post-spegnimento, macro su ogni testa attiva e stati finali | `MachineHeadMockup` in-process a `time_scale=0.05`, websocket serializzato per testa, REST tintometro in memoria e prelievo finale CR4/CR6 simulato |
| Stato e database | transizioni jar/order, indici e cleanup a lotti | SQLite temporaneo |
| Parser ordini | doppia mano KCC e persistenza di due ordini | righe/PDF fixture |
| Comunicazione | errori protocollo, broadcast, race comandi e reconnect | websocket fake/loopback |
| API Flask | stato teste, errori filtro e metodi non ammessi | test client, Redis/DB fake |
| Periferiche/UI | allarme sonoro, reminder, lifecycle browser e rendering ordini | filesystem e widget offscreen |

I doppi condivisi sono in `alfa_CR6_test.hardware_fakes`: `VirtualClock`,
`FakeMachineHead` e `FakeJar`. Nuovi test di sequenza devono estendere questi
oggetti invece di introdurre sleep reali o dipendenze dagli indirizzi delle
teste.

L'E2E completo usa invece intenzionalmente il vero `MachineHead` e il vero
`send_command`: il trasporto websocket in-process inoltra i payload a
`MachineHeadMockup`, senza aprire porte. La scala `0.05` e' il minimo usato dal
test per non comprimere un fronte fisico sotto la finestra dei campioni stabili
del polling produttivo.

### Matrice E2E ordine-barcode-dispensazione

I cinque scenari seguenti vengono eseguiti separatamente su CR4, CR6, CRX60 e
CRX80, per un totale di 20 test. Ogni test ricrea database, teste, websocket e
stato fisico, quindi un guasto non puo' contaminare lo scenario successivo.

| Scenario | Iniezione | Risultato verificato |
|---|---|---|
| Ordine corretto | barcode presente nel DB e telemetria nominale | tutte e sole le teste della variante vengono visitate e dispensano; jar e ordine terminano `DONE` |
| Barcode inesistente | barcode Alfa formalmente valido, ma assente da SQLite | nessun comando di movimento o dispensazione; ordine originale e jar restano `NEW`; alert di lookup |
| Errore movimento | eccezione del controller sul primo trasferimento dopo la dispensazione A | A risulta visitata una sola volta; nessuna testa successiva dispensa; jar e ordine terminano `ERROR` nella posizione fisica A |
| Errore dispensazione | allarme 9901 durante la macro sulla testa A, con sblocco operatore simulato | outcome `failure during dispensation`; nessuna seconda testa dispensa; jar viene comunque espulsa e jar/ordine restano `ERROR` |
| Recovery dopo spegnimento | A viene dispensata realmente e salvata come `done`; runner e sessione vengono poi eliminati e ricreati prima di chiamare la vera `machine_recovery()` | A non viene ridispensata; il percorso riparte dalla testa successiva; ordine `DONE`; file `running_jars.json` vuoto; lettura barcode riabilitata |

Nel recovery il confine di spegnimento conserva cio' che sopravvive a un vero
riavvio (SQLite, `running_jars.json` e stato delle fotocellule) e scarta lo
stato volatile (sessione e jar runner). Su CR4/CR6 la recovery termina con la
latta `DONE/OUT`, pronta per il ritiro dell'operatore; su CRX60/80 termina in
`DONE/_`, perche' il percorso lineare non ha il rullo di consegna classico.

### Politica di recovery durante una dispensazione

La sicurezza prevale sulla ripresa automatica. Il controller non espone uno
storico durable e idempotente delle macro: dopo un riavvio il backend non puo'
dedurre dal solo stato corrente se un comando confermato via websocket abbia
gia' erogato materiale. Un caso ambiguo non deve quindi essere
ridispensato automaticamente.

| Punto di interruzione | Marcatore durable osservabile | Informazione disponibile al riavvio | Esito prescritto |
|---|---|---|---|
| Prima di raggiungere una testa | nessuno; la prossima azione e' un movimento | nessun comando di dispensazione puo' essere partito in quella posizione | riprendere il movimento se le fotocellule identificano una sola posizione |
| Prima dell'invio di `DISPENSE_FORMULA` | nessuno; la prossima azione e' `dispense_step` | indistinguibile dalla finestra successiva | marcare jar/ordine `ERROR`, non dispensare, consentire solo l'espulsione da una posizione fisica non ambigua |
| Dopo ACK, prima di osservare `DISPENSING` | nessuno | il comando puo' essere stato accettato senza una prova durable dell'erogazione | stesso esito fail-closed: `ERROR`, mai ridispensare |
| Dopo aver osservato `DISPENSING` | `ongoing` | l'erogazione e' iniziata, ma quantita' e completamento sono ignoti | `ERROR`, mai ridispensare |
| Guasto o allarme durante la macro | `dispensation_failure` | erogazione parziale possibile | `ERROR`, mai ridispensare |
| Dopo `STANDBY`, prima del salvataggio finale | `ongoing` | il completamento osservato era soltanto volatile | `ERROR`, mai ridispensare |
| Dopo il salvataggio finale | `done` | completamento durable della testa corrente | saltare quella dispensazione e riprendere dalla fase successiva |

Un futuro marcatore write-ahead `pending`, scritto prima dell'invio, rende
esplicita la finestra ambigua ma non basta a renderla ripetibile: fino a quando
controller e backend non condividono una chiave idempotente o uno storico
interrogabile, anche `pending` deve terminare in `ERROR` senza ridispensazione.

Gli scenari di fault condividono questi invarianti, verificati in un solo
helper della suite:

- nessuna testa riceve due macro di dispensazione per lo stesso passaggio;
- al termine non restano uscite macchina o task ordine/comando attive;
- ogni record grezzo di `running_jars.json` identifica un jar DB con posizione
  compatibile; i terminali rimossi automaticamente non restano nel file,
  mentre un `ERROR` bloccato per intervento manuale conserva il record;
- una latta non occupa contemporaneamente piu' sensori di posizione;
- al termine di un recovery automatico blocchi UI e recovery sono chiusi e la
  lettura barcode e' riabilitata; un'ambiguita' fisica mantiene invece il
  blocco fino all'intervento dell'operatore.

La matrice completa dei marker viene eseguita su CR6. Le altre varianti
mantengono lo smoke `done -> ripresa senza ridispensazione`, che attraversa le
diverse topologie di uscita senza moltiplicare il runtime del gate per-commit.

Il websocket controllato restituisce subito l'ACK come il controller reale,
ma serializza i comandi diretti alla stessa testa. In questo modo ON/OFF e
macro non possono sovrapporsi in un ordine fisicamente irrealistico; teste
diverse restano indipendenti.

### Guasti di protocollo nel flusso E2E

La fault policy del websocket in-process e' dichiarativa e one-shot: seleziona
comando e, se necessario, parametri, quindi il retry successivo attraversa una
nuova generazione logica di connessione sana. Non simula handshake o pacchetti
TCP; verifica la degradazione dell'intero ordine quando il trasporto presenta
gli stessi esiti osservabili dal backend.

| Scenario | Esito del trasporto | Risultato verificato |
|---|---|---|
| Disconnessione dopo ACK della macro | `DISPENSE_FORMULA` e' confermato, ma sulla nuova connessione non arriva la transizione `DISPENSING` | timeout accelerato, jar/ordine `ERROR`, nessuna ridispensazione, runner concluso e attuatori a riposo |
| Restart con movimento pendente | il comando di avvio del rullo sorgente non riceve risposta; non e' noto se sia arrivato al controller | stop esplicito di entrambi i rulli, errore mostrato all'operatore, retry sulla connessione sana e ordine completato senza doppia dosata |

I timeout forzati sono limitati alle attese esatte coinvolte nel fault; polling,
movimenti e dispensazioni successivi mantengono i tempi scalati dell'emulatore.
Risposte duplicate e fuori ordine restano nei test mirati di `send_command`,
perche' a livello E2E non aggiungerebbero un diverso esito di sistema.

## Collaudi che restano sulla macchina reale

La suite non puo' certificare:

- polarita', cablaggio, deriva e rumore elettrico delle fotocellule;
- inerzia, attrito, allineamento e tempi fisici di rulli e lifter;
- accuratezza volumetrica, pressione, spurgo e qualita' della tinta;
- catena di sicurezza elettrica, emergenza, porte e ripartenza dopo blackout;
- enumerazione USB effettiva di scanner/stampante e resa del display;
- comportamento con firmware non rappresentato dai payload registrati.

Queste prove vanno mantenute come checklist HIL di rilascio. Quando una prova
reale trova un difetto software, prima della correzione va aggiunto un payload
o uno scenario deterministico alla suite hardware-free: in questo modo la
stessa prova non deve essere ripetuta manualmente a ogni release.

## Gate consigliati

1. Ogni commit: suite rapida.
2. Nightly o pre-merge: suite con `--network` e test parser su fixture cliente.
3. Release: checklist HIL ridotta ai soli punti fisici elencati sopra.
