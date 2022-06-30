# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging

from flask_restful import Resource, Api  # pylint: disable=import-error

from flask_restless_swagger import SwagAPIManager as APIManager  # pylint: disable=import-error

from alfa_CR6_backend.models import (Order, Jar, Event, Document)


class AlfaSwagAPIManager(APIManager):

    # ~ URL_PREFIX = '/db_api/v1'
    URL_PREFIX = '/db_api'

    EXCLUDE_COLUMNS_MAP = {
        # ~ 'order': ['jars'],
        # ~ 'jar': ['json_properties'],
    }

    @staticmethod
    def _universal_GET_preprocessor(*args, **kwargs):
        logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

    @staticmethod
    def _universal_GET_postprocessor(*args, **kwargs):
        logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

    @staticmethod
    def _universal_POST_preprocessor(*args, **kwargs):
        logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

    @staticmethod
    def _universal_POST_postprocessor(*args, **kwargs):
        logging.warning(f"args:{args}, kwargs:{kwargs}"[:200])

    def __init__(self, *args, **kwargs):

        super().__init__(
            preprocessors=dict(
                GET_SINGLE=[self._universal_GET_preprocessor],
                GET_MANY=[self._universal_GET_preprocessor],
                POST_SINGLE=[self._universal_POST_preprocessor],
                POST_MANY=[self._universal_POST_preprocessor]),
            postprocessors=dict(
                GET_SINGLE=[self._universal_GET_postprocessor],
                GET_MANY=[self._universal_GET_postprocessor],
                POST_SINGLE=[self._universal_POST_postprocessor],
                POST_MANY=[self._universal_POST_postprocessor]),
            *args,
            **kwargs)

        # ~ logging.warning(f"self.preprocessors:{self.preprocessors}, self.postprocessors:{self.postprocessors}")

        for model_class, model_name in ((Order, 'order'), (Jar, 'can'), (Event, 'event'), (Document, 'document')):

            self.create_api(model_class,
                            url_prefix=self.URL_PREFIX,
                            collection_name=model_class.__tablename__,
                            serializer=model_class.object_from_json,
                            deserializer=model_class.object_from_json,
                            results_per_page=10,
                            max_results_per_page=20,
                            exclude_columns=self.EXCLUDE_COLUMNS_MAP.get(model_name, []),
                            methods=['GET', 'POST', 'DELETE'],
                            allow_delete_many=True,
                            allow_functions=True)


class OrdersByJobId(Resource):

    def __init__(self, db, *args, **kwargs):

        self.db = db
        super().__init__(*args, **kwargs)

    def get(self, job_id):

        logging.warning(f"self.db:{self.db},job_id:{job_id}")

        data = []
        for order in self.db.session.query(Order).filter(Order.description == job_id).all():
            data.append(order.object_to_dict())

        ret = {'result': 'OK', 'data': data, 'count': len(data)}

        return ret


def init_restful_api(app, db):

    _api = Api(app)

    _api.add_resource(OrdersByJobId, '/api/orders_by_job_id/<job_id>', resource_class_kwargs={'db': db})
    
    return _api

def init_restless_api(app, db):

    manager = AlfaSwagAPIManager(app, session=db.session)

    # ~ logging.warning(f"manager:{manager}")

    return manager
