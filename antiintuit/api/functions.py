import math
from datetime import date, datetime, time

import ujson
from flask import request, abort, Response
from peewee import ModelBase, ModelSelect, fn
from playhouse.shortcuts import model_to_dict

from antiintuit.config import Config
from antiintuit.database import Course, Test, Question

__all__ = [
    "get_model_dict",
    "jsonify",
    "jsonify_model",
    "get_fields_by_names",
    "get_data_for_sending",
    "get_like_query"
]

basic_exceptions = {
    Course: [Course.last_scan_at, Course.created_at],
    Test: [Test.watcher, Test.created_at, Test.last_scan_at],
    Question: [Question._variants, Question.original_html, Question.last_update_at,
               Question.locked_at, Question.locked_by, Question.created_at]
}


def get_fields_by_names(model_or_class, field_list: list) -> list:
    model_class = model_or_class if isinstance(model_or_class, ModelBase) else type(model_or_class)
    exists_fields = filter(lambda ex: hasattr(model_class, ex), field_list or list())
    return [getattr(model_class, ex) for ex in exists_fields]


def get_model_dict(model, exclude: list or str = None, only: list or str = None) -> dict:
    model_class = type(model)
    exclude = exclude.split(",") if isinstance(exclude, str) else exclude
    only = only.split(",") if isinstance(only, str) else only
    exclude = get_fields_by_names(model_class, exclude)
    exclude.extend(basic_exceptions.get(model_class, list()))
    only = get_fields_by_names(model_class, only)
    exclude, only = exclude or None, only or None
    data = model_to_dict(model, False, exclude=exclude, only=only)
    if hasattr(model_class, "variants") and "_variants" in data:
        del data["_variants"]
        data["variants"] = model.variants
    if hasattr(model_class, "link") and "publish_id" in data:
        del data["publish_id"]
        data["link"] = model.link
    for name, value in filter(lambda item: isinstance(item[1], (datetime, date, time)), data.items()):
        data[name] = value.isoformat()
    return data


def jsonify(obj) -> Response:
    json_response = ujson.dumps(obj, ensure_ascii=False)
    return Response(json_response, content_type="application/json; charset=utf-8")


def jsonify_model(model, exclude: list or str = None, only: list or str = None) -> Response:
    data = get_model_dict(model, exclude, only)
    return jsonify(data)


def get_like_query(like_value: str) -> str:
    query_words = like_value.lower().split()
    return "%" + "%".join(map(lambda w: w.strip(), query_words)) + "%"


def get_expression_by_operator(field, value: str, operator=None):
    if operator is None or operator == "equal":
        return fn.LOWER(field) == value.lower()
    elif operator == "not" or operator == "not_equal":
        return fn.LOWER(field) != value.lower()
    elif operator == "like":
        return fn.LOWER(field) % get_like_query(value)
    elif operator == "not_like":
        return ~(fn.LOWER(field) % get_like_query(value))
    return None


def get_data_for_sending(query: ModelSelect, require_where=False):
    page, limit, where_count = 1, Config.DEFAULT_API_LIST_LIMIT, 0
    for arg_name, arg_value in request.args.items():
        if len(arg_value) == 0:
            continue
        if arg_name in ("order_by", "order_by_desc"):
            fields = get_fields_by_names(query.model, [arg_value])
            if len(fields) == 0:
                abort(400)
            field = fields[0] if "order_by" == arg_name else fields[0].desc()
            query = query.order_by(field)
        elif arg_name == "page":
            page = int(arg_value)
        elif arg_name == "limit":
            limit = int(arg_value)
            limit = limit if limit <= Config.MAX_API_LIST_LIMIT else Config.MAX_API_LIST_LIMIT
        elif arg_name.startswith("where:") or arg_name.startswith("or_where:"):
            operations = arg_name.split(":")
            is_or_where = operations[0] == "or_where"
            if len(operations) == 2:
                operator = "equal"
            else:
                operator = operations[1]
            fields = get_fields_by_names(query.model, [operations[-1]])
            if len(fields) == 0:
                abort(400)
            else:
                field = fields[0]
            expression = get_expression_by_operator(field, arg_value, operator)
            if expression is None:
                abort(400)
            if is_or_where:
                query = query.orwhere(expression)
            else:
                query = query.where(expression)
            where_count += 1
    if require_where and where_count == 0:
        abort(400)
    count = query.count()
    if count == 0:
        abort(404)
    pages_count = math.ceil(count / limit)
    data = [get_model_dict(sm) for sm in query.paginate(page, limit)]
    return {
        "data": data,
        "page": page,
        "pages": pages_count,
        "count": count,
        "limit": limit
    }
