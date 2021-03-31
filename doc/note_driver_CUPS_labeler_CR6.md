# Note per installazione driver CUPS

La piattaforma "supervisore" della CR6 dovrà stampare una LABEL contente alcune informazioni (tra cui BARCODE EAN13, codice colore, etc..):
la stampante di etichette scelta è la DYMO 450.
Sfortunatamente non esiste una SDK ufficiale dedicata per Linux (solo per Win e MacOS): occorre quindi utilizzare i driver CUPS.

link: https://ubuntu.com/server/docs/service-cups

#### Install Printer Drivers

<pre>
$ sudo apt-get update
$ sudo apt-get install -y cups printer-driver-dymo
$ sudo usermod -aG lpadmin username
</pre>


#### Configure DYMO LabelWriter 450

occorre impostare la stampante attraverso la pagina web di CUPS server:

http://localhost:631/admin

1. selezionare dalla barra menù la voce "Administration" e cliccare sul pulsante "Add Printer"

2. autenticarsi come <superutente> (o come utente con permessi)

3. selezionare la voce DYMO LabelWriter 450 da Local Printers

4. nella pagina successiva premere il pulsante "Continue"

5. nella voce "Model" selezionare la voce LabelWriter 450 (en) e premere "Add Printer"

6. nella pagina successiva, occorre selazionare sia il Media Size (tipologia label) sia la Print Quality.

Media Size -> 11352 Return Address Int

Output Resolution -> 300x600 DPI

Print Quality -> Barcodes and Graphics

7. infine premere il pulsante "Set Default Options"

#### Setup default OS printer

get printer list

$ lpstat -p

setup default printer

$ lpoptions -d DYMO_LabelWriter_450

#### NOTES

for more detailed info visit:
https://packages.debian.org/sid/printer-driver-dymo 
https://johnathan.org/configure-a-raspberry-pi-as-a-print-server-for-dymo-label-printers/
