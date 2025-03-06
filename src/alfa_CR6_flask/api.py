# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging
import traceback
import json
import redis

from datetime import datetime, timedelta

from sqlalchemy.inspection import inspect  # pylint: disable=import-error

from flask_restful import Resource, Api  # pylint: disable=import-error

from alfa_CR6_backend.models import (Order, Jar, Event, Document)

# ~ from flask_restless_swagger import SwagAPIManager as APIManager  # pylint: disable=import-error, import-outside-toplevel
from flask_restless import APIManager  # pylint: disable=import-error, import-outside-toplevel
from flask_restless.serialization import DefaultSerializer, DefaultDeserializer  # pylint: disable=import-error, import-outside-toplevel
from flask import request, Response


URL_PREFIX = '/api/v1'
REDIS_BUS = redis.Redis()

class OrderByJobId(Resource):  # pylint: disable=too-few-public-methods

    def __init__(self, db, *args, **kwargs):

        self.db = db
        super().__init__(*args, **kwargs)

    def get(self, job_id):

        logging.warning(f"self.db:{self.db},job_id:{job_id}")

        data = []
        query_ = self.db.session.query(Order).filter(Order.description == job_id)
        query_ = query_.join(Jar).filter(Jar.position != "DELETED").limit(50)

        for order in query_.all():
            data.append(order.object_to_dict(relationships=True))

        ret = {'result': 'OK', 'data': data, 'count': len(data)}

        return ret


class FilteredOrders(Resource):  # pylint: disable=too-few-public-methods

    def __init__(self, db, *args, **kwargs):

        self.db = db
        super().__init__(*args, **kwargs)

    def get(self):

        args = request.args.to_dict()

        if not args:
            return {"error": "Bad Request, filter parameters are required"}, 400

        query_ = self.db.session.query(Order)
        if 'last_hours_interval' in args:
            last_hours_interval = args.pop('last_hours_interval')
            try:
                last_hours_interval = int(last_hours_interval)
            except ValueError:
                return {"error": "Bad Request, 'last_hours_interval' parameter must be an integer"}, 400
            now = datetime.utcnow()
            required_dt = now - timedelta(hours=last_hours_interval)
            query_ = query_.filter(Order.date_modified >= required_dt)

        for arg, value in args.items():
            if hasattr(Order, arg):
                query_ = query_.filter(getattr(Order, arg) == value)
                # logging.warning(f"Query after filtering by {arg}: {query_}")
            else:
                return {"error": f"Bad Request, '{arg}' is not a valid filter parameter"}, 400

        res_ = query_.all()
        # logging.warning(f"query len: {query_.count()}")
        res = {
            'data': [r.object_to_dict() for r in res_],
            'meta': {
                'total': len(res_)
            }
        }

        return res

class HeadStatusApi(Resource):  # pylint: disable=too-few-public-methods

    def get(self, head_id):

        def get_head_status_via_redis(head_id):
            status = {}
            ret = REDIS_BUS.get(f"device:machine:status@5{head_id}")
            if ret:
                ret = ret.decode()
                status = json.loads(ret)
            return status

        if head_id < 0 or head_id > 6:
            response = {
                "status": "error",
                "message": "Invalid head_id. Must be between 0 and 6.",
                "data": None
            }
            return Response(json.dumps(response, indent=4), mimetype="application/json", status=400)

        status = get_head_status_via_redis(head_id)

        if not status:
            response = {
                "status": "error",
                "message": f"Head {head_id} not available",
                "data": None
            }
            response_json = json.dumps(response, indent=4)
            return Response(response_json, mimetype="application/json", status=404)

        response = {
            "status": "success",
            "message": "",
            "data": status
        }
        response_json = json.dumps(response, indent=4)
        return Response(response_json, mimetype="application/json", status=200)

    def post(self, head_id):
        return Response(json.dumps({"message": "Method Not Allowed"}), mimetype="application/json", status=405)

    def put(self, head_id):
        return Response(json.dumps({"message": "Method Not Allowed"}), mimetype="application/json", status=405)

    def delete(self, head_id):
        return Response(json.dumps({"message": "Method Not Allowed"}), mimetype="application/json", status=405)

    def patch(self, head_id):
        return Response(json.dumps({"message": "Method Not Allowed"}), mimetype="application/json", status=405)


