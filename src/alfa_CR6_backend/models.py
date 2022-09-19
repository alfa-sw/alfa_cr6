# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import logging
import traceback
import json
import uuid
import time
# ~ import sqlite3
from datetime import (date, datetime)

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from jsonschema import validate  # pylint: disable=import-error

from sqlalchemy import (      # pylint: disable=import-error
    create_engine,
    Column,
    Unicode,
    UnicodeText,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    event,
    # ~ select,
    # ~ func,
)

import sqlalchemy.ext.declarative  # pylint: disable=import-error
from sqlalchemy.orm import (  # pylint: disable=import-error
    sessionmaker,
    relationship,
    validates,
    # ~ column_property,
)
from sqlalchemy.inspection import inspect  # pylint: disable=import-error
# ~ from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.exc import OperationalError

import iso8601                       # pylint: disable=import-error

Base = sqlalchemy.ext.declarative.declarative_base()

global_session = None


def set_global_session(db_session):

    global global_session  # pylint: disable=global-statement
    global_session = db_session


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

    global global_session  # pylint: disable=global-statement, global-variable-not-assigned

    assert global_session

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

    __tablename__ = None  # this has to assigned in inheriting class

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)
    date_created = Column(DateTime, default=datetime.utcnow)
    date_modified = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    json_properties = Column(UnicodeText, default="{}")
    description = Column(Unicode, default="")

    json_properties_schema = {}

    row_count_limt = 10 * 1000

    @validates('json_properties')
    def validate_json_properties(self, key, value):

        assert key == 'json_properties'

        if self.json_properties_schema:
            validate(instance=self.json_properties, schema=self.json_properties_schema)
        else:
            json.loads(value)

        return value

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

    def get_json_property(self, key, default):
        value = default
        try:
            _properties = json.loads(self.json_properties)
            value = _properties.get(key, default)
        except Exception as exc:  # pylint: disable=broad-except
            logging.error(f"self:{self}, exc:{exc}")
        return value

    def object_to_json(self, indent=2):

        data = self.object_to_dict()
        # ~ logging.warning(f"data:{data}")
        return json.dumps(data, indent=indent)

    def object_to_dict(self, excluded_fields=None, include_relationship=0):  # pylint: disable=too-many-branches

        if excluded_fields is None:
            excluded_fields = []

        # ~ data = {
            # ~ c.key: getattr(self, c.key)
            # ~ for c in inspect(self).mapper.column_attrs
            # ~ if c.key not in excluded_fields and
        # ~ }

        data = {'type': self.__tablename__}
        c_keys = set(inspect(self).mapper.columns.keys())
        for c_key in c_keys:
            if c_key not in excluded_fields:
                value = getattr(self, c_key)
                if isinstance(value, datetime):
                    data[c_key] = value.isoformat()
                elif c_key == 'json_properties':
                    data[c_key] = json.loads(value)
                else:
                    data[c_key] = value

        if include_relationship:
            r_keys = set(inspect(self).mapper.relationships.keys())
            for r_key in r_keys:
                value = getattr(self, r_key)
                if isinstance(value, list):
                    data[r_key] = []
                    for i in value:
                        if include_relationship == 1:
                            data[r_key].append(i.id)
                        elif include_relationship == 2:
                            data[r_key].append(i.object_to_dict())
                if isinstance(value, BaseModel):
                    if include_relationship == 1:
                        data[r_key] = value.id
                    elif include_relationship == 2:
                        data[r_key] = value.object_to_dict()

        return data

    @classmethod
    def object_from_json(cls, json_data):

        data = json.loads(json_data)
        obj = cls.object_from_dict(data)
        return obj

    @classmethod
    def object_from_dict(cls, data_dict):

        logging.warning(f"inspect(cls).mapper:{inspect(cls).mapper}")

        data_dict_cpy = {}
        for k, v in data_dict.items():
            try:
                if 'date' in k and isinstance(v, str):
                    val = iso8601.parse_date(v)
                elif k == 'json_properties' and isinstance(v, dict):
                    val = json.dumps(v, indent=2, ensure_ascii=False)
                else:
                    val = v
                data_dict_cpy[k] = val
            except Exception:  # pylint: disable=broad-except
                logging.warning(traceback.format_exc())

        obj = cls(**data_dict_cpy)

        return obj


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

    row_count_limt = 10 * 1000

    name = Column(Unicode(32), nullable=False, index=True)
    UniqueConstraint("name", "date_created")

    level = Column(Unicode(16))
    severity = Column(Unicode(16))
    source = Column(Unicode(32))

    def __str__(self):
        return "{}_{}".format(self.name, self.date_created)


