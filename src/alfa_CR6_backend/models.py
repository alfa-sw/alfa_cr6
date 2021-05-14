# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import os
import logging
import traceback
import json
import uuid
import time
from datetime import date
from datetime import datetime

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from sqlalchemy import (      # pylint: disable=import-error
    create_engine,
    Column,
    Unicode,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    event)

import sqlalchemy.ext.declarative  # pylint: disable=import-error
from sqlalchemy.orm import sessionmaker, relationship    # pylint: disable=import-error

from jsonschema import validate  # pylint: disable=import-error

Base = sqlalchemy.ext.declarative.declarative_base()

global_session = None


def generate_id():
    return str(uuid.uuid4())


def compile_barcode(order_nr, index):
    barcode = int(order_nr) + int(index) % 1000
    return str(barcode)


def decompile_barcode(barcode):
    order_nr = 1000 * (int(barcode) // int(1000))
    index = int(barcode) % 1000
    return int(order_nr), int(index)


def generate_order_nr():

    global global_session  # pylint: disable=global-statement

    today = date.today()

    date_number = (
        today.year % 100 * 10000 + today.month * 100 + today.day) * 1000 * 1000

    order = (
        global_session.query(Order)
        .filter(Order.order_nr > date_number)
        .order_by(Order.order_nr.desc())
        .first()
    )
    if order:
        new_number = order.order_nr + 1000
    else:
        new_number = date_number + 1000

    order_nr = int(new_number)

    logging.warning(f"order_nr:{order_nr}, date_number:{date_number}, order:{order}")

    return order_nr


# ~ #######################
class BaseModel:  # pylint: disable=too-few-public-methods

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    json_properties = Column(Unicode, default="{}")
    description = Column(Unicode(200))

    json_properties_schema = {}

    row_count_limt = 10000

    def validate_json_properties(self, instance):

        ret = None

        try:
            validate(instance=instance, schema=self.json_properties_schema)
            ret = json.dumps(instance, indent=2)
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        return ret

    @classmethod
    def check_size_limit(cls, session):

        exceeding_objects = []
        if cls.row_count_limt > 0:
            try:
                query_ = session.query(cls)
                row_count = query_.count()
                exceeding = max(0, row_count - cls.row_count_limt)
                if exceeding > 0:
                    exceeding += int(cls.row_count_limt * 0.1)  # below watermark
                    exceeding_objects = query_.order_by(cls.date_created).limit(exceeding)
                    msg = "cls:{}, row_count:{}, exceeding:{}, exceeding_objects.count():{}".format(
                        cls, row_count, exceeding, exceeding_objects.count())
                    logging.warning(msg)
            except Exception as e:  # pylint: disable=broad-except
                logging.error(e)

        return exceeding_objects


class User(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "user"

    name = Column(Unicode(20), unique=True, nullable=False)
    password = Column(Unicode(20), nullable=False)
    role = Column(Unicode, default="OPERATOR")


class Command(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "command"
    name = Column(Unicode(20), unique=True, nullable=False)
    UniqueConstraint("name", "date_created")

    channel = Column(Unicode(32), nullable=False)
    remote_address = Column(Unicode(16))
    status_code = Column(Integer, default=-1)

    # ~ row_count_limt = 10 * 1000

    def __str__(self):
        return "{}_{}".format(self.name, self.date_created)


class Event(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "event"
    name = Column(Unicode(32), nullable=False, index=True)
    UniqueConstraint("name", "date_created")

    level = Column(Unicode(16))
    severity = Column(Unicode(16))
    source = Column(Unicode(32))

    # ~ row_count_limt = 100 * 1000

    def __str__(self):
        return "{}_{}".format(self.name, self.date_created)


class Order(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "order"
    order_nr = Column(BigInteger, unique=True, nullable=False, default=generate_order_nr)
    jars = relationship("Jar")

    json_properties = Column(Unicode, default='{"meta": "", "ingrdients": []}')

    def __str__(self):
        return f"<Order object. status:{self.status}, order_nr:{self.order_nr}>"

    @property
    def status(self):
        sts_ = "NEW"
        new_jars = [j for j in self.jars if j.status == 'NEW']
        progress_jars = [j for j in self.jars if j.status == 'PROGRESS']
        error_jars = [j for j in self.jars if j.status == 'ERROR']
        done_jars = [j for j in self.jars if j.status == 'DONE']
        if error_jars:
            sts_ = "ERROR"
        elif progress_jars:
            sts_ = "PROGRESS"
        elif new_jars and done_jars:
            sts_ = "PARTIAL"
        elif not new_jars and done_jars:
            sts_ = "DONE"

        return sts_


class Jar(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "jar"
    status = Column(
        Unicode, default="NEW", doc="one of ['NEW', 'PROGRESS', 'DONE', 'ERROR', ]")
    index = Column(Integer, default=0, doc="position of this jar inside the order")
    size = Column(
        Integer,
        nullable=False,
        doc="one of [0x0, 0x1, 0x2, 0x3] corresponging to the combinations of MICROSWITCH 1 and 2")
    position = Column(
        Unicode,
        doc="one of [None, 'step_1', 'step_1,step_2', 'step_2', 'step_2,step_3', ..., 'step_11,step_12', 'step_12']")

    order_id = Column(Unicode, ForeignKey("order.id"), nullable=False)
    order = relationship("Order", back_populates="jars")

    machine_head = None
    t0 = None

    def update_live(self, machine_head=None, status=None, pos=None, t0=None):

        old = f"{self}"

        self.machine_head = machine_head

        if t0 is not None:
            self.t0 = t0

        if status is not None:
            self.status = status

        if pos is not None:
            self.position = pos

        if self.t0 is not None:
            self.description = "d:{:.1f}".format(time.time() - self.t0)

        new = f"{self}"
        logging.warning(f"old:{old}, new:{new}.")

        try:
            app = QApplication.instance()
            app.main_window.debug_page.update_status()
        except Exception as e:  # pylint: disable=broad-except
            logging.error(e)

    def __str__(self):
        return "[m:{}, status:{}, position:{}, {}:{}]".format(
            self.machine_head, self.status, self.position, self.order.order_nr, self.index)

    @property
    def barcode(self):
        return compile_barcode(self.order.order_nr, self.index)

    @property
    def extra_lines_to_print(self):
        _order_json_properties = json.loads(self.order.json_properties)
        return _order_json_properties.get("extra_lines_to_print", [])

    @property
    def insufficient_pigments(self):
        _json_properties = json.loads(self.json_properties)
        return _json_properties.get("insufficient_pigments", {})

    @property
    def unknown_pigments(self):
        _json_properties = json.loads(self.json_properties)
        return _json_properties.get("unknown_pigments", {})

    def get_ingredients_for_machine(self, m):
        json_properties = json.loads(self.json_properties)
        ingredient_volume_map = json_properties["ingredient_volume_map"]
        ingredients = {}
        for pigment_name in ingredient_volume_map.keys():
            try:
                val_ = ingredient_volume_map \
                    and ingredient_volume_map.get(pigment_name) \
                    and ingredient_volume_map[pigment_name].get(m.name)
                if val_:
                    ingredients[pigment_name] = val_
            except Exception as e:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
                QApplication.instance().handle_exception(e)

        logging.warning(f"{m.name} ingredients:{ingredients}")

        return ingredients


# ~ #######################
class dbEventManager:

    def __init__(self, session):
        self.to_be_deleted_object_list = set([])
        self.session = session

    def do_delete_pending_objects(self, session, flush_context, instances=None):  # pylint: disable=unused-argument

        for item in list(self.to_be_deleted_object_list)[:50]:
            cls, id_ = item
            session.query(cls).filter(cls.id == id_).delete()
            self.to_be_deleted_object_list.remove(item)

    def receive_before_insert(self, mapper, connection, target):  # pylint: disable=unused-argument

        exceeding_objects = target.check_size_limit(self.session)
        if exceeding_objects:
            for o in exceeding_objects:
                self.to_be_deleted_object_list.add((target.__class__, o.id))

    def install_listeners(self):

        event.listen(self.session, 'after_flush', self.do_delete_pending_objects)

        # ~ event.listen(self.session, 'pending_to_persistent', self.receive_pending_to_persistent)

        for n in globals():
            m = globals().get(n)
            try:
                if isinstance(m, sqlalchemy.ext.declarative.api.DeclarativeMeta) and issubclass(m, BaseModel):
                    if m.row_count_limt > 0:
                        event.listen(m, 'before_insert', self.receive_before_insert)
                        logging.info("m:{}, type(m):{}".format(m, type(m)))
            except Exception as e:  # pylint: disable=broad-except
                logging.error(e)


def init_models(sqlite_connect_string):

    toks = sqlite_connect_string.split("sqlite:///")
    pth = toks[1:] and toks[1]
    if pth:
        pth = os.path.dirname(os.path.abspath(pth))
        if not os.path.exists(pth):
            os.makedirs(pth)

    engine = create_engine(sqlite_connect_string)
    Base.metadata.create_all(engine)

    global global_session  # pylint: disable=global-statement

    Session = sessionmaker(bind=engine)
    global_session = Session()

    e = dbEventManager(global_session)
    e.install_listeners()

    return global_session
