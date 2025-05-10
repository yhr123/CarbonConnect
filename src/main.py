import os
import sys
import datetime # Added for now.year in footer

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, jsonify, session, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename # For file uploads
import uuid # For generating unique filenames

from src.models.models import db, User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus # Import db and models

# --- App Initialization and Configuration ---
def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "a_very_secret_key_for_dev_only_longer_and_more_random_!@#$%") # Essential for session management
    DATABASE_DIR = os.path.join(PROJECT_ROOT, "src", "database")
    DATABASE_NAME = "carbon_connect.db"
    DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(PROJECT_ROOT, "uploads") # For file uploads
    app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif", "pdf"}
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload size

    # Ensure upload folder and subdirectories exist
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    credits_upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "credits")
    verifications_upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "verifications")
    certificates_upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates") # For generated PDFs
    signed_certificates_upload_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed") # For signed PDFs

    for path in [credits_upload_path, verifications_upload_path, certificates_upload_path, signed_certificates_upload_path]:
        if not os.path.exists(path):
            os.makedirs(path)

    db.init_app(app) # Initialize SQLAlchemy with the app

    # --- Blueprints --- 
    from src.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    from src.routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")
    from src.routes.seller import seller_bp
    app.register_blueprint(seller_bp, url_prefix="/seller")
    from src.routes.buyer import buyer_bp
    app.register_blueprint(buyer_bp, url_prefix="/buyer")

    # --- Context Processors ---
    @app.context_processor
    def inject_user():
        user_id = session.get("user_id")
        if user_id:
            user = User.query.get(user_id)
            if user:
                user.is_authenticated = True 
                return dict(current_user=user)
        unauthenticated_user = type("UnauthenticatedUser", (), {"is_authenticated": False, "role": None, "username": "Guest"})()
        return dict(current_user=unauthenticated_user)

    # --- Jinja Custom Filters/Functions & Globals ---
    @app.template_filter("datetimeformat")
    def datetimeformat(value, format="%Y-%m-%d %H:%M:%S"):
        if value is None:
            return "N/A"
        return value.strftime(format)
    
    app.jinja_env.globals.update(
        datetimeformat=datetimeformat,
        UserRole=UserRole,
        CreditStatus=CreditStatus, # Added CreditStatus
        OrderStatus=OrderStatus,   # Added OrderStatus
        now=datetime.datetime.utcnow()
    )

    # --- Basic Routes (Publicly Accessible) ---
    @app.route("/")
    def index():
        return render_template("index.html", title="CarbonConnect - Home")

    @app.route("/privacy-policy")
    def privacy_policy():
        return render_template("privacy_policy.html", title="Privacy Policy")

    @app.route("/terms-of-service")
    def terms_of_service():
        return render_template("terms_of_service.html", title="Terms of Service")

    @app.route("/marketplace")
    def marketplace():
        query = CarbonCredit.query.filter_by(status=CreditStatus.APPROVED)
        keyword = request.args.get("keyword")
        project_type = request.args.get("project_type")
        min_price = request.args.get("min_price", type=float)
        max_price = request.args.get("max_price", type=float)
        sort_by = request.args.get("sort_by", "latest")

        if keyword:
            search_term = f"%{keyword}%"
            query = query.filter(or_(
                CarbonCredit.title.ilike(search_term),
                CarbonCredit.description.ilike(search_term),
                CarbonCredit.source_project_type.ilike(search_term),
                CarbonCredit.source_project_location.ilike(search_term)
            ))
        if project_type:
            query = query.filter(CarbonCredit.source_project_type == project_type)
        if min_price is not None:
            query = query.filter(CarbonCredit.price_per_unit >= min_price)
        if max_price is not None:
            query = query.filter(CarbonCredit.price_per_unit <= max_price)

        if sort_by == "price_asc":
            query = query.order_by(CarbonCredit.price_per_unit.asc())
        elif sort_by == "price_desc":
            query = query.order_by(CarbonCredit.price_per_unit.desc())
        elif sort_by == "quantity_desc":
            query = query.order_by(CarbonCredit.quantity.desc())
        else: 
            query = query.order_by(CarbonCredit.submitted_at.desc())
        
        page = request.args.get("page", 1, type=int)
        per_page = 9
        credits_page = query.paginate(page=page, per_page=per_page, error_out=False)
        credits = credits_page.items
        pagination = credits_page

        return render_template("marketplace.html", 
                                 title="Carbon Credit Marketplace", 
                                 credits=credits, 
                                 pagination=pagination,
                                 request_args=request.args)

    @app.route("/credit/<int:credit_id>")
    def credit_detail(credit_id):
        credit = CarbonCredit.query.get_or_404(credit_id)
        if credit.status != CreditStatus.APPROVED:
            user_id = session.get("user_id")
            temp_current_user = User.query.get(user_id) if user_id else None
            if not temp_current_user or (temp_current_user.role != UserRole.ADMIN and credit.seller_id != temp_current_user.id):
                flash("This carbon credit is currently not available for public viewing.", "warning")
                return redirect(url_for("marketplace"))
        return render_template("credit_detail.html", title=f"Credit Detail - {credit.title}", credit=credit)

    @app.route("/uploads/<path:subfolder>/<path:filename>")
    def uploaded_file(subfolder, filename):
        allowed_subfolders = ["credits", "verifications", "certificates", "certificates/signed"]
        if subfolder not in allowed_subfolders:
            return "Invalid file path", 404
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], subfolder)
        return send_from_directory(file_path, filename)

    @app.route("/api/health")
    def health_check():
        return jsonify({"status": "healthy", "message": "CarbonConnect API is running"}), 200

    @app.cli.command("init-db")
    def init_db_command():
        scripts_dir = os.path.join(PROJECT_ROOT, "scripts")
        original_sys_path = list(sys.path)
        sys.path.insert(0, PROJECT_ROOT) 
        sys.path.insert(0, scripts_dir)
        try:
            import init_db 
            with app.app_context(): 
                 init_db.initialize_database(app) 
            print("Database initialization command finished.")
        except ImportError as e:
            print(f"Error importing init_db script: {e}")
        except Exception as e:
            print(f"An error occurred during database initialization: {e}")
        finally:
            sys.path = original_sys_path 
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)

