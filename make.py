# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import sys
import os
import argparse
import time
import logging

from setup import __version__, __app_name__

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEPLOY_PATH = "/opt/alfa_cr6"
VENV_PATH = f"{DEPLOY_PATH}/venv"
CONF_PATH = f"{DEPLOY_PATH}/conf"
LOG_PATH = f"{DEPLOY_PATH}/log"
DATA_PATH = f"{DEPLOY_PATH}/data"
TMP_PATH = f"{DEPLOY_PATH}/tmp"
SCRIPTS_PATH = f"{DEPLOY_PATH}/scripts"

OUT_ERR_PTH = f"{PROJECT_ROOT}/make.err.out"

RSA_ID = "-i ~/.ssh/alfa_rsa"

args = {}

def parse_arguments():

    parser = argparse.ArgumentParser(description='development tool for build/install.')
    parser.add_argument(
        '-l',
        '--log_level',
        default='INFO',
        help='level of verbosity in logging messages default: %(default)s.')
    parser.add_argument('-t', '--target_credentials', default='admin@192.168.0.100', help='ssh credentials to target. default: "%(default)s".')
    parser.add_argument('-s', '--app_settings', default='app_settings.target', help='select the app conf file. default: "%(default)s".')
    parser.add_argument('-i', '--ignore_requires', default=False, help='ignore_requires in installing. default: "%(default)s".')
    parser.add_argument('-d', '--dry_run', default=False, help='dry run: just test, do nothing. default: "%(default)s".')
    parser.add_argument('-v', '--verbose', default=False, help='verbose: print to stdout messages, while executing commands. default: "%(default)s".')

    parser.add_argument('-b', '--build', help='action: build the wheel.', action='store_const', const=1)
    parser.add_argument('-e', '--install_editable', help='action: install om host in edit mode.', action='store_const', const=1)
    parser.add_argument('-I', '--install_target', help='action: install om target.', action='store_const', const=1)
    parser.add_argument('-M', '--makedirs_on_target', help='action: make dirs on target', action='store_const', const=1)
    parser.add_argument('-C', '--deploy_conf_to_target', help='action: copy conf files to target', action='store_const', const=1)
    parser.add_argument('-D', '--deploy_db_to_target', action='store_const', const=1,
                        help='action: copy the sqlite db to target, *BEWARE* overwriting it!')
    parser.add_argument('-V', '--virtenv_on_target', action='store_const', const=True,
                        help='action: build virtual env on target.')
    parser.add_argument('-A', '--enable_desktop_autologin_on_target', action='store_const', const=True,
                        help='action: enable desktop (i.e. GUI) autologin on target. Raspberrypi only.')

    parser.add_argument('-S', '--deploy_and_execute_target_scripts', action='store_const', const=1, help='DEPRECATED. action: If in doubt, avoid doing it!')

    return parser.parse_args()


def exec_(cmd_):

    global args

    logging.info(f"args.dry_run:{args.dry_run}, args.verbose:{args.verbose}, cmd_:{cmd_}")
    if not args.dry_run:
        if args.verbose:
            ret_val = os.system(cmd_)
        else:
            ret_val = os.system(cmd_ + f"  >>{OUT_ERR_PTH} 2>&1 ")
        logging.info(f"ret_val:{ret_val}")

    return ret_val 

def build(args):

    cmd_ = f"cd {PROJECT_ROOT};. {VENV_PATH}/bin/activate; python setup.py bdist_wheel "
    exec_(cmd_)
    cmd_ = f"ls -l {PROJECT_ROOT}/dist/alfa_CR6-{__version__}-py3-none-any.whl"
    exec_(cmd_)


def makedirs_on_target(args):

    tgt_cred = args.target_credentials

    for pth in (DEPLOY_PATH, VENV_PATH, CONF_PATH, LOG_PATH, DATA_PATH, TMP_PATH, SCRIPTS_PATH):
        cmd_ = f'ssh {RSA_ID} {tgt_cred} "if [ ! -e {pth} ]; then sudo mkdir -p {pth} ;fi"'
        exec_(cmd_)
    cmd_ = f'ssh {RSA_ID} {tgt_cred} "sudo chown -R admin:admin {DEPLOY_PATH}"'
    exec_(cmd_)

def deploy_db_to_target(args):

    tgt_cred = args.target_credentials

    cmd_ = f"scp {RSA_ID} {DATA_PATH}/cr6_Vx_test.sqlite {tgt_cred}:{DATA_PATH}/"
    exec_(cmd_)

