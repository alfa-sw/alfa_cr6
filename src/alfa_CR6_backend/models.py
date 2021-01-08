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

from sqlalchemy import (
    create_engine,
    Column,
    Unicode,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from jsonschema import validate  # pylint: disable=import-error

Base = declarative_base()

global_session = None

def compile_barcode(order_nr, index):
    return int(order_nr) + int(index) % 1000


def decompile_barcode(barcode):
    order_nr = 1000 * (int(barcode) // int(1000))
    index = int(barcode) % 1000
    return int(order_nr), int(index)


def generate_order_nr():

    global global_session  # pylint: disable=global-statement

    today = date.today()
    midnight = datetime.combine(today, datetime.min.time())
    daily_cntr = 0

    order = (
        global_session.query(Order)
        .filter(Order.date_created >= midnight)
        .order_by(Order.order_nr.desc())
        .first()
    )
    # ~ logging.warning(f"order:{order}")
    if order:
        daily_cntr = (order.order_nr / 1000) % 1000

    order_nr = (
        (today.year % 100 * 10000 + today.month * 100 + today.day) * 1000
        + daily_cntr
        + 1
    )
    order_nr = int(order_nr * 1000)

    # ~ logging.warning(f"order_nr:{order_nr}")

    return order_nr


def generate_id():
    return str(uuid.uuid4())


class BaseModel(object):  # pylint: disable=too-few-public-methods

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)
    date_created = Column(DateTime, default=datetime.now)
    date_modified = Column(DateTime, default=datetime.now)
    json_properties = Column(Unicode, default="{}")
    description = Column(Unicode(200))

    json_properties_schema = {}

    def validate_json_properties(self, instance):

        ret = None

        try:
            validate(instance=instance, schema=self.json_properties_schema)
            ret = json.dumps(instance, indent=2)
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        return ret


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
    order_nr = Column(
        BigInteger, unique=True, nullable=False, default=generate_order_nr
    )
    # ~ status = Column(Unicode, default="NEW")
    jars = relationship("Jar")

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
        Unicode, default="NEW", doc="one of ['NEW', 'PROGRESS', 'DONE', 'ERROR', ]"
    )
    index = Column(Integer, default=0, doc="position of this jar inside the order")
    size = Column(
        Integer,
        nullable=False,
        doc="one of [0x0, 0x1, 0x2, 0x3] corresponging to the combinations of MICROSWITCH 1 and 2",
    )
    position = Column(
        Unicode,
        doc="one of [None, 'step_1', 'step_1,step_2', 'step_2', 'step_2,step_3', ..., 'step_11,step_12', 'step_12']",
    )

    order_id = Column(Unicode, ForeignKey("order.id"), nullable=False)
    order = relationship("Order", back_populates="jars")

    machine_head = None
    t0 = None

    def update_live(self, machine_head=None, status=None, pos=None, t0=None):

        logging.warning(f"{self}")

        self.machine_head = machine_head

        if t0 is not None:
            self.t0 = t0

        if status is not None:
            self.status = status

        if pos is not None:
            self.position = pos

        if self.t0 is not None:
            self.description = "d:{:.1f}".format(time.time() - self.t0)

        try:
            app = QApplication.instance()
            app.main_window.debug_status_view.update_status()
        except Exception as e:
            logging.error(e)

    def __str__(self):
        # ~ return f"<Jar object. status:{self.status}, position:{self.position}, barcode:{self.barcode}>"
        return f"[m:{self.machine_head}, status:{self.status}, position:{self.position}, {self.order.order_nr}:{self.index}]"

    @property
    def barcode(self):
        return compile_barcode(self.order.order_nr, self.index)


def init_models(sqlite_connect_string):

    global global_session  # pylint: disable=global-statement

    toks = sqlite_connect_string.split("sqlite:///")
    pth = toks[1:] and toks[1]
    if pth:
        pth = os.path.dirname(os.path.abspath(pth))
        if not os.path.exists(pth):
            os.makedirs(pth)

    engine = create_engine(sqlite_connect_string)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    global_session = Session()

    return global_session
