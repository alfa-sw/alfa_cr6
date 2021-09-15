# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

"""
>>> import evdev; ls_ = [str(evdev.InputDevice(p)) for p in  evdev.list_devices()]; ls_.sort(); [print(i) for i in ls_]
device /dev/input/event0, name "LWTEK Barcode Scanner", phys "usb-0000:01:00.0-1.3.1/input0"
device /dev/input/event1, name "LWTEK Barcode Scanner", phys "usb-0000:01:00.0-1.3.1/input1"
device /dev/input/event2, name "SIGMACH1P U+P Mouse", phys "usb-0000:01:00.0-1.3.2/input0"
device /dev/input/event3, name "NOVATEK USB Keyboard", phys "usb-0000:01:00.0-1.3.3/input0"
device /dev/input/event4, name "NOVATEK USB Keyboard System Control", phys "usb-0000:01:00.0-1.3.3/input1"
device /dev/input/event5, name "NOVATEK USB Keyboard Consumer Control", phys "usb-0000:01:00.0-1.3.3/input1"
device /dev/input/event6, name "NOVATEK USB Keyboard", phys "usb-0000:01:00.0-1.3.3/input1"
device /dev/input/event7, name "py-evdev-uinput", phys "py-evdev-uinput"
[None, None, None, None, None, None, None, None]

lrwxrwxrwx 1 root root 9 Jun 28 15:02 usb-LWTEK_Barcode_Scanner_00000000011C-event-if01 -> ../event1
lrwxrwxrwx 1 root root 9 Jun 28 15:02 usb-LWTEK_Barcode_Scanner_00000000011C-event-kbd -> ../event0
lrwxrwxrwx 1 root root 9 Jun 28 14:39 usb-NOVATEK_USB_Keyboard-event-if01 -> ../event5
lrwxrwxrwx 1 root root 9 Jun 28 14:39 usb-NOVATEK_USB_Keyboard-event-kbd -> ../event3
lrwxrwxrwx 1 root root 9 Jun 28 14:39 usb-NOVATEK_USB_Keyboard-if01-event-mouse -> ../event6
lrwxrwxrwx 1 root root 9 Jun 28 15:02 usb-SIGMACH1P_U+P_Mouse-event-mouse -> ../event2
lrwxrwxrwx 1 root root 9 Jun 28 15:02 usb-SIGMACH1P_U+P_Mouse-mouse -> ../mouse0


>>> import evdev; ls_ = [str(evdev.InputDevice(p)) for p in  evdev.list_devices()]; ls_.sort(); [print(i) for i in ls_]
device /dev/input/event0, name "Manufacturer Barcode Reader", phys "usb-0000:01:00.0-1.2.1/input0"
device /dev/input/event1, name "ILITEK ILITEK-TP", phys "usb-0000:01:00.0-1.2.2.3/input0"
device /dev/input/event2, name "ILITEK ILITEK-TP Mouse", phys "usb-0000:01:00.0-1.2.2.3/input0"
device /dev/input/event3, name "py-evdev-uinput", phys "py-evdev-uinput"
[None, None, None, None]

lrwxrwxrwx 1 root root 9 Jun 28 15:02 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.1:1.0-event-kbd -> ../event0
lrwxrwxrwx 1 root root 9 Jun 28 15:02 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.1:1.1-event -> ../event1
lrwxrwxrwx 1 root root 9 Jun 28 15:02 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.2:1.0-event-mouse -> ../event2
lrwxrwxrwx 1 root root 9 Jun 28 15:02 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.2:1.0-mouse -> ../mouse0
lrwxrwxrwx 1 root root 9 Jun 28 14:39 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.3:1.0-event-kbd -> ../event3
lrwxrwxrwx 1 root root 9 Jun 28 14:39 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.3:1.1-event -> ../event5
lrwxrwxrwx 1 root root 9 Jun 28 14:39 platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3.3:1.1-event-mouse -> ../event6
"""



# ~ import os
import sys
# ~ import time
import logging
import traceback
import asyncio
import subprocess

