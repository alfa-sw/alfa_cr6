# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import logging
import json


from alfa_CR6_backend.globals import tr_

class CarouselMotor:

    async def move_00_01(self):  # 'feed'

        A = self.get_machine_head_by_letter("A")

        r = await A.wait_for_jar_photocells_and_status_lev(
            "JAR_INPUT_ROLLER_PHOTOCELL", on=False, status_levels=["STANDBY"], timeout=1
        )
        if r:
            r = await A.wait_for_jar_photocells_and_status_lev(
                "JAR_DISPENSING_POSITION_PHOTOCELL",
                on=False,
                status_levels=["STANDBY"],
                timeout=1,
            )
            if r:
                await A.can_movement({"Input_Roller": 2})
                r = await A.wait_for_jar_photocells_status("JAR_INPUT_ROLLER_PHOTOCELL", on=True, timeout=30)
                if not r:
                    await A.can_movement()
        else:
            logging.warning("A JAR_INPUT_ROLLER_PHOTOCELL is busy, nothing to do.")

        return r

    async def move_01_02(self, jar=None):  # 'IN -> A'

        A = self.get_machine_head_by_letter("A")

        self.update_jar_position(jar=jar, machine_head=A, status="ENTERING", pos="IN_A")

        r = await A.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            await A.can_movement({"Input_Roller": 1, "Dispensing_Roller": 2})
            r = await A.wait_for_jar_photocells_status(
                "JAR_DISPENSING_POSITION_PHOTOCELL", on=True)

            self.update_jar_position(jar=jar, machine_head=A, status="PROGRESS", pos="A")

        return r

    async def move_02_03(self, jar=None):  # 'A -> B'

        A = self.get_machine_head_by_letter("A")
        B = self.get_machine_head_by_letter("B")

        r = await B.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:

            await A.can_movement({"Dispensing_Roller": 1})
            await B.can_movement({"Dispensing_Roller": 2})
            r = await B.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await A.can_movement()
                self.update_jar_position(jar=jar, machine_head=B, pos="B")

        return r

    async def move_02_04(self, jar=None):  # 'A -> C'

        A = self.get_machine_head_by_letter("A")
        C = self.get_machine_head_by_letter("C")

        def condition():
            flag = not C.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
            flag = (
                flag and not C.jar_photocells_status["JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"]
            )
            flag = flag and C.status["status_level"] in ["STANDBY"]
            return flag

        logging.warning(f" condition():{condition()}")
        r = await C.wait_for_condition(condition, timeout=60 * 3)
        logging.warning(f" r:{r}")

        if r:
            await A.can_movement({"Dispensing_Roller": 1})
            await C.can_movement({"Dispensing_Roller": 2})
            r = await C.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await A.can_movement()
                self.update_jar_position(jar=jar, machine_head=C, pos="C")

        return r

    async def move_03_04(self, jar=None):  # 'B -> C'

        B = self.get_machine_head_by_letter("B")
        C = self.get_machine_head_by_letter("C")

        def condition():
            flag = not C.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
            flag = (
                flag and not C.jar_photocells_status["JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"]
            )
            flag = flag and C.status["status_level"] in ["STANDBY"]
            return flag

        logging.warning(f" condition():{condition()}")
        r = await C.wait_for_condition(condition, timeout=60 * 3)
        logging.warning(f" r:{r}")

        if r:
            await B.can_movement({"Dispensing_Roller": 1})
            await C.can_movement({"Dispensing_Roller": 2})
            r = await C.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await B.can_movement()
                self.update_jar_position(jar=jar, machine_head=C, pos="C")

        return r

    async def move_04_05(self, jar=None):  # 'C -> UP'

        C = self.get_machine_head_by_letter("C")
        D = self.get_machine_head_by_letter("D")

        r = await C.wait_for_jar_photocells_status("JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", on=False)
        if r:
            r = await D.wait_for_jar_photocells_status(
                "LOAD_LIFTER_UP_PHOTOCELL", on=True, timeout=3, show_alert=False)
            if not r:

                r = await D.wait_for_jar_photocells_and_status_lev(
                    "JAR_DISPENSING_POSITION_PHOTOCELL",
                    on=False,
                    status_levels=["STANDBY"],
                )
                if r:
                    await D.can_movement({"Lifter": 1})
                    r = await D.wait_for_jar_photocells_status("LOAD_LIFTER_UP_PHOTOCELL", on=True)
            if r:
                await C.can_movement({"Dispensing_Roller": 1, "Lifter_Roller": 2})
                r = await C.wait_for_jar_photocells_status("JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", on=True)
                self.update_jar_position(jar=jar, pos="LIFTR_UP")

        return r

    async def move_05_06(self, jar=None):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter("D")

        r = await D.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            await D.can_movement({"Lifter": 2})
            r = await D.wait_for_jar_photocells_status("LOAD_LIFTER_DOWN_PHOTOCELL", on=True)

            self.update_jar_position(jar=jar, pos="LIFTR_DOWN")

        return r

    async def move_06_07(self, jar=None):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter("C")
        D = self.get_machine_head_by_letter("D")

        r = await D.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            r = await C.wait_for_status_level(status_levels=["STANDBY"])

            await C.can_movement({"Lifter_Roller": 3})
            await D.can_movement({"Dispensing_Roller": 2})
            r = await D.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await C.can_movement()
                self.update_jar_position(jar=jar, machine_head=D, pos="D")

        return r

    async def move_07_08(self, jar=None):  # 'D -> E'

        D = self.get_machine_head_by_letter("D")
        E = self.get_machine_head_by_letter("E")

        r = await E.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            r = await D.wait_for_jar_photocells_status(
                "LOAD_LIFTER_UP_PHOTOCELL", on=True, timeout=3, show_alert=False)

            if not r:
                await D.can_movement()
                await D.can_movement({"Dispensing_Roller": 1})
            else:
                await D.can_movement({"Dispensing_Roller": 1})
            await E.can_movement({"Dispensing_Roller": 2})
            r = await E.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await D.can_movement()
                self.update_jar_position(jar=jar, machine_head=E, pos="E")

        return r

    async def move_07_09(self, jar=None):  # 'D -> F'

        D = self.get_machine_head_by_letter("D")
        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=False)
        if r:
            r = await F.wait_for_jar_photocells_and_status_lev(
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
                on=False,
                status_levels=["STANDBY"],
            )
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "UNLOAD_LIFTER_DOWN_PHOTOCELL", on=True, timeout=3, show_alert=False)
                if not r:
                    await F.can_movement({"Lifter": 2})
                    r = await F.wait_for_jar_photocells_and_status_lev(
                        "UNLOAD_LIFTER_DOWN_PHOTOCELL",
                        on=True,
                        status_levels=["STANDBY"],
                    )
                if r:
                    await D.can_movement({"Dispensing_Roller": 1})
                    await F.can_movement({"Dispensing_Roller": 2})
                    r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
                    if r:
                        await D.can_movement()
                        self.update_jar_position(jar=jar, machine_head=F, pos="F")

        return r

    async def move_08_09(self, jar=None):  # 'E -> F'

        E = self.get_machine_head_by_letter("E")
        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=False)
        if r:
            r = await F.wait_for_jar_photocells_and_status_lev(
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
                on=False,
                status_levels=["STANDBY"],
            )
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "UNLOAD_LIFTER_DOWN_PHOTOCELL", on=True, timeout=3, show_alert=False)
                if not r:
                    await F.can_movement({"Lifter": 2})
                    r = await F.wait_for_jar_photocells_and_status_lev(
                        "UNLOAD_LIFTER_DOWN_PHOTOCELL",
                        on=True,
                        status_levels=["STANDBY"],
                    )
                if r:
                    await E.can_movement({"Dispensing_Roller": 1})
                    await F.can_movement({"Dispensing_Roller": 2})
                    r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
                    if r:
                        await E.can_movement()
                        self.update_jar_position(jar=jar, machine_head=F, pos="F")

        return r

    async def move_09_10(self, jar=None):  # 'F -> DOWN'  pylint: disable=unused-argument

        F = self.get_machine_head_by_letter("F")
        r = await F.wait_for_jar_photocells_status("JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", on=False)
        if r:
            r = await F.wait_for_jar_photocells_status("UNLOAD_LIFTER_DOWN_PHOTOCELL", on=True)
            if r:
                await F.can_movement({"Dispensing_Roller": 1, "Lifter_Roller": 5})
            self.update_jar_position(jar=jar, pos="LIFTL_DOWN")
        return r

    async def move_10_11(self, jar=None):  # 'DOWN -> UP -> OUT'

        F = self.get_machine_head_by_letter("F")
        r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=3, show_alert=False)
        if r:
            r = await F.wait_for_jar_photocells_status("JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", on=True)
            self.update_jar_position(jar=jar, machine_head=F, pos="LIFTL_UP")
            if r:
                r = await F.wait_for_jar_photocells_and_status_lev(
                    "UNLOAD_LIFTER_UP_PHOTOCELL", on=True, status_levels=["STANDBY"])
                if r:
                    await F.can_movement({"Output_Roller": 2})
                    r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False)

                    self.update_jar_position(jar=jar, machine_head=F, pos="WAIT")

                    if r:
                        await F.can_movement()
                        await F.can_movement({"Lifter_Roller": 3, "Output_Roller": 1})
                        r = await F.wait_for_status_level(status_levels=["STANDBY"])
                    else:
                        raise Exception("JAR_OUTPUT_ROLLER_PHOTOCELL busy timeout")
        else:
            r = await F.wait_for_status_level(status_levels=["STANDBY"])
            self.update_jar_position(jar=jar, machine_head=F, pos="OUT")

        return r

    async def move_11_12(self, jar=None):  # 'UP -> OUT'

        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_status_level(status_levels=["STANDBY"], timeout=3, show_alert=False)
        if r:
            r = await F.wait_for_jar_photocells_status(
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
                on=True,
                timeout=3,
                show_alert=False,
            )
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=3, show_alert=False)
                if r:
                    await F.can_movement({"Output_Roller": 2})

                r = await F.wait_for_jar_photocells_and_status_lev(
                    "JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, status_levels=["STANDBY"])
                if r:
                    await F.can_movement({"Lifter_Roller": 3, "Output_Roller": 1})

        self.update_jar_position(jar=jar, machine_head=None, status="DONE", pos="OUT")

        return r

    async def move_12_00(self, jar=None):  # 'deliver' # pylint: disable=unused-argument

        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_and_status_lev(
            "JAR_OUTPUT_ROLLER_PHOTOCELL",
            on=True,
            status_levels=["STANDBY"],
            timeout=3,
            show_alert=False)
        if r:
            F = self.get_machine_head_by_letter("F")
            await F.can_movement({"Output_Roller": 2})
        else:
            msg_ = f"cannot move output roller"
            logging.warning(msg_)
            self.main_window.open_alert_dialog(msg_)

    async def wait_for_jar_delivery(self, jar):

        F = self.get_machine_head_by_letter("F")

        try:
            r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=60, show_alert=True)
            if r:
                r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=24 * 60 * 60)

            jar.update_live(pos="_")

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    async def dispense_step(self, r, machine_letter, jar):

        m = self.get_machine_head_by_letter(machine_letter)
        self.main_window.update_status_data(m.index, m.status)

        logging.warning(f"{m.name}")

        await m.update_tintometer_data(invalidate_cache=True)

        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} -").format(machine_letter))
        _, _, unavailable_pigment_names = self.check_available_volumes(jar)

        if unavailable_pigment_names:

            msg_ = tr_('Missing material for barcode {}.\n please refill pigments:{} on head {}.').format(
                jar.barcode, unavailable_pigment_names, m.name)

            logging.warning(msg_)
            r = await self.wait_for_carousel_not_frozen(True, msg_)

            await m.update_tintometer_data(invalidate_cache=True)

            ingredient_volume_map, _, _ = self.check_available_volumes(jar)
            json_properties = json.loads(jar.json_properties)
            json_properties["ingredient_volume_map"] = ingredient_volume_map
            jar.json_properties = json.dumps(json_properties, indent=2)

        r = await m.do_dispense(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +").format(machine_letter))

        return r

    async def execute_carousel_steps(self, n_of_heads, jar):

        # ~ await self.move_00_01(jar)
        r = await self.move_01_02(jar)
        r = await self.dispense_step(r, "A", jar)

        if n_of_heads == 6:
            r = await self.move_02_03(jar)
            r = await self.dispense_step(r, "B", jar)
            r = await self.move_03_04(jar)
        elif n_of_heads == 4:
            r = await self.move_02_04(jar)

        r = await self.dispense_step(r, "C", jar)
        r = await self.move_04_05(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} ++").format('C'))
        r = await self.move_05_06(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +++").format('C'))
        r = await self.move_06_07(jar)
        r = await self.dispense_step(r, "D", jar)

        if n_of_heads == 6:
            r = await self.move_07_08(jar)
            r = await self.dispense_step(r, "E", jar)
            r = await self.move_08_09(jar)
        elif n_of_heads == 4:
            r = await self.move_07_09(jar)

        r = await self.dispense_step(r, "F", jar)
        r = await self.move_09_10(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} ++").format('F'))
        r = await self.move_10_11(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +++").format('F'))
        r = await self.move_11_12(jar)

        r = await self.wait_for_jar_delivery(jar)

        return r

