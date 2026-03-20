# coding: utf-8

""" dymo printer module """

# pylint: disable=too-many-function-args
# pylint: disable=missing-function-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import asyncio
import functools
import shlex
import tempfile
import time
import traceback
import logging
import subprocess
import os

from alfa_CR6_backend.globals import (create_printable_image_from_jar,create_printable_image_for_pigment,create_printable_image_for_package,extract_jar_print_data,_get_print_label_options)

def _exec_cmd(command, shell=False):

    if isinstance(command, str):
        command_list = shlex.split(command)
    else:
        command_list = command
    logging.debug('command_list -> {}'.format(command_list))
    os_cmd_reply = subprocess.check_output(command_list, shell=shell, stderr=subprocess.STDOUT).decode()
    reply_cmd = [i.strip() for i in os_cmd_reply.split('\n')]
    return reply_cmd


def _check_dymo_printer_presence():
    lsusb_res = _exec_cmd('lsusb', True)
    return [elem for elem in lsusb_res if 'Dymo-CoStar' in elem]


def _dymo_print_tmp_image(_printable_image_pth, fake=False):

    if fake:
        return {'result': 'OK', 'msg': 'Dry run, not printed'}

    ret = {}
    _dymo_printer_presence = _check_dymo_printer_presence()
    logging.warning(f'_printable_image_pth:{_printable_image_pth}, _dymo_printer_presence:{_dymo_printer_presence}')
    if not _printable_image_pth:
        return {'result': 'NOK', 'msg': 'Cannot create printable image'}

    if _dymo_printer_presence or os.getenv("IN_DOCKER", False) in ['1', 'true']:
        _print_cups_cmd = f'lp -o fit-to-page {_printable_image_pth}'
        logging.debug("_print_cups_cmd: %s", _print_cups_cmd)

        res_print = _exec_cmd(_print_cups_cmd)
        ret = {'result': 'OK', 'msg': res_print}
    else:
        ret = {'result': 'NOK', 'msg': 'Printer not detected'}

    return ret

def dymo_print_jar(jar):

    logging.debug(f'jar: {jar}')

    ret = {}
    try:
        _printable_image_pth = create_printable_image_from_jar(jar)
        ret = _dymo_print_tmp_image(_printable_image_pth)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret

def dymo_print_pigment_label(barcode_txt, pigment_name, pipe_name, fake=False):

    ret = {}
    try:
        _printable_image_pth = create_printable_image_for_pigment(
            barcode_txt, pigment_name, pipe_name)
        ret = _dymo_print_tmp_image(_printable_image_pth, fake=fake)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret

def dymo_print_package_label(package, fake=False):

    ret = {}
    try:
        _printable_image_pth = create_printable_image_for_package(package)
        ret = _dymo_print_tmp_image(_printable_image_pth, fake=fake)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        ret = {'result': 'NOK', 'msg': traceback.format_exc()}

    return ret


def _images_to_pdf(image_paths, pdf_path):

    from PIL import Image   # pylint: disable=import-outside-toplevel
    images = []
    try:
        for p in image_paths:
            images.append(Image.open(p).convert('L'))
        images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=300)
    finally:
        for img in images:
            img.close()


def _dymo_print_pdf(pdf_path):

    ret = {}
    _dymo_printer_presence = _check_dymo_printer_presence()
    logging.warning(f'_dymo_print_pdf: {pdf_path}, _dymo_printer_presence:{_dymo_printer_presence}')

    if _dymo_printer_presence or os.getenv("IN_DOCKER", False) in ['1', 'true']:
        _print_cups_cmd = f'lp -o fit-to-page {pdf_path}'
        logging.debug("_print_cups_cmd: %s", _print_cups_cmd)
        res_print = _exec_cmd(_print_cups_cmd)
        ret = {'result': 'OK', 'msg': res_print}
    else:
        ret = {'result': 'NOK', 'msg': 'Printer not detected'}

    return ret


