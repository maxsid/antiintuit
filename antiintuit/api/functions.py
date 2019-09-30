from datetime import date, datetime, time

import ujson
from flask import request, abort, Response
from peewee import ModelBase, ModelSelect, fn
from playhouse.shortcuts import model_to_dict

from antiintuit.database import Course, Test, Question

__all__ = [
    "get_model_dict",
    "jsonify",
    "jsonify_model",
    "get_fields_by_names",
    "get_query_from_args",
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


def get_query_from_args(query: ModelSelect, require_where=False):
    page, where_count = 1, 0
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
        elif arg_name.startswith("where:"):
            operations = arg_name.split(":")
            fields = get_fields_by_names(query.model, [operations[-1]])
            if len(fields) == 0:
                abort(400)
            else:
                field = fields[0]
            if len(operations) == 2:
                query = query.where(fn.LOWER(field) == arg_value.lower())
            elif operations[1] == "not":
                query = query.where(fn.LOWER(field) != arg_value.lower())
            elif operations[1] == "like":
                query = query.where(fn.LOWER(field) % get_like_query(arg_value))
            elif operations[1] == "not_like":
                query = query.where(~(fn.LOWER(field) % get_like_query(arg_value)))
            else:
                abort(400)
            where_count += 1
    if require_where and where_count == 0:
        abort(400)
    return query.paginate(page, 10)
