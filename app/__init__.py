import os
from flask import Flask, jsonify

from config.config import config_by_name
from app.extensions import db, migrate, cors, jwt
from app.keepalive import start_keepalive_pinger


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    if config_name == "production":
        config_by_name["production"].validate()

    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB request cap (uploads are capped at 5MB)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    jwt.init_app(app)

    with app.app_context():
        from app import models  # noqa: F401  (register models with SQLAlchemy)

    register_blueprints(app)
    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    start_keepalive_pinger()

    return app


def register_blueprints(app):
    from app.routes.auth import bp as auth_bp
    from app.routes.categories import bp as categories_bp
    from app.routes.opportunities import bp as opportunities_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.saved_opportunities import bp as saved_bp
    from app.routes.teacher_questions import bp as teacher_questions_bp
    from app.routes.teacher_tests import bp as teacher_tests_bp
    from app.routes.study_materials import bp as study_materials_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.uploads import bp as uploads_bp

    for blueprint in (
        auth_bp,
        categories_bp,
        opportunities_bp,
        reports_bp,
        saved_bp,
        teacher_questions_bp,
        teacher_tests_bp,
        study_materials_bp,
        admin_bp,
        uploads_bp,
    ):
        app.register_blueprint(blueprint)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": getattr(e, "description", "Bad request")}), 400

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify({"error": "Internal server error"}), 500
