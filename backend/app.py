"""
Flask entry point.

Serves:
  - the REST API under /api/*  (menu, orders, inventory, reports, suppliers, auth)
  - the static frontend (HTML/CSS/JS) from ../frontend

Run:
    python backend/app.py
"""
import mysql.connector
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import Config
from routes.auth_routes import auth_bp
from routes.expenses_routes import expenses_bp
from routes.ingredients_routes import ingredients_bp
from routes.inventory_routes import inventory_bp
from routes.menu_routes import menu_bp
from routes.orders_routes import orders_bp
from routes.reports_routes import reports_bp
from routes.settings_routes import settings_bp
from routes.suppliers_routes import suppliers_bp
from utils.validators import error_response


def create_app():
    app = Flask(__name__, static_folder=Config.FRONTEND_DIR, static_url_path="")
    app.config.from_object(Config)
    CORS(app)  # harmless if frontend is same-origin; useful if served separately

    # ---- REST API blueprints -------------------------------------------------
    app.register_blueprint(menu_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "status": "ok", "service": "pos-backend"})

    # ---- Frontend (static) ----------------------------------------------------
    @app.get("/")
    def serve_index():
        return send_from_directory(Config.FRONTEND_DIR, "index.html")

    @app.get("/pos.html")
    def serve_pos():
        return send_from_directory(Config.FRONTEND_DIR, "pos.html")

    # ---- Error handlers (always return JSON, never HTML, for /api/*) ----------
    @app.errorhandler(404)
    def not_found(e):
        return error_response("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response("Method not allowed", 405)

    @app.errorhandler(mysql.connector.Error)
    def db_error(e):
        app.logger.error(f"Database error: {e}")
        return error_response("Database error occurred", 500)

    @app.errorhandler(500)
    def server_error(e):
        return error_response("Internal server error", 500)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
