# Popup del rabbocco con bilancia: S01-S19

Data analisi: 17 settembre 2026

## Ambito e origine dei dati

Le sigle da S01 a S19 sono identificatori usati nelle anteprime grafiche e non
codici di errore mostrati dall'applicazione.

- La pagina `/settings` abilita il flusso con
  `ENABLE_REFILL_BY_SCALE` e il layout ingrandito con
  `ENABLE_REFILL_BY_SCALE_LARGE_MESSAGE_LAYOUT`, ma non genera direttamente
  quasi nessuno degli errori descritti di seguito.
- I dati di prodotto e circuito arrivano da `apiV1/pigment`.
- La configurazione delle unità arriva da `apiV1/config`.
- Per "modifica DB" si intende quindi una modifica al database/backend che
  alimenta questi endpoint, seguita dall'aggiornamento dei dati della testa.
- Il database locale degli eventi non influenza questi popup.

## Quadro riassuntivo

| ID | Tipo | Significato | Riproduzione principale |
|---|---|---|---|
| S01 | Richiesta operativa | Avvio del rabbocco con bilancia | Settings e operatore |
| S02 | Errore configurazione/scansione | Barcode non associato a prodotti validi | Barcode o DB |
| S03 | Selezione | Più circuiti associati allo stesso barcode | DB |
| S04 | Errore operativo | Automazione non in pausa | Stato macchina |
| S05 | Errore operativo | Testa non disponibile | Stato macchina |
| S06 | Errore operativo | Uscite o operazione attive | Stato macchina |
| S07 | Errore bilancia/comunicazione | Peso stabile non disponibile | Hardware o comunicazione |
| S08 | Errore movimento/comunicazione | Circuito non posizionato | Hardware o comunicazione |
| S09 | Richiesta operativa | Verifica barcode sul circuito | Flusso normale |
| S10 | Errore preparazione | Eccezione imprevista prima del rabbocco | DB corrotto o codice |
| S11 | Errore operatore | Barcode diverso da quello iniziale | Scansione |
| S12 | Istruzione operativa | Esecuzione fisica del rabbocco | Flusso normale |
| S13 | Esito positivo | Rabbocco completato entro il massimo | Flusso normale |
| S14 | Esito con avvertimento | Rabbocco superiore al massimo | Quantità fisica o DB |
| S15 | Errore visualizzazione | Risultato ricevuto ma non elaborabile | Configurazione, dati o codice |
| S16 | Errore misura | Quantità rabboccata minore o uguale a zero | Operatore o bilancia |
| S17 | Errore configurazione prodotto | Peso specifico non valido | DB |
| S18 | Errore comunicazione | Comando `REFILL` non inviato | Connessione o testa |
| S19 | Errore interno generico | Eccezione imprevista finale | Codice o stato incoerente |

## S01 - Posizionamento iniziale

```text
Posizionare il barattolo aperto sulla bilancia.
Scansionare il codice a barre.
```

Questa è la schermata iniziale, non un errore.

Per riprodurla:

1. impostare `ENABLE_REFILL_BY_SCALE = true`;
2. avere `USE_PIGMENT_ID_AS_BARCODE = true`;
3. mettere in pausa l'automazione;
4. premere il comando di rabbocco della testa.

`ENABLE_REFILL_BY_SCALE_LARGE_MESSAGE_LAYOUT` modifica soltanto l'aspetto.

Categoria: **settings e flusso normale**.

## S02 - Prodotto non configurato

```text
Il codice a barre scansionato non corrisponde
ad alcun prodotto configurato in macchina.
```

Compare quando non viene trovato nessun circuito che soddisfi
contemporaneamente queste condizioni:

- `pigment.customer_id == barcode`;
- circuito `enabled`;
- circuito `sync`.

Riproduzione:

- scansionare un barcode inesistente;
- modificare `customer_id`;
- disabilitare tutti i circuiti associati;
- impostare `sync = false` su tutti i circuiti associati.

Categoria: **operatore o dati backend/DB**.

## S03 - Prodotto su più circuiti

