# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import logging
import json
import time
import asyncio
from functools import partial


from alfa_CR6_backend.globals import tr_
from alfa_CR6_backend.machine_head import DEFAULT_WAIT_FOR_TIMEOUT
from alfa_CR6_backend.base_application import BaseApplication


class CarouselMotor(BaseApplication):  # pylint: disable=too-many-public-methods

    """
     'CRX_OUTPUTS_MANAGEMENT': {'MAB_code': 122, 'visibility': 2,     #  CRX_OUTPUTS_MANAGEMENT  = 122,
        'documentable': False,
        'description': 'Move rollers or lifters of a dispening head of a car refinishing machine in different ways',
        'allowed_status_levels': ['JAR_POSITIONING', 'DIAGNOSTIC', 'STANDBY', 'ALARM', 'DISPENSING',],
        'target_status_levels': ['JAR_POSITIONING', 'DISPENSING',],

        # Output_Number:
        # TESTA1: A 0 = DOSING ROLLER, 1 = INPUT ROLLER,
        # TESTA2: F 0 = DOSING ROLLER, 1 = LIFTER_ROLLER, 2 = OUTPUT_ROLLER, 3 = LIFTER
        # TESTA3: B 0 = DOSING ROLLER
        # TESTA4: E 0 = DOSING ROLLER
        # TESTA5: C 0 = DOSING ROLLER, 1 = LIFTER_ROLLER,
        # TESTA6: D 0 = DOSING ROLLER, 1 = LIFTER

        # ~ Output_Action:
        # ~ 0 = Stop Movement,
        # ~ 1 = Start Movement CW,
        # ~ 2 = Start Movement CW or UP till Photocell transition LIGHT - DARK,
        # ~ 3 = Start Movement CW or UP till Photocell transition DARK - LIGHT,
        # ~ 4 = Start Movement CCW,
        # ~ 5 = Start Movement CCW or DOWN till Photocell transition LIGHT - DARK,
        # ~ 6 = Start Movement CCW or DOWN till Photocell transition DARK - LIGHT"}}}},


    'crx_outputs_status'   : {"type": "number",  "propertyOrder": 52, 'fmt': 'B',
        'description': "rollers or lifters status of a dispening head of a CRx machine. Mask bit coding: bit x = 0 output = OFF, bit x = 1 output = ON"},
        # TESTA1: A bit0 = DOSING ROLLER, bit1 = INPUT ROLLER,
        # TESTA2: F bit0 = DOSING ROLLER, bit1 = LIFTER_ROLLER, bit2 = OUTPUT_ROLLER, bit3 = LIFTER
        # TESTA3: B bit0 = DOSING ROLLER
        # TESTA4: E bit0 = DOSING ROLLER
        # TESTA5: C bit0 = DOSING ROLLER, bit1 = LIFTER_ROLLER,
        # TESTA6: D bit0 = DOSING ROLLER, bit1 = LIFTER
    """

    async def wait_for_condition(      # pylint: disable=too-many-arguments
            self, condition, timeout, show_alert=True, extra_info="", stability_count=3, step=0.01, callback=None):

        ret = None
        t0 = time.time()
        counter = 0
        try:
            while time.time() - t0 < timeout:

                if condition and condition():
                    counter += 1
                    if counter >= stability_count:
                        if callback:
                            callback()
                        ret = True
                        break
                else:
                    counter = 0

                await asyncio.sleep(step)

            if not ret:

                _ = f"timeout expired! timeout:{timeout}.\n"
                if extra_info:
                    _ += str(extra_info)

                if show_alert:
                    self.main_window.open_alert_dialog(_)
                else:
                    logging.warning(_)

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

        return ret

    async def wait_for_jar_delivery(self, jar):

        F = self.get_machine_head_by_letter("F")
        r = None
        try:
            r = await F.wait_for_jar_photocells_status(
                "JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=60, show_alert=True)
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=24 * 60 * 60)

                jar.update_live(pos="_")

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

        return r

    async def wait_for_dispense_position_available(self, head_letter, extra_check=None):

        m = self.get_machine_head_by_letter(head_letter)

        logging.warning(f"{m.name} ")

        status_levels = ['JAR_POSITIONING', 'DIAGNOSTIC', 'STANDBY', 'ALARM', 'DISPENSING']

        while True:

            def condition():
                flag = not m.status.get('crx_outputs_status', 0x0) & 0x01
                flag = flag and not m.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL', False)
                flag = flag and m.status.get("status_level") in status_levels
                if extra_check:
                    flag = flag and extra_check()
                return flag

            r = await self.wait_for_condition(condition, timeout=DEFAULT_WAIT_FOR_TIMEOUT, show_alert=False)

            if not r:
                await self.wait_for_carousel_not_frozen(True, tr_('{} waiting for dispense position to get available.'.format(m.name)))
            else:
                break

        logging.warning(f"{m.name} r:{r}")
        return r

    async def wait_for_load_lifter_is_up(self):

        D = self.get_machine_head_by_letter("D")
        C = self.get_machine_head_by_letter("C")

        if (D.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL') or
                D.status.get('status_level') != 'STANDBY' or
                D.status.get('crx_outputs_status', 0x0) & 0x02):
            timeout_ = 30.3
        else:
            timeout_ = 5.5

        def condition_11():
            return D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')
        r = await self.wait_for_condition(condition_11, show_alert=False, timeout=timeout_)

        if not r:  # the lifter is not UP, we must call it
            cntr = 0
            r = False
            while not D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL'):
                def condition_12():
                    flag = not D.status.get('crx_outputs_status', 0x0) & 0x02
                    flag = flag and not C.status.get('crx_outputs_status', 0x0) & 0x02
                    flag = flag and not C.jar_photocells_status.get('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', True)
                    flag = flag and not D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')
                    return flag
                r = await self.wait_for_condition(condition_12, show_alert=False, timeout=10)
                if r:
                    await D.crx_outputs_management(1, 2)

                cntr += 1
                if cntr > 12:
                    r = False
                    break

        r = D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')

        return r

    async def wait_for_deliver_line_available(self):

        F = self.get_machine_head_by_letter("F")

        while True:
            def condition_1():
                flag = not F.status.get('crx_outputs_status', 0x0) & 0x04
                flag = flag and not F.jar_photocells_status.get('JAR_OUTPUT_ROLLER_PHOTOCELL', False)
                flag = flag and not F.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', False)
                return flag
            r = await self.wait_for_condition(condition_1, show_alert=False, timeout=2.0)
            if not r:  # the output line is busy
                def condition_120():
                    return not F.status.get('crx_outputs_status', 0x0) & 0x04
                r = await self.wait_for_condition(condition_120, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
                if r:
                    await F.crx_outputs_management(2, 4)
                    r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=5.5, show_alert=False)
                    await F.crx_outputs_management(2, 0)

            if r:
                def condition_11():
                    return F.jar_photocells_status.get('UNLOAD_LIFTER_DOWN_PHOTOCELL')
                r = await self.wait_for_condition(condition_11, show_alert=False, timeout=10)
                if not r:  # the lifter is not DOWN, we must call it
                    def condition_12():
                        flag = not F.status.get('crx_outputs_status', 0x0) & 0x02
                        flag = flag and not F.status.get('crx_outputs_status', 0x0) & 0x08
                        flag = flag and not F.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', True)
                        return flag
                    r = await self.wait_for_condition(condition_12, show_alert=False, timeout=34)
                    if r:
                        await F.crx_outputs_management(3, 5)
                if r:
                    def condition():
                        flag = not F.status.get('crx_outputs_status', 0x0) & 0x01
                        flag = flag and not F.status.get('crx_outputs_status', 0x0) & 0x02
                        # ~ flag = flag and not F.status.get('crx_outputs_status', 0x0) & 0x04
                        flag = flag and not F.status.get('crx_outputs_status', 0x0) & 0x08
                        flag = flag and not F.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', True)
                        flag = flag and F.jar_photocells_status.get('UNLOAD_LIFTER_DOWN_PHOTOCELL', False)
                        return flag
                    r = await self.wait_for_condition(condition, timeout=DEFAULT_WAIT_FOR_TIMEOUT,
                                                      show_alert=True, extra_info=tr_('waiting for unload lifter to be free, stopped.'))
            if not r:
                await self.wait_for_carousel_not_frozen(True, tr_("please, remove completed items from output roller"))
            else:
                break

    async def move_from_to(self, jar, letter_from, letter_to):

        logging.warning(f"j:{jar} {letter_from} -> {letter_to}")

        FROM = self.get_machine_head_by_letter(letter_from)
        TO = self.get_machine_head_by_letter(letter_to)

        def condition():
            return not FROM.status.get('crx_outputs_status', 0x0) & 0x01

        r = await self.wait_for_dispense_position_available(letter_to, extra_check=condition)
        if r:
            self.update_jar_position(jar=jar, pos=f"{letter_from}_{letter_to}")

            await FROM.crx_outputs_management(0, 1)
            await TO.crx_outputs_management(0, 2)
            r = await TO.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True, timeout=27)
            await FROM.crx_outputs_management(0, 0)
            await TO.crx_outputs_management(0, 0)
            if r:
                self.update_jar_position(jar=jar, machine_head=TO, pos=letter_to)

        logging.warning(f"j:{jar} {letter_from} -> {letter_to} r:{r}")

        return r

    async def move_00_01(self, silent=False):  # 'feed'

        A = self.get_machine_head_by_letter("A")

        if silent:
            show_alert = False
            extra_info = ''
        else:
            show_alert = True
            extra_info = tr_('waiting for input_roller available and stopped.')

        def condition():
            flag = not A.status.get('crx_outputs_status', 0x0) & 0x02
            flag = flag and not A.jar_photocells_status.get("JAR_INPUT_ROLLER_PHOTOCELL", False)
            # ~ flag = flag and not A.jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL']
            logging.warning(f"flag:{flag}.")
            return flag
        r = await self.wait_for_condition(
            condition, timeout=1.2, show_alert=show_alert, extra_info=extra_info, stability_count=1, step=0.5)

        if r:
            await A.crx_outputs_management(1, 2)
            r = await A.wait_for_jar_photocells_status("JAR_INPUT_ROLLER_PHOTOCELL", on=True, timeout=7, show_alert=False)
            await A.crx_outputs_management(1, 0)
        else:
            logging.warning("input_roller is busy, nothing to do.")

        return r

    async def move_01_02(self, jar=None):  # 'IN -> A'

        logging.warning(f"j:{jar}")

        A = self.get_machine_head_by_letter("A")

        self.update_jar_position(jar=jar, machine_head=A, status="ENTERING", pos="IN")

        def condition():
            return not A.status.get('crx_outputs_status', 0x0) & 0x02
        r = await self.wait_for_dispense_position_available("A", extra_check=condition)

        self.update_jar_position(jar=jar, machine_head=A, pos="IN_A")

        if r:
            await A.crx_outputs_management(1, 2)
            await A.crx_outputs_management(0, 2)
            r = await A.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True, timeout=13)
            await A.crx_outputs_management(1, 0)
            await A.crx_outputs_management(0, 0)

            if r:
                self.update_jar_position(jar=jar, machine_head=A, status="PROGRESS", pos="A")

        return r

    async def move_02_03(self, jar=None):  # 'A -> B'

        return await self.move_from_to(jar, "A", "B")

    async def move_03_04(self, jar=None):  # 'B -> C'

        return await self.move_from_to(jar, "B", "C")

    async def move_02_04(self, jar=None):  # 'A -> C'

        return await self.move_from_to(jar, "A", "C")

    async def move_04_05(self, jar=None):  # 'C -> UP'

        D = self.get_machine_head_by_letter("D")
        C = self.get_machine_head_by_letter("C")

        r = await self.wait_for_load_lifter_is_up()

        if r:
            def condition():
                flag = not D.status.get('crx_outputs_status', 0x0) & 0x02
                flag = flag and not C.status.get('crx_outputs_status', 0x0) & 0x01
                flag = flag and not C.status.get('crx_outputs_status', 0x0) & 0x02
                flag = flag and not C.jar_photocells_status.get('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', True)
                flag = flag and D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')
                return flag

            r = await self.wait_for_condition(condition,
                                              show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT,
                                              extra_info=tr_('waiting for load_lifter roller available and stopped.'))
            if r:
                await C.crx_outputs_management(0, 1)
                await C.crx_outputs_management(1, 2)
                r = await C.wait_for_jar_photocells_status("JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", on=True, timeout=17)
                await C.crx_outputs_management(0, 0)
                await C.crx_outputs_management(1, 0)

                self.update_jar_position(jar=jar, pos="LIFTR_UP")

        return r

    async def move_05_06(self, jar=None):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter("D")

        logging.warning("")

        def condition_12():
            return not D.status.get('crx_outputs_status', 0x0) & 0x02
        r = await self.wait_for_condition(condition_12, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
        if r:
            await D.crx_outputs_management(1, 5)
            r = await D.wait_for_jar_photocells_status("LOAD_LIFTER_DOWN_PHOTOCELL", on=True, timeout=40)
            await D.crx_outputs_management(1, 0)
            self.update_jar_position(jar=jar, pos="LIFTR_DOWN")

        return r

    async def move_06_07(self, jar=None):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter("C")
        D = self.get_machine_head_by_letter("D")

        def condition():
            return not C.status.get('crx_outputs_status', 0x0) & 0x02
        r = await self.wait_for_dispense_position_available("D", extra_check=condition)

        logging.warning(f"j:{jar}, r:{r}")
        if r:

            await C.crx_outputs_management(1, 4)
            await D.crx_outputs_management(0, 5)
            r = await D.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True, timeout=20)
            await C.crx_outputs_management(1, 0)
            await D.crx_outputs_management(0, 0)

            def condition_1():
                return not D.status.get('crx_outputs_status', 0x0) & 0x02
            r1 = await self.wait_for_condition(condition_1, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
            if r1:
                await D.crx_outputs_management(1, 2)

            self.update_jar_position(jar=jar, pos="D")

        return r

    async def move_07_08(self, jar=None):  # 'D -> E'

        return await self.move_from_to(jar, "D", "E")

    async def move_08_09(self, jar=None):  # 'E -> F'

        return await self.move_from_to(jar, "E", "F")

    async def move_07_09(self, jar=None):  # 'D -> F'

        return await self.move_from_to(jar, "D", "F")

    async def move_09_10(self, jar=None):  # 'F -> DOWN'  pylint: disable=unused-argument

        await self.wait_for_deliver_line_available()

        F = self.get_machine_head_by_letter("F")

        await F.crx_outputs_management(0, 4)
        await F.crx_outputs_management(1, 5)
        r = await F.wait_for_jar_photocells_status("JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", on=True, timeout=20)
        await F.crx_outputs_management(0, 0)
        await F.crx_outputs_management(1, 0)
        self.update_jar_position(jar=jar, pos="LIFTL_DOWN")

        return r

    async def move_10_11(self, jar=None):  # 'DOWN -> UP'

        F = self.get_machine_head_by_letter("F")

        def condition_12():
            return not F.status.get('crx_outputs_status', 0x0) & 0x08
        r = await self.wait_for_condition(condition_12, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
        if r:
            await F.crx_outputs_management(3, 2)
            r = await F.wait_for_jar_photocells_status("UNLOAD_LIFTER_UP_PHOTOCELL", on=True, timeout=20)
            await F.crx_outputs_management(3, 0)
            self.update_jar_position(jar=jar, pos="LIFTL_UP")

        return r

    async def move_11_12(self, jar=None):  # 'UP -> OUT'

        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=1.5, show_alert=False)
        if not r:  # the output position is busy
            def condition_120():
                return not F.status.get('crx_outputs_status', 0x0) & 0x04
            r = await self.wait_for_condition(condition_120, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
            if r:
                await F.crx_outputs_management(2, 4)
                r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=5.5, show_alert=False)
                await F.crx_outputs_management(2, 0)

        if r:
            def condition_121():
                flag = not F.status.get('crx_outputs_status', 0x0) & 0x02
                flag = flag and not F.status.get('crx_outputs_status', 0x0) & 0x04
                return flag
            r = await self.wait_for_condition(condition_121, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
            if r:
                await F.crx_outputs_management(1, 4)
                await F.crx_outputs_management(2, 4)
                r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=22)
                await F.crx_outputs_management(1, 0)
                await F.crx_outputs_management(2, 0)

                def condition_12():
                    return not F.status.get('crx_outputs_status', 0x0) & 0x08
                r = await self.wait_for_condition(condition_12, show_alert=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT)
                if r:
                    await F.crx_outputs_management(3, 5)

                self.update_jar_position(jar=jar, machine_head=None, status="DONE", pos="OUT")

        return r

    async def move_12_00(self, jar=None):  # 'deliver' # pylint: disable=unused-argument

        F = self.get_machine_head_by_letter("F")

        def condition():
            return not F.status.get('crx_outputs_status', 0x0) & 0x04

        r = await self.wait_for_condition(
            condition, timeout=5, show_alert=True, extra_info=tr_('output roller is busy.'))

        if r:
            await F.crx_outputs_management(2, 4)
            r = await self.wait_for_condition(condition=None, timeout=7, show_alert=False)
            await F.crx_outputs_management(2, 0)
        else:
            logging.warning("F output roller is busy.")

        return r

    async def single_move(self, head_letter, params):

        m = self.get_machine_head_by_letter(head_letter)
        return await m.crx_outputs_management(*params)

    async def dispense_step(self, machine_letter, jar):

        m = self.get_machine_head_by_letter(machine_letter)
        self.main_window.update_status_data(m.index, m.status)

        await m.update_tintometer_data(invalidate_cache=True)
        self.update_jar_properties(jar)
        json_properties = json.loads(jar.json_properties)
        insufficient_pigment_names = list(json_properties.get("insufficient_pigments", {}).keys())
        if insufficient_pigment_names:
            msg_ = tr_('Missing material for barcode {}.\n please refill pigments:{} on head {}.').format(
                jar.barcode, insufficient_pigment_names, m.name)
            logging.warning(msg_)
            r = await self.wait_for_carousel_not_frozen(True, msg_)
            await m.update_tintometer_data(invalidate_cache=True)
            self.update_jar_properties(jar)

        r = await m.do_dispense(jar)
        logging.warning(f"{m.name}, j:{jar}.")
        logging.debug(f"jar.json_properties:{jar.json_properties}.")
        return r

    async def execute_carousel_steps(self, n_of_heads, jar):

        sequence_6 = [
            self.move_01_02,
            partial(self.dispense_step, "A"),
            self.move_02_03,
            partial(self.dispense_step, "B"),
            self.move_03_04,
            partial(self.dispense_step, "C"),
            self.move_04_05,
            self.move_05_06,
            self.move_06_07,
            partial(self.dispense_step, "D"),
            self.move_07_08,
            partial(self.dispense_step, "E"),
            self.move_08_09,
            partial(self.dispense_step, "F"),
            self.move_09_10,
            self.move_10_11,
            self.move_11_12,
            self.wait_for_jar_delivery,
        ]

        sequence_4 = [
            self.move_01_02,
            partial(self.dispense_step, "A"),
            self.move_02_04,
            partial(self.dispense_step, "C"),
            self.move_04_05,
            self.move_05_06,
            self.move_06_07,
            partial(self.dispense_step, "D"),
            self.move_07_09,
            partial(self.dispense_step, "F"),
            self.move_09_10,
            self.move_10_11,
            self.move_11_12,
            self.wait_for_jar_delivery,
        ]

        if n_of_heads == 6:
            sequence = sequence_6
        elif n_of_heads == 4:
            sequence = sequence_4

        barcode_ = jar and jar.barcode

        for i, step in enumerate(sequence):
            logging.warning(f"step:{step}")
            await self.wait_for_carousel_not_frozen(False, tr_("barcode:{}").format(barcode_) + tr_("STEP {} -").format(i))

            while True:
                r = await step(jar)
                if not r:
                    msg_ = tr_('barcode:{} error in STEP {}. I will retry.').format(barcode_, i)
                    await self.wait_for_carousel_not_frozen(True, msg_)
                else:
                    break
            await self.wait_for_carousel_not_frozen(not r, tr_("barcode:{}").format(barcode_) + tr_("STEP {} +").format(i))

        return r
