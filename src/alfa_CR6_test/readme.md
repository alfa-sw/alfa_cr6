# Eseguire i test di alfa_CR6

Eseguire i comandi dalla **directory principale del repository**, quella che
contiene `src`, usando un ambiente virtuale con le dipendenze dell'applicazione,
incluse quelle Qt.

Negli esempi:

- `PYTHONPATH=src` carica il codice del checkout corrente.
- `QT_QPA_PLATFORM=offscreen` consente ai test Qt di creare widget senza aprire
  finestre sul desktop.
- `-v` mostra il nome e l'esito di ogni test.

## Percorso dell'interprete Python

`/opt/alfa_cr6/venv/bin/python` e' il percorso dell'ambiente virtuale usato
sulla macchina dello sviluppatore. **Non e' un percorso obbligatorio del
progetto**: sostituirlo con quello del proprio ambiente virtuale.

In alternativa, dopo aver attivato il proprio ambiente, usare `python`:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  python -m unittest alfa_CR6_test.test_home_step_blink -v
```

## Lampeggio delle icone di transito: rm616

Esempio completo con il percorso dell'interprete dello sviluppatore:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  /opt/alfa_cr6/venv/bin/python -m unittest \
  alfa_CR6_test.test_home_step_blink -v
```

Il modulo verifica icone e timer Qt reali, con controller e input operatore
simulati. Comprende errori sovrapposti, rilascio selettivo delle richieste,
cancellazione dei task, tentativi ripetuti ed eccezioni durante il disegno.

Tre scenari usano anche il codice reale del trasferimento e dell'attesa della
fotocellula, con orologio virtuale:

- Un'altra testa entra in allarme prima del timeout: l'attesa scade anche
  durante la pausa, viene attivato il blink e compare il popup specifico
  `barcode:... error in move_... I will retry`, anche se un altro errore
  aveva gia' mostrato un popup. La conferma del nuovo messaggio mantiene
  la pausa precedente; la ripartenza richiede lo sblocco esplicito.
- Il barattolo arriva prima del timeout mentre la macchina e' in pausa:
  il trasferimento riesce senza attivare il blink.
- Il task viene cancellato dopo il timeout: il blink si spegne e la pausa
  dovuta all'altro allarme rimane attiva.

Per eseguire soltanto uno scenario:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  python -m unittest \
  alfa_CR6_test.test_home_step_blink.TestCarouselStepBlink.test_transfer_timeout_during_other_alarm_blinks_until_explicit_resume \
  -v
```

Questi test non richiedono una macchina CR6, connessioni alle teste o il
trascorrere reale dei 45 secondi di timeout. Verificano la logica software;
risposta del firmware, sensori e movimenti fisici richiedono il collaudo reale.

## Altri moduli senza hardware

Sostituire il nome del modulo nel comando seguente, usando il proprio Python:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  python -m unittest alfa_CR6_test.test_status_guard -v
```

| Modulo | Cosa verifica |
|---|---|
| `alfa_CR6_test.test_status_guard` | Transizioni di stato di ordini e barattoli, conservazione degli stati `DONE` e `ERROR` e cancellazione del barattolo in ingresso. |
| `alfa_CR6_test.test_home_autorecovery_blink` | Indicazione lampeggiante dell'autorecovery sui pulsanti di stato delle teste. |
| `alfa_CR6_test.test_autorecovery_interlock` | Blocco delle nuove lavorazioni durante autorecovery o stato testa non verificato e ripartenza esplicita. |
| `alfa_CR6_test.test_debug_page_unfreeze` | Controlli di sblocco del carosello dalla Home e dal Debug. |
| `alfa_CR6_test.test_carousel_hardware_free` | Attese, occupazione delle posizioni, trasferimenti e arresto delle uscite durante il cleanup. |
| `alfa_CR6_test.test_application_hardware_free` | Calcoli applicativi, disponibilita' dei pigmenti e lifecycle delle teste. |

## Eseguire una selezione di moduli insieme

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  python -m unittest \
  alfa_CR6_test.test_status_guard \
  alfa_CR6_test.test_home_step_blink \
  alfa_CR6_test.test_home_autorecovery_blink \
  alfa_CR6_test.test_carousel_hardware_free \
  alfa_CR6_test.test_application_hardware_free \
  alfa_CR6_test.test_debug_page_unfreeze \
  alfa_CR6_test.test_autorecovery_interlock \
  -v
```

Il riepilogo finale `OK` indica che la selezione e' passata. `FAIL` identifica
un'asserzione non soddisfatta; `ERROR` nel riepilogo identifica un'eccezione
non gestita dal test. Alcuni scenari di guasto producono intenzionalmente log
con livello `ERROR`: valutarli insieme al risultato finale di `unittest`.

## Suite completa ed emulatore

La [guida ai test senza hardware](../../doc/TEST_HARDWARE_FREE.md) descrive
il runner `alfa_CR6_test.hardware_free_suite`, l'opzione per i test websocket
su loopback e l'emulatore delle teste `alfa_CR6_emulator`.

Per l'esecuzione complessiva usare il runner documentato, evitando
`unittest discover` sull'intera directory: alcune utility storiche con nome
`test_*.py` accedono a periferiche reali durante l'importazione.
