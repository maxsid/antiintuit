from flask import Flask, abort, request, send_from_directory
from flask.logging import default_handler
from peewee import BackrefAccessor, Database

from antiintuit.api.functions import *
from antiintuit.basic import get_publish_id_from_link
from antiintuit.config import Config
from antiintuit.database import *
from antiintuit.logger import get_logger

__all__ = [
    "app",
    "run_server"
]

logger = get_logger("antiintuit", "api")
app = Flask(logger.name, static_folder=Config.STATIC_DIRECTORY)
app.logger.removeHandler(default_handler)

allow_models = {
    "courses": Course,
    "tests": Test,
    "questions": Question
}


@app.route("/<string:model_name>/<int:model_id>", defaults={'attr': None}, methods=["GET"])
@app.route("/<string:model_name>/<int:model_id>/<string:attr>", methods=["GET"])
def get_model_data_by_id(model_name, model_id, attr):
    if model_name not in allow_models:
        abort(404)
    model_class = allow_models[model_name]
    try:
        model = model_class.get_by_id(model_id)
    except model_class.DoesNotExist:
        abort(404)
    if attr is None:
        return jsonify_model(model)
    elif hasattr(model_class, attr) and isinstance(getattr(model_class, attr), BackrefAccessor):
        backref_query = get_query_from_args(getattr(model, attr))
        return jsonify([get_model_dict(sm) for sm in backref_query])
    elif hasattr(model_class, attr):
        return jsonify_model(model, only=[attr])
    else:
        abort(404)


@app.route("/<string:model_name>", methods=["GET"])
def find_model(model_name):
    if model_name not in allow_models:
        abort(404)
    model_class = allow_models[model_name]
    if "url" in request.args and hasattr(model_class, "publish_id") and len(request.args["url"]) > 5:
        url = request.args["url"].lower().strip()
        publish_id = get_publish_id_from_link(url)
        query = model_class.select().where(model_class.publish_id == publish_id).limit(1)
    else:
        query = get_query_from_args(model_class.select(), True)
    return jsonify([get_model_dict(c) for c in query])


@app.route("/image/<string:image_name>", methods=["GET"])
def send_file(image_name):
    return send_from_directory(Config.STATIC_DIRECTORY, image_name)


@app.route("/health")
def health_check():
    database: Database = Course._meta.database
    database.connection().ping(True)
    assert not database.is_closed(), "Database is closed!"
    return "OK"


def run_server(host: str = None, port: int = None, debug: bool = None, **kwargs):
    host, port = host or "0.0.0.0", port or 5000
    app.run(host, port, debug, **kwargs)
