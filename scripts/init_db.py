import os
import sys
from werkzeug.security import generate_password_hash

# Add project root to Python path to allow direct imports from src
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask
from src.models.models import db, User, UserRole, CarbonCredit, CreditStatus, Order, UploadedFile

# --- Configuration ---
DATABASE_DIR = os.path.join(PROJECT_ROOT, "src", "database")
DATABASE_NAME = "carbon_connect.db"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)

def create_app_for_db_init():
    """Creates a minimal Flask app for database initialization context."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app

def initialize_database(app):
    """Creates database and tables, then seeds initial data."""
    with app.app_context():
        # Ensure the database directory exists
        if not os.path.exists(DATABASE_DIR):
            os.makedirs(DATABASE_DIR)
            print(f"Created database directory: {DATABASE_DIR}")

        # Drop all tables if they exist (for a clean init) - use with caution
        # db.drop_all()
        # print("Dropped existing tables.")

        # Create all tables
        db.create_all()
        print(f"Database tables created at {DATABASE_PATH}")

        # Seed initial data
        seed_data()
        print("Initial data seeded.")

def seed_data():
    """Seeds the database with initial necessary data."""
    # 1. Admin User
    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin",
            email="admin@carbonconnect.local",
            password_hash=generate_password_hash("AdminPassword123!", method="pbkdf2:sha256"),
            role=UserRole.ADMIN,
            company_name="CarbonConnect Platform",
            is_active=True
        )
        db.session.add(admin_user)
        print("Admin user created.")

    # 2. Example Seller User
    if not User.query.filter_by(username="test_seller").first():
        seller_user = User(
            username="test_seller",
            email="seller@example.com",
            password_hash=generate_password_hash("SellerPassword123!", method="pbkdf2:sha256"),
            role=UserRole.SELLER,
            company_name="Green Ventures Ltd.",
            is_active=True
        )
        db.session.add(seller_user)
        print("Example seller user created.")

    # 3. Example Buyer User
    if not User.query.filter_by(username="test_buyer").first():
        buyer_user = User(
            username="test_buyer",
            email="buyer@example.com",
            password_hash=generate_password_hash("BuyerPassword123!", method="pbkdf2:sha256"),
            role=UserRole.BUYER,
            company_name="Eco Conscious Inc.",
            is_active=True
        )
        db.session.add(buyer_user)
        print("Example buyer user created.")
    
    db.session.commit()

    # 4. Example Carbon Credit (from the seller created above)
    seller = User.query.filter_by(username="test_seller").first()
    if seller and not CarbonCredit.query.filter_by(title="Amazon Rainforest Conservation Units").first():
        credit1 = CarbonCredit(
            seller_id=seller.id,
            title="Amazon Rainforest Conservation Units",
            description="Verified carbon credits from a REDD+ project aimed at conserving a significant portion of the Amazon rainforest. Supports biodiversity and local communities.",
            quantity=10000.0,
            price_per_unit=12.50,
            source_project_type="Forestry (REDD+)",
            source_project_location="Brazil, Amazon Basin",
            status=CreditStatus.PENDING_APPROVAL
        )
        db.session.add(credit1)
        print("Example carbon credit 1 created.")

    if seller and not CarbonCredit.query.filter_by(title="Wind Farm Energy Credits - India").first():
        credit2 = CarbonCredit(
            seller_id=seller.id,
            title="Wind Farm Energy Credits - India",
            description="Carbon credits generated from a large-scale wind farm in Rajasthan, India, displacing fossil fuel energy generation.",
            quantity=50000.0,
            price_per_unit=18.75,
            source_project_type="Renewable Energy (Wind)",
            source_project_location="Rajasthan, India",
            status=CreditStatus.PENDING_APPROVAL
        )
        db.session.add(credit2)
        print("Example carbon credit 2 created.")

    db.session.commit()
    print("Database seeding complete.")

if __name__ == "__main__":
    app = create_app_for_db_init()
    initialize_database(app)
    print("CarbonConnect Database Initialization Script Finished.")

