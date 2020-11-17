# alfa_CR6 (Python Package for Supervisor Application of alfa CR6 - Car Refinishing System)

#### A. Prerequisiti per la esecuzione del pacchetto (sia su target che su host):

1. sistema linux con installati i pacchetti debian: 
    * python3
    * virtualenv
    * python3-pyqt5
    * python3-pyqt5.qtwebengine
    * python3-evdev [readthedocs](https://python-evdev.readthedocs.io)  (barcode reader and virt kb)

comando:

    $ apt install -y python3 virtualenv python3-pyqt5 python3-pyqt5.qtwebengine python3-evdev

2. permessi di accesso in lettura ai /dev/input all'utente che esegue l'applicazione, per l'accesso al 
lettore di barcode e in scrittura a /dev/uinput per la virt. kb.
    
aggiungi lo user [NOME_UTENTE] al gruppo "input" e cambia gruppo e permissions al dev "/dev/uinput":

    $ sudo usermod -a -G input [NOME_UTENTE]
    $ sudo chgrp input /dev/uinput
    $ sudo chmod 770 /dev/uinput

3. un virtualenv nel path "/opt/alfa_cr6/venv", con accesso ai pacchetti di sistema.

crea con:

    $ mkdir /opt/alfa_cr6                              
    $ virtualenv --system-site-packages -p /usr/bin/python3 /opt/alfa_cr6/venv


#### B. Prerequisiti per lo sviluppo (su host):

1. "Prerequisiti per la esecuzione del pacchetto"
    .

2. clone del progetto in ${PROJECT_ROOT}
    .

#### C. Build su host: (creazione del pacchetto wheel in ${PROJECT_ROOT}/dist)

1. build the wheel 

**NOTA**: il n. di versione e' derivato dal contenuto nel file `${PROJECT_ROOT}/__version__`.

comandi:

    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ python setup.py bdist_wheel      

#### D. Install:

**NOTA BENE**: Per la installazione occorre, oltre a pip-installare il pacchetto, copiare 
sul sistema target, nel path "/opt/alfa_cr6/conf/settings.py", il file di 
settings, oppre, nel caso di "install in edit mode", creare un link simbolico:

1. install in edit mode su host per sviluppo:

comandi:

    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ pip uninstall -y alfa_CR6        
    host$ pip install -e ${PROJECT_ROOT}   
    host$ ln -s ${PROJECT_ROOT}/conf/settings.py /opt/alfa_cr6/conf/settings.py

2. install su target:

**NOTA**: [VERSION_NUMBER] e' il n. di versione contenuto nel file `${PROJECT_ROOT}/__version__`.

comandi:

    host$ scp user@host:${PROJECT_ROOT}/dist/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl user@target:${DEPLOY_PATH} 
    host$ scp user@host:${PROJECT_ROOT}/conf/settings.py user@target:/opt/alfa_cr6/conf/settings.py
    target$ . /opt/alfa_cr6/venv/bin/activate                                                                       
    target$ pip install ${DEPLOY_PATH}/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl
                                   

#### E. Run:

1. run  su target e host:

lancia con:

    $ . /opt/alfa_cr6/venv/bin/activate ; alfa_CR6                         

username: "", password: ""

#### F. Run test suite:

1. run test su target e host:

lancia con:

    $ . /opt/alfa_cr6/venv/bin/activate ; alfa_CR6_test [OPTION]                        

per i valori di [OPTION] vedi "src/alfa_CR6_test/main.py".

#### G. Code styling and linting

1. [autopep8](https://pypi.org/project/autopep8):

modifica con:

    $ autopep8 -a -a -a -i --max-line-length 120 $(FilePath)
    
2. [pylint](https://pypi.org/project/pylint): 

controlla con:

    $ pylint3 -f parseable $(FilePath)

    see also pylint directives embedded in source files 