```text
Il prodotto è configurato su più circuiti.

Scegliere il circuito da rabboccare:
```

Compare quando lo stesso barcode identifica più circuiti validi.

Riproduzione DB:

- assegnare lo stesso `customer_id` a più pigmenti;
- oppure configurare più circuiti `enabled = true` e `sync = true` sullo
  stesso pigmento.

Può coinvolgere circuiti della stessa testa o di teste differenti.

Categoria: **configurazione backend/DB**, non errore.

## S04 - Automazione non in pausa

```text
Mettere in pausa l'automazione prima di avviare il rabbocco.
```

Compare se `carousel_frozen` è falso durante la preparazione.

Normalmente il pulsante di rabbocco è utilizzabile solo ad automazione ferma.
Il caso più realistico è:

1. avviare il flusso mentre l'automazione è in pausa;
2. riattivare l'automazione prima della selezione o preparazione del circuito.

Si può riprodurre anche impostando programmaticamente:

```python
QApplication.instance().carousel_frozen = False
```

Categoria: **stato operativo**, non DB.

## S05 - Testa non pronta

```text
La testa A non è pronta per il rabbocco.
```

Compare quando `machine.status["status_level"]` non è né `STANDBY` né
`DIAGNOSTIC`. Anche un `status_level` assente produce S05.

Riproduzione:

- testa in allarme;
- testa offline o non inizializzata;
- stato `BUSY`, `ERROR` o equivalente;
- manipolazione della telemetria `machine.status`.

Categoria: **stato live della testa**, non settings/DB.

## S06 - Operazione in corso

```text
La testa A ha un'operazione in corso.
```

Per raggiungere questo popup, lo stato deve essere `STANDBY` o `DIAGNOSTIC`,
ma deve risultare:

```python
int(status["crx_outputs_status"]) != 0
```

Un valore assente, non numerico o non convertibile viene trattato
prudenzialmente come "operazione in corso".

Riproduzione:

- attivare un'uscita della testa;
- lasciare un movimento o un comando in corso;
- impostare `crx_outputs_status` a un valore diverso da zero;
- fornire uno stato non valido.

Categoria: **stato hardware o telemetria**.

## S07 - Peso stabile non disponibile

```text
Impossibile leggere un peso stabile
dalla bilancia.
```

Può comparire durante la pesata iniziale o durante quella finale dopo il
rabbocco.

Condizioni:

- timeout;
- connessione assente;
- risposta mancante;
- `status_code != 0`;
- comando di risposta differente da `STABLE_WEIGHT`;
- parametri mancanti o malformati;
- unità diversa da `g`;
- peso non numerico;
- peso `NaN` o infinito.

Riproduzione:

- scollegare la bilancia;
- impedire la stabilizzazione del peso;
- simulare un timeout;
- simulare una risposta come:

```python
{"status_code": 0, "command": "STABLE_WEIGHT", "params": ["abc", "g"]}
```

Categoria: **bilancia, comunicazione o risposta hardware**.

## S08 - Circuito non posizionato

```text
Impossibile posizionare il circuito di rabbocco.
```

La pesata iniziale è riuscita, ma il comando
`DIAG_ROTATING_TABLE_POSITIONING` ha restituito un risultato falso o è
scaduto.

Riproduzione:

- bloccare la tavola rotante;
- provocare un timeout;
- scollegare la testa dopo la pesata iniziale;
- simulare `send_command(...) -> None/False`.

Un nome circuito formalmente errato non produce S08: genera normalmente S10.

Categoria: **movimento, hardware o comunicazione**.

## S09 - Verifica del circuito

```text
Scansionare il codice a barre presente sul circuito B01
della testa A.
```

Compare dopo che sono stati superati i controlli della testa, la pesata
iniziale e il posizionamento. Serve a verificare che l'operatore stia
rabboccando il circuito associato al barattolo.

Categoria: **notifica operativa normale**.

## S10 - Preparazione non riuscita

```text
Preparazione del rabbocco non riuscita:
<dettaglio>
```