def init_restful_api(app, db):

    _api = Api(app)

    _api.add_resource(OrderByJobId, f'{URL_PREFIX}/order_by_job_id/<job_id>', resource_class_kwargs={'db': db})
    _api.add_resource(FilteredOrders, f'{URL_PREFIX}/filtered_orders', resource_class_kwargs={'db': db})
    _api.add_resource(HeadStatusApi, f'{URL_PREFIX}/head_status/<int:head_id>')

    return _api


def init_restless_api(app, db):

    class CustomSerializer(DefaultSerializer):

        def serialize_attributes(self, instance, only=None):

            ret = super().serialize_attributes(instance, only)

            if ret.get('json_properties') is not None:
                try:
                    ret['json_properties'] = json.loads(ret['json_properties'])
                except Exception:
                    logging.error(traceback.format_exc())

            return ret

    class CustomDeserializer(DefaultDeserializer):

        def __init__(self, session, model, api_manager):

            # ~ logging.warning(f"only:{only}, instance:{instance}"[:140])

            self.model_class = model
            super().__init__(session, model, api_manager)

        def deserialize(self, document):

            logging.warning(f"document:{document}"[:140])
            return self.model_class.object_from_dict(document)

    class CustomAPIManager(APIManager):          # pylint: disable=too-few-public-methods

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

            # ~ super().__init__(
            # ~ preprocessors=dict(
            # ~ GET_SINGLE=[self._universal_GET_preprocessor],
            # ~ GET_MANY=[self._universal_GET_preprocessor],
            # ~ POST_SINGLE=[self._universal_POST_preprocessor],
            # ~ POST_MANY=[self._universal_POST_preprocessor]),
            # ~ postprocessors=dict(
            # ~ GET_SINGLE=[self._universal_GET_postprocessor],
            # ~ GET_MANY=[self._universal_GET_postprocessor],
            # ~ POST_SINGLE=[self._universal_POST_postprocessor],
            # ~ POST_MANY=[self._universal_POST_postprocessor]),
            # ~ *args,
            # ~ **kwargs)
            super().__init__(
                preprocessors=dict(
                    GET_RESOURCE=[self._universal_GET_preprocessor],
                    GET_COLLECTION=[self._universal_GET_preprocessor],
                    POST_RESOURCE=[self._universal_POST_preprocessor]),
                postprocessors=dict(
                    GET_RESOURCE=[self._universal_GET_postprocessor],
                    GET_COLLECTION=[self._universal_GET_postprocessor],
                    POST_RESOURCE=[self._universal_POST_postprocessor]),
                *args,
                **kwargs)

            # ~ logging.warning(f"self.preprocessors:{self.preprocessors}, self.postprocessors:{self.postprocessors}")

            for model_class, model_name, primary_key in (
                # ~ (Order, 'order', 'order_nr'),
                (Order, 'order', 'id'),
                (Jar, 'can', 'id'),
                (Event, 'event', 'id'),
                (Document, 'document', 'id')
            ):

                attributes = set(inspect(model_class).mapper.columns.keys())
                relationships = set(inspect(model_class).mapper.relationships.keys())

                ser_ = CustomSerializer(model_class, model_name, api_manager=self, primary_key='id')
                deser_ = CustomDeserializer(session=db.session, model=model_class, api_manager=self)

                self.create_api(model_class,
                                url_prefix=URL_PREFIX,
                                # ~ collection_name=model_class.__tablename__,
                                collection_name=model_name,
                                primary_key=primary_key,
                                serializer=ser_,
                                deserializer=deser_,
                                methods=['GET', 'POST', 'DELETE'])

    manager = CustomAPIManager(app, session=db.session)

    # ~ logging.warning(f"manager:{manager}")

    return manager
