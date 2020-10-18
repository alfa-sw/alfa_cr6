## ALFA CR6 1.0.0 

### Prerequisiti per la esecuzione del pacchetto (sia sui target che su host):

1. sistema linux con installati i pacchetti debian 
    * python3
    * python3-pyqt5

2. un virtualenv nel path "/opt/alfa_cr6/", i.e. creato con:

    $ virtualenv -p /usr/bin/python3 /opt/alfa_cr6/venv

### Prerequisiti per lo sviluppo (su host):
    
1. "Prerequisiti per la esecuzione del pacchetto",
2. clone del progetto in ${PROJECT_ROOT}

### Build su host: (creazione del pacchetto wheel in ${PROJECT_ROOT}/dist)

    host$ cd ${PROJECT_ROOT}
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ python setup.py bdist_wheel

### Install in edit-mode per sviluppo su host:

NOTA: VERSION_NUMBER e' il n. di versione contenuto nel file setup.py.

    host$ cd ${PROJECT_ROOT}
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ pip install -e ${PROJECT_ROOT} ${PROJECT_ROOT}/dist/alfa_CR6-VERSION_NUMBER-py3-none-any.whl

### Install su target:

    host$ scp user@host:${PROJECT_ROOT}/dist/alfa_CR6-VERSION_NUMBER-py3-none-any.whl user@target:${DEPLOY_PATH}
    target$ . /opt/alfa_cr6/venv/bin/activate
    target$ pip install ${DEPLOY_PATH}/alfa_CR6-VERSION_NUMBER-py3-none-any.whl

### Run su target e host:

    $ . /opt/alfa_cr6/venv/bin/activate
    $ alfa_cr6

### credenziali vuote login

username: "", password: ""

### Cleanup automatico codice

1. autoflake <files> --remove-all-unused-imports --remove-unused-variables
2. autopep8 <files> --aggressive --aggressive