È il fallback generico della fase di preparazione, equivalente a S19 ma
precedente al rabbocco.

Un caso DB facilmente riproducibile è un nome circuito non valido:

```text
X01
B09
C25
B1
```

Sono validi solamente `B01-B08` e `C01-C24`.

Esempio risultante:

```text
Preparazione del rabbocco non riuscita:
invalid pipe name: X01
```

Altri casi:

- campo `pipe["name"]` mancante;
- struttura di `machine.status` inattesa;
- oggetto macchina o circuito incoerente;
- eccezione imprevista dalla bilancia o dal comando di movimento;
- errore interno durante l'apertura del popup.

Categoria: **dati backend/DB corrotti oppure errore interno**.

## S11 - Barcode differente

```text
Il codice a barre non corrisponde:
<barcode atteso> != <barcode scansionato>
```

Può comparire durante la scansione del barcode sul circuito oppure durante la
scansione finale del barattolo rimesso sulla bilancia.

Riproduzione:

1. avviare il flusso con un barattolo;
2. scansionare successivamente un barcode differente.

Categoria: **errore operativo o di scansione**.

## S12 - Istruzione di rabbocco

```text
Rimuovere il barattolo dalla bilancia e procedere con il rabbocco.
Al termine, riporre il barattolo sulla bilancia e scansionare il codice a barre.
```

È l'istruzione principale del flusso, non un errore. Compare dopo la corretta
verifica del barcode sul circuito.

Categoria: **notifica operativa normale**.

## S13 - Rabbocco completato correttamente

Esempio:

```text
Quantità rabboccata: 742,35 g
livelli aggiornati: B01: 618,62 (cc)
Eseguire il RESET della testa A?
```

Mostra:

- differenza tra peso iniziale e finale;
- livelli restituiti dalla macro `REFILL`, se presenti;
- unità di servizio configurata;
- richiesta di reset della testa.

È S13 quando:

```python
refill_cc <= max(0, maximum_level - current_level)
```

Riproduzione:

- effettuare un rabbocco reale;
- fare in modo che la quantità misurata resti entro la capacità residua;
- ricevere una risposta valida dalla macro `REFILL`.

I livelli visualizzati dipendono dalla risposta della testa e non sono sempre
presenti.

Categoria: **esito positivo normale**; i valori dipendono da bilancia, DB e
risposta della testa.

## S14 - Rabbocco superiore al massimo

Contiene le informazioni di S13 e inoltre:

```text
Attenzione: il rabbocco misurato supera
il livello massimo configurato.
```

Condizione:

```python
refill_cc > max(0, maximum_level - current_level)
```

Riproduzione operativa:

- versare più prodotto della capacità residua.

Riproduzione DB:

- aumentare `current_level`;
- diminuire `maximum_level`;
- configurare `current_level > maximum_level`;
- utilizzare un peso specifico che converta la differenza in un volume
  maggiore.

È un avvertimento: il comando `REFILL` è già stato inviato.

Categoria: **esito positivo con anomalia quantitativa**, riproducibile
fisicamente o tramite dati backend/DB.

## S15 - Risultato non visualizzabile

```text
Impossibile visualizzare il risultato del rabbocco.
```

La macro `REFILL` ha risposto, ma `_show_result()` ha generato un'eccezione.

Riproduzioni tramite configurazione o dati:

- `service_page_unit = "ML"` o altra unità non supportata;
- `service_page_unit = "FL OZ"` con `fl_oz_unit` o `fl_oz_fraction`
  negativi o `NaN`;
- valore di livello restituito dalla testa non numerico;
- `current_level` o `maximum_level` non numerico;
- risposta della macro con struttura inattesa;
- configurazione `UNITS` con struttura non valida.

Esempio di risposta problematica:

```python
{"adjusted_levels": {"B01": "non-numerico"}}
```

Il dettaglio tecnico viene scritto nel log ma non mostrato.

Categoria: **configurazione macchina, risposta hardware, dati backend/DB o
errore interno**.

## S16 - Quantità misurata non positiva

