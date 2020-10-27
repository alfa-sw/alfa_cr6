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
from datetime import datetime

from sqlalchemy import (create_engine, Column, Unicode, Integer, DateTime, ForeignKey, UniqueConstraint)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (sessionmaker, relationship, backref)

from jsonschema import validate

Base = declarative_base()


def generate_id():
    return str(uuid.uuid4())


class ModelCr6(object):

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_modified = Column(DateTime, default=datetime.utcnow)
    json_properties = Column(Unicode, default="{}")
    description = Column(Unicode(200))

    json_properties_schema = {}

    def validate_json_properties(self):

        ret = False

        try:
            _inst = json.loads(self.json_properties)
            validate(instance=_inst, schema=self.json_properties_schema)
            ret = True
        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        return ret

class User(Base, ModelCr6):

    __tablename__ = 'user'

    name = Column(Unicode(20), unique=True, nullable=False)
    password = Column(Unicode(20), nullable=False)
    role = Column(Unicode, default='OPERATOR')


class Command(Base, ModelCr6):  # pylint: disable=too-few-public-methods

    __tablename__ = 'command'
    name = Column(Unicode(20), unique=True, nullable=False)
    UniqueConstraint('name', 'date_created')

    channel = Column(Unicode(32), nullable=False)
    remote_address = Column(Unicode(16))
    status_code = Column(Integer, default=-1)

    # ~ row_count_limt = 10 * 1000

    def __str__(self):
        return "{}_{}".format(self.name, self.date_created)


class Event(Base, ModelCr6):  # pylint: disable=too-few-public-methods

    __tablename__ = 'event'
    name = Column(Unicode(32), nullable=False, index=True)
    UniqueConstraint('name', 'date_created')

    level = Column(Unicode(16))
    severity = Column(Unicode(16))
    source = Column(Unicode(32))

    # ~ row_count_limt = 100 * 1000

    def __str__(self):
        return "{}_{}".format(self.name, self.date_created)


class Order(Base, ModelCr6):

    __tablename__ = 'order'
    barcode = Column(Unicode(20), unique=True, nullable=False)
    status = Column(Unicode, default='NEW')

    def __str__(self):
        return f"<Order object. status:{self.status}, barcode:{self.barcode}>"


class Jar(Base, ModelCr6):

    __tablename__ = 'jar'
    status = Column(Unicode, default='NEW')
    position = Column(Unicode, default='FTC_1')
    order_id = Column(Unicode, ForeignKey('order.id'), unique=True, nullable=False)
    order = relationship("Order", backref=backref("jar", uselist=False))

    def __str__(self):
        return f"<Jar object. status:{self.status}, position:{self.position}, order.barcode:{self.order.barcode}>"

    def move(self):

        r = self.validate_json_properties()
        logging.warning(f"TBI r:{r}, { self }")


def init_models(sqlite_connect_string):

    engine = create_engine(sqlite_connect_string)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    return session