import evdev  # pylint: disable=import-error, import-outside-toplevel

from alfa_CR6_backend.base_application import BarCodeReader

class Reader:

    scanner_device = None

    BARCODE_DEVICE_KEY_CODE_MAP = {
        "KEY_SPACE": " ",
        "KEY_1": "1",
        "KEY_2": "2",
        "KEY_3": "3",
        "KEY_4": "4",
        "KEY_5": "5",
        "KEY_6": "6",
        "KEY_7": "7",
        "KEY_8": "8",
        "KEY_9": "9",
        "KEY_0": "0",
    }

    @staticmethod
    def search_device_by_id():

        # ~ lrwxrwxrwx 1 root root 9 Jun 28 15:02 usb-LWTEK_Barcode_Scanner_00000000011C-event-kbd -> ../event0
        cmd_ = "ls -l /dev/input/by-id/"
        output_lines = subprocess.check_output(cmd_.split(), shell=False).decode().split('\n')
        logging.warning(f"output_lines:{output_lines}")

        dev_name = ''
        for l in output_lines:
            if "LWTEK_Barcode_Scanner" in l and "event-kbd" in l:
                dev_name = l.split("/")[-1]
                break

        logging.warning(f"dev_name:{dev_name}")

        return dev_name

    async def read_forever(self):

        buffer = ""

        device_list = [evdev.InputDevice(p) for p in  evdev.list_devices()]
        device_list.sort(key=str)
        for device_ in device_list:
            # ~ logging.warning(f"device_:{ device_ }")
            s_ = str(device_)
            if "LWTEK Barcode Scanner" in s_ or "Manufacturer Barcode Reader" in s_:
                self.scanner_device = device_
                logging.warning(f"BARCODE DEVICE FOUND. self.scanner_device:{self.scanner_device}")
                break

        if not self.scanner_device:
            logging.error(f"****** !!!! BARCODE DEVICE NOT FOUND !!! ******")
        else:
            self.scanner_device.grab()  # become the sole recipient of all incoming input events from this device
            async for event in self.scanner_device.async_read_loop():
                keyEvent = evdev.categorize(event)
                type_key_event = evdev.ecodes.EV_KEY  # pylint:  disable=no-member
                # ~ logging.warning(f"type_key_event:{type_key_event} ({event.type})")
                if event.type == type_key_event and keyEvent.keystate == 0:
                    # key_up = 0
                    if keyEvent.keycode == "KEY_ENTER":
                        logging.warning(f"buffer:{buffer}")
                        buffer = buffer[:12]
                        buffer = ""
                    else:
                        buffer += self.BARCODE_DEVICE_KEY_CODE_MAP.get(keyEvent.keycode, keyEvent.keycode + ', ')


def one():

    identification_string = "usb-0000:01:00.0-1.2.4"


    if sys.argv[1:] and sys.argv[1]:
        identification_string = sys.argv[1]

    logging.warning(f"identification_string:{identification_string}.")

    def barcode_handler(barcode):
        logging.warning(f"barcode:{barcode}.")

    barcode_reader = None
    try:
        barcode_reader = BarCodeReader(barcode_handler, identification_string, exception_handler=None)
        t = barcode_reader.run()

        asyncio.ensure_future(t)
        asyncio.get_event_loop().run_forever()

    except KeyboardInterrupt:
        pass

    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())

    if barcode_reader and barcode_reader._device:   # pylint: disable=protected-access
        barcode_reader._device.close()              # pylint: disable=protected-access

    asyncio.get_event_loop().stop()
    asyncio.get_event_loop().close()

def two():

    reader = None
    try:
        reader = Reader()
        t = reader.read_forever()
        asyncio.ensure_future(t)
        asyncio.get_event_loop().run_forever()

    except KeyboardInterrupt:
        pass

    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())

    if reader and reader.scanner_device:
        reader.scanner_device.close()

    asyncio.get_event_loop().stop()
    asyncio.get_event_loop().close()




def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.WARNING, format=fmt_)

    one()

main()
