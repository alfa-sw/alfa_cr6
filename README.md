## ALFA CR6 1.0.0 

### Lanciare il file in sviluppo

"python3 build/lib/alfa_CR6/cr6.py" or
"python3 src/alfa_CR6/cr6.py"

### Deploy

python3 setup.py build
python3 setup.py install

### Run

cr6

### credenziali vuote login

username: ""
password: ""

### Cleanup automatico codice

autoflake <files> --remove-all-unused-imports --remove-unused-variables
autopep8 <files> --aggressive --aggressive