class Jar(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "jar"

    row_count_limt = 10 * 1000

    status_choices = ['NEW', 'PROGRESS', 'DONE', 'ERROR', 'VIRTUAL']
    position_choices = ["REMOVED", "_", "LIFTR_UP", "LIFTR_DOWN", "IN", "OUT", "WAIT", "DELETED", ] + list("ABCDEF")

    status = Column(Unicode, default="NEW", doc=f"one of {status_choices}")
    index = Column(Integer, default=0, doc="position of this jar inside the order")
    size = Column(
        Integer, nullable=False,
        doc="one of [0x0, 0x1, 0x2, 0x3] corresponging to the combinations of MICROSWITCH 1 and 2")
    position = Column(Unicode, doc=f"one of {position_choices}", default="-")

    order_id = Column(Unicode, ForeignKey("order.id"), nullable=False)
    order = relationship("Order", back_populates="jars")

    # ~ is_deleted = Column(Unicode)
    reserved = Column(Unicode)

    machine_head = None
    t0 = None

    def update_live(self, machine_head=None, status=None, pos=None, t0=None):

        old = f"{self}"

        self.machine_head = machine_head

        if t0 is not None:
            self.t0 = t0

        if status is not None:
            self.status = status
            self.order.update_status()

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
            logging.error(f"{e}")

    def __str__(self):

        try:
            ret = "[m:{}, status:{}, position:{}, {}:{}]".format(
                self.machine_head, self.status, self.position, self.order.order_nr, self.index)
        except Exception as e:  # pylint: disable=broad-except
            logging.error(f"{e}")
            ret = f"{e}"

        return ret

    @property
    def barcode(self):
        order_ = self.order
        order_nr_ = order_ and order_.order_nr
        return order_nr_ and compile_barcode(order_nr_, self.index)

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
        # ~ _json_properties = json.loads(self.json_properties)
        # ~ return _json_properties.get("unknown_pigments", {})
        _order_json_properties = json.loads(self.order.json_properties)
        # ~ return _order_json_properties.get("unknown_pigments", [])
        return _order_json_properties.get("unknown_pigments", {})

    def get_ingredients_for_machine(self, m):

        ingredients = {}
        json_properties = json.loads(self.json_properties)
        ingredient_volume_map = json_properties["ingredient_volume_map"]
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

        # ~ logging.warning(f"{m.name} ingredients:{ingredients}")

        return ingredients


class Order(Base, BaseModel):  # pylint: disable=too-few-public-methods

    __tablename__ = "order"

    row_count_limt = 10 * 1000

    id = Column(Unicode, primary_key=True, nullable=False, default=generate_id)

    order_nr = Column(BigInteger, unique=True, nullable=False, default=generate_order_nr)
    jars = relationship("Jar", cascade="all, delete-orphan")

    json_properties = Column(Unicode, default='{"meta": "", "ingrdients": []}')

    is_deleted = Column(Unicode)
    reserved = Column(Unicode)
    inner_status = Column(Unicode)
    file_name = Column(Unicode)

    def __str__(self):
        return f"<Order object. status:{self.status}, order_nr:{self.order_nr}>"

    # ~ @property
    # ~ def file_name(self):

        # ~ return self.inner_file_name

    @property
    def status(self):

        ret = None
        if hasattr(self, 'inner_status'):
            if self.inner_status is None:
                self.update_status(global_session)
            ret = self.inner_status
        else:
            ret = self.update_status()
        return ret

    @property
    def deleted(self):

        ret = None
        if hasattr(self, 'is_deleted'):
            if self.is_deleted is None:
                self.update_deleted(global_session)
            ret = self.is_deleted
        else:
            ret = self.update_deleted()
        return ret

    def update_file_name(self, session=None):

        if self.file_name is None:
            meta = json.loads(self.json_properties).get("meta", {})
            self.file_name = meta.get("file name", '')
            if session:
                session.commit()

    def update_deleted(self, session=None):

        flag = (not self.jars) or [j for j in self.jars if j.position != "DELETED"]
        ret = '' if flag else 'yes'

        logging.warning(f"flag:{flag}, ret:{ret}")

        if hasattr(self, 'is_deleted'):
            self.is_deleted = ret
            logging.warning(f"self.is_deleted:{self.is_deleted}")

            if session:
                session.commit()

        return ret

    def update_status(self, session=None):

        sts_ = "NEW"

        counters = {}

        for j in self.jars:
            if j.position != "DELETED":
                counters.setdefault(j.status, 0)
                counters[j.status] += 1

        if counters.get("ERROR"):
            sts_ = "ERROR"
        elif counters.get("PROGRESS"):
            sts_ = "PROGRESS"
        elif counters.get("NEW") and counters.get("DONE"):
            sts_ = "PARTIAL"
        elif not counters.get("NEW") and counters.get("DONE"):
            sts_ = "DONE"

        if hasattr(self, 'inner_status'):
            self.inner_status = sts_

            if session:
                session.commit()

        return sts_


class Document(Base, BaseModel):  # pylint: disable=too-few-public-methods

    """ General purpose model (table) to let the integration of future features be smoother.
    """

    __tablename__ = "document"

    row_count_limt = 10 * 1000

    name = Column(Unicode(32), nullable=False, index=True)
    type = Column(UnicodeText, default='')
    UniqueConstraint('name', 'type', 'date_created')

    def __str__(self):
        return "{}_{}_{}".format(self.name, self.type, self.date_created)

# ~ #######################


def apply_table_alterations(engine):

    def update_order_file_names():

        Session = sessionmaker(bind=engine)
        _session = Session()

        t0 = time.time()
        cntr = 0
        if _session:
            query_ = _session.query(Order)
            for o in query_.all():
                o.update_file_name()
                cntr += 1
            _session.commit()
            logging.warning(f"cntr:{cntr}, dt:{time.time() - t0}")

    stmts = [
        ('ALTER TABLE "jar" ADD COLUMN reserved VARCHAR;', None),
        ('ALTER TABLE "order" ADD COLUMN is_deleted VARCHAR;', None),
        ('ALTER TABLE "order" ADD COLUMN reserved VARCHAR;', None),
        ('ALTER TABLE "order" ADD COLUMN inner_status VARCHAR;', None),
        ('ALTER TABLE "order" ADD COLUMN file_name VARCHAR;', update_order_file_names),
    ]

    successfully_executed = []
    try:
        from sqlalchemy import DDL  # pylint: disable=import-outside-toplevel
        for stmt, updater in stmts:
            try:
                engine.execute(DDL(stmt))
                successfully_executed.append(stmt)
                if updater:
                    updater()
            except OperationalError as e:  # pylint: disable=broad-except
                if "duplicate column name" in str(e):
                    logging.info(f"Error executing stmt:{stmt}, e:{e}")
                else:
                    logging.warning(traceback.format_exc())
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())

    logging.warning(f"successfully_executed({len(successfully_executed)}):{successfully_executed}")