```text
Il rabbocco misurato deve essere
maggiore di zero grammi.
```

Calcolo:

```python
refilled_grams = initial_weight - final_weight
```

Compare quando il peso finale è uguale o superiore al peso iniziale.

Riproduzione:

- non prelevare prodotto dal barattolo;
- aggiungere peso al barattolo;
- scambiare il barattolo con uno più pesante;
- simulare pesata iniziale `1000 g` e finale `1000 g` o `1100 g`.

Categoria: **errore operativo o misura fisicamente incoerente**.

## S17 - Peso specifico non valido

```text
Il peso specifico del prodotto non è valido.
```

Il codice prova, nell'ordine:

1. `pipe["effective_specific_weight"]`;
2. `pigment["specific_weight"]`.

È sufficiente che uno dei due sia numerico, finito e maggiore di zero. Per
generare S17 devono essere entrambi:

- assenti;
- non numerici;
- minori o uguali a zero;
- `NaN` o infiniti.

Riproduzione DB:

```python
pipe["effective_specific_weight"] = 0
pigment["specific_weight"] = 0
```

Serve inoltre una differenza di peso positiva, altrimenti compare prima S16.

Categoria: **configurazione prodotto o circuito backend/DB**.

## S18 - Livello non aggiornato

```text
Impossibile aggiornare il livello del prodotto.
```

Compare quando l'invio della macro `REFILL` restituisce `None` o `False`.

Cause:

- websocket della testa assente;
- connessione chiusa;
- errore di serializzazione o invio;
- errore interno intercettato da `send_command`;
- macchina non raggiungibile nel momento dell'invio.

Per riprodurlo specificamente bisogna:

1. completare con successo la pesata finale;
2. interrompere la connessione prima dell'invio di `REFILL`;

oppure simulare:

```python
machine.send_command(...) -> False
```

Se la connessione viene interrotta prima della pesata finale, comparirà S07
invece di S18.

Categoria: **comunicazione o disponibilità della testa**.

## S19 - Errore interno finale

```text
Rabbocco non riuscito:
<dettaglio dell'errore>
```

È l'ultimo `except Exception` del completamento.

Possibili categorie:

- `machine_`, `pipe_` o `pigment_` incoerenti;
- tipi dati inattesi;
- campo `pipe["name"]` mancante;
- peso iniziale non numerico;
- funzione o driver che solleva un'eccezione non intercettata;
- regressione software;
- stato modificato mentre il flusso è già in corso.

Non è normalmente producibile dalla pagina `/settings`.

Una semplice configurazione DB errata tende a produrre:

- S10 per nome circuito errato;
- S15 per livelli o unità errati;
- S17 per peso specifico errato.

Per ottenere S19 tramite dati sarebbe necessaria una corruzione molto anomala
o una modifica dello stato in memoria durante il flusso. La riproduzione
affidabile richiede fault injection o mocking.

Categoria: **errore interno o stato fortemente incoerente**.

## Riepilogo per metodo di riproduzione

- Tramite `/settings`: abilita il flusso e il layout; non genera direttamente
  S02-S19.
- Tramite dati backend/DB: S02, S03, S10, S13, S14, S15 e S17.
- Tramite azioni dell'operatore: S04, S11, S14 e S16.
- Tramite stato macchina, hardware o comunicazione: S05, S06, S07, S08, S15
  e S18.
- Tramite errore interno o fault injection: soprattutto S10, S15 e S19.

## Riferimenti al codice

- Flusso completo: `src/alfa_CR6_frontend/home_page.py`, classe
  `ScaleRefillProcedureHelper`.
- Attivazione del flusso: `src/alfa_CR6_frontend/home_page.py`, metodo
  `refill_lbl_clicked()`.
- Impostazioni: `src/alfa_CR6_backend/settings_manager.py`.
- Conversione delle quantità: `src/alfa_CR6_backend/refill_utils.py`.
- Lettura stabile e invio comandi: `src/alfa_CR6_backend/machine_head.py`.
- Traduzioni italiane: `src/alfa_CR6_backend/lang/it.py`.
