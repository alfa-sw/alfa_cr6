# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import os
# ~ import logging
# ~ import traceback
# ~ import json
import uuid
from datetime import datetime


from sqlalchemy import (create_engine, Column, Unicode, DateTime, ForeignKey)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (sessionmaker, relationship, backref)

Base = declarative_base()


def generate_id():
    return str(uuid.uuid4())


class ModelCr6(object):

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_modified = Column(DateTime, default=datetime.utcnow)
    json_properties = Column(Unicode)
    description = Column(Unicode(200))

    json_properties_schema = "{}"

class Order(Base, ModelCr6):

    __tablename__ = 'order'
    barcode = Column(Unicode(20), unique=True, nullable=False)
    status = Column(Unicode, default='NEW')

class Jar(Base, ModelCr6):

    __tablename__ = 'jar'
    status = Column(Unicode, default='NEW')
    position = Column(Unicode, default='BARCODE READER')
    order_id = Column(Unicode, ForeignKey('order.id'), unique=True, nullable=False)
    order = relationship("Order", backref=backref("jar", uselist=False))

    def move(self):
        pass


def init_models(sqlite_connect_string):

    if sqlite_connect_string.split("sqlite:///")[1:]:
        pth = os.path.dirname(os.path.abspath(sqlite_connect_string.split("sqlite:///")[1]))
        if not os.path.exists(pth):
            os.makedirs(pth)

    engine = create_engine(sqlite_connect_string)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    return session
