import json
import unittest

from alfa_CR6_backend.carousel_motor import CarouselMotor


class _MainWindowStub:

    @staticmethod
    def update_status_data(_index, _status):
        return None


class _JarStub:

    status = "PROGRESS"
    barcode = "test-barcode"
    json_properties = json.dumps({"insufficient_pigments": {}})


class _MachineHeadStub:

    index = 0
    status = {}
    name = "A"

    def __init__(self):
        self.events = []

    async def update_tintometer_data(self):
        self.events.append("refresh")

    async def do_dispense(self, _jar, _restore_machine_helper):
        self.events.append("dispense")
        return True


class _CarouselStub:

    def __init__(self, machine):
        self.machine = machine
        self.main_window = _MainWindowStub()
        self.restore_machine_helper = object()

    def get_machine_head_by_letter(self, _letter):
        return self.machine

    @staticmethod
    def update_jar_properties(_jar):
        return None


class PostDispenseTintometerRefreshTest(unittest.IsolatedAsyncioTestCase):

    async def test_refreshes_tintometer_data_after_dispense(self):
        machine = _MachineHeadStub()
        carousel = _CarouselStub(machine)

        result = await CarouselMotor.dispense_step(carousel, "A", _JarStub())

        self.assertTrue(result)
        self.assertEqual(machine.events[-2:], ["dispense", "refresh"])


if __name__ == "__main__":
    unittest.main()