async def async_dymo_print_jar(jar):
    loop = asyncio.get_event_loop()
    try:
        _printable_image_pth = create_printable_image_from_jar(jar)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        return {'result': 'NOK', 'msg': traceback.format_exc()}
    return await loop.run_in_executor(None, _dymo_print_tmp_image, _printable_image_pth)


async def async_dymo_print_jars(jars):

    jar_data_list = [extract_jar_print_data(jar) for jar in jars]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_and_print_jars, jar_data_list)


def _generate_and_print_jars(jar_data_list):

    t0 = time.monotonic()
    image_paths = []
    fd_pdf, pdf_path = tempfile.mkstemp(suffix='.pdf', dir='/opt/alfa_cr6/tmp/')
    os.close(fd_pdf)
    try:
        options = _get_print_label_options()
        for jar_data in jar_data_list:
            fd, tmp_file = tempfile.mkstemp(suffix='.png', dir='/opt/alfa_cr6/tmp/')
            os.close(fd)
            try:
                _path = create_printable_image_from_jar(jar_data, options=dict(options), output_path=tmp_file)
                if _path:
                    image_paths.append(_path)
            except Exception:   # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        t1 = time.monotonic()
        logging.debug(f"[print_batch] {len(image_paths)} images generated in {t1-t0:.3f}s")

        if not image_paths:
            return {'result': 'NOK', 'msg': 'No images generated'}

        _images_to_pdf(image_paths, pdf_path)
        t2 = time.monotonic()
        logging.debug(f"[print_batch] pdf created in {t2-t1:.3f}s")

        ret = _dymo_print_pdf(pdf_path)
        t3 = time.monotonic()
        logging.debug(f"[print_batch] print submitted in {t3-t2:.3f}s, total {t3-t0:.3f}s")
        return ret

    finally:
        for p in image_paths + [pdf_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def _generate_and_print_pigment_labels(printables, fake=False):

    t0 = time.monotonic()
    image_paths = []
    fd_pdf, pdf_path = tempfile.mkstemp(suffix='.pdf', dir='/opt/alfa_cr6/tmp/')
    os.close(fd_pdf)
    try:
        options = _get_print_label_options()
        for printable in printables:
            fd, tmp_file = tempfile.mkstemp(suffix='.png', dir='/opt/alfa_cr6/tmp/')
            os.close(fd)
            try:
                _path = create_printable_image_for_pigment(
                    printable.get('barcode_txt', ''),
                    printable.get('pigment_name', ''),
                    printable.get('pipe_name', ''),
                    options=dict(options),
                    output_path=tmp_file)
                if _path:
                    image_paths.append(_path)
            except Exception:   # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        t1 = time.monotonic()
        logging.debug(f"[print_pigment_batch] {len(image_paths)} images generated in {t1-t0:.3f}s")

        if not image_paths:
            return {'result': 'NOK', 'msg': 'No images generated'}

        if fake:
            return {'result': 'OK', 'msg': 'Dry run, not printed'}

        _images_to_pdf(image_paths, pdf_path)
        t2 = time.monotonic()
        logging.debug(f"[print_pigment_batch] pdf created in {t2-t1:.3f}s")

        ret = _dymo_print_pdf(pdf_path)
        t3 = time.monotonic()
        logging.debug(f"[print_pigment_batch] print submitted in {t3-t2:.3f}s, total {t3-t0:.3f}s")
        return ret

    finally:
        for p in image_paths + [pdf_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


async def async_dymo_print_pigment_labels(printables, fake=False):

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(_generate_and_print_pigment_labels, printables, fake=fake))


async def async_dymo_print_package_label(package, fake=False):
    loop = asyncio.get_event_loop()
    try:
        _printable_image_pth = create_printable_image_for_package(package)
    except Exception:   # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        return {'result': 'NOK', 'msg': traceback.format_exc()}
    return await loop.run_in_executor(None, functools.partial(_dymo_print_tmp_image, _printable_image_pth, fake=fake))