class dbEventManager:

    def __init__(self, session):
        self.to_be_deleted_object_list = set([])
        self.session = session

    def do_delete_pending_objects(self, session, flush_context, instances=None):  # pylint: disable=unused-argument

        if self.to_be_deleted_object_list:
            for item in list(self.to_be_deleted_object_list)[:100]:
                cls, id_ = item
                obj = session.query(cls).filter(cls.id == id_).first()
                if obj:
                    session.delete(obj)
                self.to_be_deleted_object_list.remove(item)

            logging.warning(f"objects to be deleted:{len(self.to_be_deleted_object_list)}")

    def receive_after_update(self, mapper, connection, target):  # pylint: disable=unused-argument

        logging.warning(f"self:{self}, mapper({type(mapper)}):{mapper}, target:{target}")

    def receive_before_update(self, mapper, connection, target):  # pylint: disable=unused-argument

        logging.warning(f"self:{self}, mapper({type(mapper)}):{mapper}, target:{target}")

    def receive_before_insert(self, mapper, connection, target):  # pylint: disable=unused-argument

        exceeding_objects = target.check_size_limit(self.session)
        if exceeding_objects:
            for o in exceeding_objects:
                self.to_be_deleted_object_list.add((target.__class__, o.id))
            logging.warning(f"objects to be deleted:{len(self.to_be_deleted_object_list)}")

    def install_listeners(self):

        event.listen(self.session, 'after_flush', self.do_delete_pending_objects)

        # ~ event.listen(self.session, 'pending_to_persistent', self.receive_pending_to_persistent)

        for n in globals():
            m = globals().get(n)
            try:
                _cls_ = None
                if hasattr(sqlalchemy.ext.declarative, 'DeclarativeMeta'):
                    _cls_ = sqlalchemy.ext.declarative.DeclarativeMeta
                elif hasattr(sqlalchemy.ext.declarative, 'api'):
                    _cls_ = sqlalchemy.ext.declarative.api.DeclarativeMeta

                if isinstance(m, _cls_) and issubclass(m, BaseModel):
                    # ~ event.listen(m, 'after_update', self.receive_after_update)
                    # ~ event.listen(m, 'before_update', self.receive_before_update)
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

    apply_table_alterations(engine)

    e = dbEventManager(global_session)
    e.install_listeners()

    return global_session
