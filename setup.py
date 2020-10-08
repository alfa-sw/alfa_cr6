from setuptools import setup
import glob

setup (
    name='alfa_CR6',
    version='1.0',
    description='ALFA CR& Project',
    packages=['alfa_CR6'],
    #modules_py=['alfa_CR6', 'alfa_cr6.CR6'],
    package_data={'alfa_CR6/ui': glob.glob('alfa_CR6/ui/*')},
    data_files=[('alfa_CR6/ui', list(glob.glob('alfa_CR6/ui/*')))],
   # install_requires=[
   #     'alfa_CR6'
   # ],
    scripts=['alfa_CR6/scripts/cr6']
    

)
