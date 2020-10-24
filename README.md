# alfa_CR6 (Python Package for Supervisor Application of alfa CR6 - Car Refinishing System)

#### A. Prerequisiti per la esecuzione del pacchetto (sia su target che su host):

1. sistema linux con installati i pacchetti debian: 
    * python3
    * virtualenv
    * python3-pyqt5
    * python3-pyqt5.qtwebengine
    * python3-evdev [readthedocs](https://python-evdev.readthedocs.io)  (barcode reader)

	$ apt install -y python3 virtualenv python3-pyqt5 python3-pyqt5.qtwebengine python-evdev

2. permessi di accesso ai /dev/input all'utente che esegue l'applicazione, per l'accesso al lettore di barcode.
    Su Ubuntu, il comando:

    $ sudo usermod -a -G input [NOME_UTENTE]

    aggiunge lo user [NOME_UTENTE] al gruppo "input", che ha i permessi voluti.

3. un virtualenv nel path "/opt/alfa_cr6/venv", con accesso ai pacchetti di sistema, i.e. creato con:

    $ mkdir /opt/alfa_cr6                              
    $ virtualenv --system-site-packages -p /usr/bin/python3 /opt/alfa_cr6/venv


#### B. Prerequisiti per lo sviluppo (su host):
    
1. "Prerequisiti per la esecuzione del pacchetto"
    .

2. clone del progetto in ${PROJECT_ROOT}
    .

#### C. Build su host: (creazione del pacchetto wheel in ${PROJECT_ROOT}/dist)

1. build the wheel 

	NOTA: il n. di versione e' derivato dal contenuto nel file `${PROJECT_ROOT}/__version__`.

	host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ python setup.py bdist_wheel      

#### D. Install:

1. install in edit mode su host per sviluppo:

    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ pip uninstall -y alfa_CR6        
    host$ pip install -e ${PROJECT_ROOT}   

1. install su target:

	NOTA: [VERSION_NUMBER] e' il n. di versione contenuto nel file `${PROJECT_ROOT}/__version__`.

    host$ scp user@host:${PROJECT_ROOT}/dist/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl user@target:${DEPLOY_PATH}  
    target$ . /opt/alfa_cr6/venv/bin/activate                                                                       
    target$ pip install ${DEPLOY_PATH}/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl                                   

#### E. Run:

1. run  su target e host

    $ . /opt/alfa_cr6/venv/bin/activate
    $ alfa_CR6                         

    username: "", password: ""


#### F. Code styling and linting

1. [autopep8](https://pypi.org/project/autopep8):

    $ autopep8 -a -a -a -i --max-line-length 120 $(FilePath)
    
2. [pylint](https://pypi.org/project/pylint): 

    $ pylint3 -f parseable $(FilePath)

	see also pylint directives embedded in source files 
