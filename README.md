## alfa_CR6

### UI for alfa CR6

#### 1. Prerequisiti per la esecuzione del pacchetto (sia su target che su host):

1. sistema linux con installati i pacchetti debian: 
    * python3
    * virtualenv
    * python3-pyqt5
    * python3-pyqt5.qtwebengine

    $ apt install -y python3 virtualenv python3-pyqt5 python3-pyqt5.qtwebengine

2. un virtualenv nel path "/opt/alfa_cr6/venv", con accesso ai pacchetti di sistema, i.e. creato con:

    $ mkdir /opt/alfa_cr6                              
    $ virtualenv --system-site-packages -p /usr/bin/python3 /opt/alfa_cr6/venv

#### 2. Prerequisiti per lo sviluppo (su host):
    
1. "Prerequisiti per la esecuzione del pacchetto",
2. clone del progetto in ${PROJECT_ROOT}

#### 3. Build su host: (creazione del pacchetto wheel in ${PROJECT_ROOT}/dist)

    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ python setup.py bdist_wheel      

#### 4. Install in edit-mode per sviluppo su host:

    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ pip uninstall -y alfa_CR6        
    host$ pip install -e ${PROJECT_ROOT}   

#### 5. Install su target:

NOTA: [VERSION_NUMBER] e' il n. di versione contenuto nel file `${PROJECT_ROOT}/__version__`.

    host$ scp user@host:${PROJECT_ROOT}/dist/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl user@target:${DEPLOY_PATH}
    target$ . /opt/alfa_cr6/venv/bin/activate                                                                     
    target$ pip install ${DEPLOY_PATH}/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl                                 
                                                                                                                   
#### 6. Run su target e host:

    $ . /opt/alfa_cr6/venv/bin/activate
    $ alfa_CR6                         

username: "", password: ""


#### 7. Code styling and linting

1. [autopep8](https://pypi.org/project/autopep8):

    $ autopep8 -a -a -a -i --max-line-length 120 $(FilePath)
    
2. [pylint](https://pypi.org/project/pylint): 

    $ pylint3 -f parseable $(FilePath)

see also pylint directives embedded in source files 
