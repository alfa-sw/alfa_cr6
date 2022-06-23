# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging

from flask_restless_swagger import SwagAPIManager as APIManager  # pylint: disable=import-error

from alfa_CR6_backend.models import (Order, Jar, Event, Document)

URL_PREFIX = '/db_api/v1'

EXCLUDE_COLUMNS_MAP = {
    # ~ 'order': ['jars'],
    # ~ 'jar': ['json_properties'],
}

def _universal_GET_preprocessor(*args, **kwargs):

    logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])


def _universal_GET_postprocessor(*args, **kwargs):

    logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])


def _universal_POST_preprocessor(*args, **kwargs):

    logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])


def _universal_POST_postprocessor(*args, **kwargs):

    logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])



def init_restless_api(app, db):

    manager = APIManager(app,
                         # ~ preprocessors=dict(
                             # ~ GET_SINGLE=[_universal_GET_preprocessor],
                             # ~ GET_MANY=[_universal_GET_preprocessor],
                             # ~ POST_SINGLE=[_universal_POST_preprocessor],
                             # ~ POST_MANY=[_universal_POST_preprocessor]),
                         # ~ postprocessors=dict(
                             # ~ GET_SINGLE=[_universal_GET_postprocessor],
                             # ~ GET_MANY=[_universal_GET_postprocessor],
                             # ~ POST_SINGLE=[_universal_POST_postprocessor],
                             # ~ POST_MANY=[_universal_POST_postprocessor]),
                         session=db.session)

    for model_class, model_name in ((Order, 'order'), (Jar, 'can'), (Event, 'event'), (Document, 'document')):

        manager.create_api(model_class,
                           # ~ url_prefix=URL_PREFIX,
                           collection_name=model_class.__tablename__,
                           # ~ serializer=model_class.object_from_json,
                           # ~ deserializer=model_class.object_from_json,
                           results_per_page=10,
                           max_results_per_page=20,
                           exclude_columns=EXCLUDE_COLUMNS_MAP.get(model_name, []),
                           methods=['GET', 'POST', 'DELETE'],
                           allow_delete_many=True,
                           allow_functions=True)

    # ~ logging.warning(f"manager:{manager}")

    return manager
