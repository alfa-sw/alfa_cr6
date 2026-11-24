##### Toner duplicati negli ordini (BASF Linea 90)

L'opzione `MERGE_DUPLICATE_ORDER_INGREDIENTS`, disponibile nella pagina Settings,
è disattivata per impostazione predefinita. Abilitarla sulle macchine che devono
accettare ricette con lo stesso toner ripetuto, come quelle BASF Linea 90.

Quando è attiva, alla creazione dell'ordine le righe con lo stesso `pigment_name`
vengono accorpate sommando le quantità in grammi, dopo la conversione degli alias.
Si conservano la posizione e i dati descrittivi della prima riga. Il database
salva la ricetta accorpata; il file originale e gli ordini già salvati restano
invariati. L'opzione vale per tutti gli ordini creati sulla macchina su cui è
abilitata, senza un filtro automatico sulla linea di prodotto.

Per provare l'importazione sono disponibili in `src/alfa_CR6_test/fixtures/`:

- `formula_sample.json`: campione senza duplicati, identico a quello presente
  nei test installati sulla macchina BASF raggiungibile via VPN.
- `formula_sample_duplicate_toner.json`: variante dello stesso campione con
  `C10` diviso in due righe da 10 g e 2,3347 g, per un totale invariato di 12,3347 g.

Il test `TestDuplicateOrderIngredients.test_vpn_json_samples_with_enabled_disabled_and_missing_option`
verifica entrambi i file con l'opzione attiva, disattivata e assente. Il campione
senza duplicati viene sempre accettato; quello con duplicati viene accorpato
solo con l'opzione attiva. I test usano un database temporaneo, senza hardware.

##### Ordini Color Communications in formato DCI

I file `.dci` contengono ricette in formato INI, con sezioni `[FORMULA1]`,
`[INGREDIENTS1]` e `[SUMMARY]`. Il campo `TotalFormulas` indica quante ricette
importare: ogni coppia `FORMULAn` / `INGREDIENTSn` genera un ordine distinto.

I nomi completi dei pigmenti vengono mantenuti, comprese maiuscole e minuscole.
Le quantità sono espresse in grammi (`DispenseUnit=G`); vengono conservate anche
le righe con quantità zero. La base indicata in `Base` viene aggiunta agli
ingredienti con il peso specificato in `BaseAmount`, mantenendone la precisione.
Se `Base` è vuoto (`Base=`) o assente, si importano soltanto tutte le righe di
`INGREDIENTSn`, ignorando `BaseAmount`. Quando la base è indicata, il suo peso
deve essere finito e positivo. Le quantità dei coloranti devono essere finite
e non negative, e il loro numero deve coincidere con `NumColorants`.

Sono disponibili i seguenti campioni:

- `dci_charleston.dci`: ricetta `CHARLESTON GRAY 243`, con 20 coloranti e la base
  `CCI-A Gloss Clear` da 15,51952 g. Verifica anche la rimozione del nome colore
  dalla fine di `CollectionName`, evitando di ripeterlo nell'etichetta.
- `dci_test1.dci`: ricetta `test 1`, con 20 coloranti (13 a quantità zero) e la
  stessa base da 5 g, per un totale di 10,985 g. In questo caso il nome colore
  non compare alla fine di `CollectionName`, che viene quindi mantenuto intero.
- `dci_adirondack_no_base.dci`, `dci_chatsworth_no_base.dci` e
  `dci_charleston_no_base.dci`: nuovi file ricevuti con `Base=` e `BaseAmount=0`.
  Devono importare rispettivamente 6, 10 e 20 ingredienti, comprese tutte le
  righe a zero, senza aggiungere una base.

La suite `DciOrderTests`, in `src/alfa_CR6_test/test_dci_order.py`, verifica
l'importazione dei campioni, i file con più ricette, i dati non validi e la
stampa delle quattro righe descrittive dell'etichetta. Controlla anche il ritorno
a capo dei testi lunghi e la stampa singola e in gruppo, senza stampante reale.

Per eseguirla dalla radice del repository:

```sh
PYTHONPATH=src /opt/alfa_cr6/venv/bin/python -m unittest -v alfa_CR6_test.test_dci_order
```