def deploy_conf_to_target(args):

    tgt_cred = args.target_credentials
    settings = args.app_settings

    cmds = [
        f"scp {RSA_ID} {PROJECT_ROOT}/conf/{settings}.py {tgt_cred}:{CONF_PATH}/app_settings.py",
        # ~ f"scp {RSA_ID} {PROJECT_ROOT}/conf/supervisor.target.conf {tgt_cred}:/opt/alfa/conf/supervisor/cr6.conf",
        # ~ f"scp {RSA_ID} {PROJECT_ROOT}/conf/xhost.desktop {tgt_cred}:/opt/alfa/tmp/",
        # ~ f'ssh {RSA_ID} {tgt_cred} "sudo cp /opt/alfa/tmp/xhost.desktop /home/pi/.config/autostart/"',
        # ~ f'ssh {RSA_ID} {tgt_cred} "sudo chown pi:pi /home/pi/.config/autostart/xhost.desktop"',
    ]

    for cmd_ in cmds:
        exec_(cmd_)

        time.sleep(.1)

def install_target(args, silent=False):

    tgt_cred = args.target_credentials
    settings = args.app_settings
    ignore_requires = '--ignore-requires --no-dependencies ' if args.ignore_requires else ''

    cmds = [
        f"scp {RSA_ID} {PROJECT_ROOT}/dist/alfa_CR6-{__version__}-py3-none-any.whl {tgt_cred}:{TMP_PATH}/",
        f'ssh {RSA_ID} {tgt_cred} ". /opt/alfa_cr6/venv/bin/activate; pip uninstall -y alfa_CR6"',
        f'ssh {RSA_ID} {tgt_cred} ". /opt/alfa_cr6/venv/bin/activate; pip install {ignore_requires} {TMP_PATH}/alfa_CR6-{__version__}-py3-none-any.whl"',
        f"rm -f {tgt_cred}:{TMP_PATH}/alfa_CR6-{__version__}-py3-none-any.whl",
        f'ssh {RSA_ID} {tgt_cred} "sudo supervisorctl reload"',
    ]

    for cmd_ in cmds:
        r = exec_(cmd_)
        if r:
            break
        time.sleep(.1)

def install_editable(args):

    ignore_requires = '--ignore-requires --no-dependencies ' if args.ignore_requires else ''

    cmd_ = f"cd {PROJECT_ROOT};. {VENV_PATH}/bin/activate;pip uninstall -y {__app_name__}; pip install {ignore_requires} -e ./"
    exec_(cmd_)

def deploy_and_execute_target_scripts(args):

    tgt_cred = args.target_credentials
    settings = args.app_settings

    cmds = [
        f"scp {RSA_ID} {PROJECT_ROOT}/target_scripts/target_scripts.sh {tgt_cred}:{SCRIPTS_PATH}/target_scripts.sh",
        f'ssh {RSA_ID} {tgt_cred} "sudo chmod +x {SCRIPTS_PATH}/target_scripts.sh"',
        f'ssh {RSA_ID} {tgt_cred} "sudo bash {SCRIPTS_PATH}/target_scripts.sh"',
    ]

    for cmd_ in cmds:
        exec_(cmd_)

        time.sleep(.1)

def enable_desktop_autologin_on_target(args):

    tgt_cred = args.target_credentials

    cmd_ = f'ssh {RSA_ID} {tgt_cred} "sudo raspi-config nonint do_boot_behaviour B4"'
    exec_(cmd_)

def virtenv_on_target(args):

    tgt_cred = args.target_credentials

    cmd_ = f'ssh {RSA_ID} {tgt_cred} "virtualenv --system-site-packages --clear -p /usr/bin/python3 /opt/alfa_cr6/venv"'
    exec_(cmd_)

def main():

    global args

    args = parse_arguments()

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=args.log_level, format=fmt_)

    logging.info(f"args:{args}")
    logging.warning(f"see also command log msgs in {OUT_ERR_PTH}")
    with open(OUT_ERR_PTH, 'w') as f: # reset messages
        f.write(f'{time.asctime()}\n')

    if args.build:
        build(args)
    if args.install_editable:
        install_editable(args)
    if args.makedirs_on_target:
        makedirs_on_target(args)
    if args.deploy_db_to_target:
        deploy_db_to_target(args)
    if args.deploy_conf_to_target:
        deploy_conf_to_target(args)
    if args.deploy_and_execute_target_scripts:
        deploy_and_execute_target_scripts(args)
    if args.virtenv_on_target:
        virtenv_on_target(args)
    if args.enable_desktop_autologin_on_target:
        enable_desktop_autologin_on_target(args)
    if args.install_target:
        install_target(args)


main()
