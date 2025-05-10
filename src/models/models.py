import os
import enum # Import the standard Python enum module
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy. This will be configured in main.py
db = SQLAlchemy()

# Corrected Enum definitions: Inherit from Python's enum.Enum
class UserRole(enum.Enum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"

class CreditStatus(enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SOLD = "sold"
    EXPIRED = "expired"
    DELISTED = "delisted"

class OrderStatus(enum.Enum):
    PENDING_SELLER_ACTION = "pending_seller_action"
    CONFIRMED_BY_SELLER = "confirmed_by_seller"
    REJECTED_BY_SELLER = "rejected_by_seller"
    COMPLETED = "completed" # After seller confirmation, order is considered completed for PDF generation
    CANCELLED_BY_BUYER = "cancelled_by_buyer"

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # Store hashed passwords
    # Use the Python Enum with SQLAlchemy's Enum type
    role = db.Column(db.Enum(UserRole, name="user_role_enum"), nullable=False, default=UserRole.BUYER)
    company_name = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    credits_listed = db.relationship("CarbonCredit", backref="seller", lazy=True, foreign_keys="CarbonCredit.seller_id")
    orders_placed = db.relationship("Order", backref="buyer", lazy=True, foreign_keys="Order.buyer_id")
    orders_received = db.relationship("Order", backref="seller_user", lazy=True, foreign_keys="Order.seller_id") # Differentiate from credit.seller

    def __repr__(self):
        return f"<User {self.username} ({self.role.value if isinstance(self.role, enum.Enum) else self.role})>"

class CarbonCredit(db.Model):
    __tablename__ = "carbon_credits"
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Total available quantity
    price_per_unit = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default="ton CO2e", nullable=False)
    source_project_type = db.Column(db.String(100), nullable=True)
    source_project_location = db.Column(db.String(100), nullable=True)
    image_filename = db.Column(db.String(256), nullable=True) # Path to uploaded image for the credit
    validity_start_date = db.Column(db.DateTime, nullable=True)
    validity_end_date = db.Column(db.DateTime, nullable=True)
    verification_details_filename = db.Column(db.String(256), nullable=True) # Path to verification document
    status = db.Column(db.Enum(CreditStatus, name="credit_status_enum"), nullable=False, default=CreditStatus.PENDING_APPROVAL)
    admin_remarks = db.Column(db.Text, nullable=True)
    approved_or_rejected_at = db.Column(db.DateTime, nullable=True)
    admin_id_reviewer = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = db.relationship("Order", backref="carbon_credit", lazy=True)
    reviewer = db.relationship("User", foreign_keys=[admin_id_reviewer])

    def __repr__(self):
        return f"<CarbonCredit {self.title} ({self.status.value if isinstance(self.status, enum.Enum) else self.status})>"

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    credit_id = db.Column(db.Integer, db.ForeignKey("carbon_credits.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False) # The seller of the credit at time of order
    quantity_ordered = db.Column(db.Float, nullable=False)
    price_per_unit_at_order = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus, name="order_status_enum"), nullable=False, default=OrderStatus.PENDING_SELLER_ACTION)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    seller_action_date = db.Column(db.DateTime, nullable=True)
    completion_date = db.Column(db.DateTime, nullable=True)
    buyer_remarks = db.Column(db.Text, nullable=True)
    seller_remarks = db.Column(db.Text, nullable=True)
    pdf_certificate_filename = db.Column(db.String(256), nullable=True) # Filename of the generated PDF
    signed_pdf_certificate_filename = db.Column(db.String(256), nullable=True) # Filename of the signed PDF
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Order {self.id} by Buyer {self.buyer_id} for Credit {self.credit_id} ({self.status.value if isinstance(self.status, enum.Enum) else self.status})>"

class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"
    id = db.Column(db.Integer, primary_key=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    saved_filename = db.Column(db.String(256), unique=True, nullable=False) # UUID based filename on disk
    file_type = db.Column(db.String(50), nullable=True) # e.g., 'credit_image', 'verification_doc', 'order_pdf'
    related_entity_id = db.Column(db.Integer, nullable=True) # e.g., credit_id or order_id
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", backref="uploaded_files", lazy=True)

    def __repr__(self):
        return f"<UploadedFile {self.original_filename} by User {self.uploader_id}>"

