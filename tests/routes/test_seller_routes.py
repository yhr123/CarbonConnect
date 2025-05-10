import pytest
import os
from flask import url_for, session
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

from src.models.models import User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus, db

# Helper function to log in a user (can be moved to a common test utility if used across more files)
def login(client, username, password):
    return client.post(url_for("auth.login"), data={"username": username, "password": password}, follow_redirects=True)

@pytest.fixture
def logged_in_seller(client, new_seller_user):
    seller = new_seller_user(username="loginsellertest", password="sellerpass")
    login(client, "loginsellertest", "sellerpass")
    return seller

@pytest.fixture
def seller_credit(db, logged_in_seller):
    credit = CarbonCredit(
        seller_id=logged_in_seller.id, title="Seller Test Credit", description="Desc",
        quantity=100, price_per_unit=10, unit="tCO2e", status=CreditStatus.APPROVED
    )
    db.session.add(credit)
    db.session.commit()
    return credit

@pytest.fixture
def seller_pending_credit(db, logged_in_seller):
    credit = CarbonCredit(
        seller_id=logged_in_seller.id, title="Seller Pending Credit", description="Pending Desc",
        quantity=50, price_per_unit=12, unit="tCO2e", status=CreditStatus.PENDING_APPROVAL
    )
    db.session.add(credit)
    db.session.commit()
    return credit

@pytest.fixture
def order_for_seller(db, new_buyer_user, logged_in_seller, seller_credit):
    buyer = new_buyer_user(username="orderbuyerforseller", email="obfs@example.com")
    order = Order(
        buyer_id=buyer.id, seller_id=logged_in_seller.id, credit_id=seller_credit.id,
        quantity_ordered=10, price_per_unit_at_order=seller_credit.price_per_unit,
        total_price=10 * seller_credit.price_per_unit, status=OrderStatus.PENDING_SELLER_ACTION
    )
    db.session.add(order)
    db.session.commit()
    return order

# --- Access Control Tests ---
def test_seller_dashboard_unauthenticated(client):
    response = client.get(url_for("seller.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a seller to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

def test_seller_dashboard_as_buyer(client, new_buyer_user):
    login(client, new_buyer_user(username="buyer_access_seller", password="pass").username, "pass")
    response = client.get(url_for("seller.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a seller to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

def test_seller_dashboard_as_admin(client, new_admin_user):
    login(client, new_admin_user(username="admin_access_seller", password="pass").username, "pass")
    response = client.get(url_for("seller.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a seller to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

# --- Seller Dashboard ---
def test_get_seller_dashboard(client, logged_in_seller, seller_credit, seller_pending_credit, order_for_seller):
    response = client.get(url_for("seller.dashboard"))
    assert response.status_code == 200
    assert b"Seller Dashboard" in response.data
    assert bytes(seller_credit.title, "utf-8") in response.data
    assert bytes(seller_pending_credit.title, "utf-8") in response.data
    assert bytes(f"Order #{order_for_seller.id}", "utf-8") in response.data
    assert b"Total Listed Credits" in response.data

# --- List New Carbon Credit ---
def test_get_list_credit_page(client, logged_in_seller):
    response = client.get(url_for("seller.list_credit"))
    assert response.status_code == 200
    assert b"List New Carbon Credit" in response.data

def test_post_list_credit_success(client, logged_in_seller, app):
    data = {
        "title": "New Awesome Credit", "description": "Very good credit",
        "quantity": "150.5", "price_per_unit": "25.75", "unit": "kg CO2e",
        "source_project_type": "Solar", "source_project_location": "Nevada",
        "validity_start_date": "2024-01-01", "validity_end_date": "2025-01-01"
    }
    response = client.post(url_for("seller.list_credit"), data=data, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"New carbon credit listed successfully!" in response.data
    assert b"Seller Dashboard" in response.data # Redirects to dashboard
    credit = CarbonCredit.query.filter_by(title="New Awesome Credit").first()
    assert credit is not None
    assert credit.quantity == 150.5
    assert credit.price_per_unit == 25.75
    assert credit.status == CreditStatus.PENDING_APPROVAL

def test_post_list_credit_with_files(client, logged_in_seller, app):
    # Ensure UPLOAD_FOLDER subdirectories exist (handled by app fixture in conftest)
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], "credits")
    verif_path = os.path.join(app.config["UPLOAD_FOLDER"], "verifications")
    os.makedirs(image_path, exist_ok=True)
    os.makedirs(verif_path, exist_ok=True)

    data = {
        "title": "Credit With Files", "description": "Files attached",
        "quantity": "100", "price_per_unit": "10",
        "image_filename": (FileStorage(stream=b"dummy image data", filename="test_image.png", content_type="image/png")),
        "verification_details_filename": (FileStorage(stream=b"dummy pdf data", filename="test_verif.pdf", content_type="application/pdf")),
    }
    response = client.post(url_for("seller.list_credit"), data=data, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"New carbon credit listed successfully!" in response.data
    credit = CarbonCredit.query.filter_by(title="Credit With Files").first()
    assert credit is not None
    assert credit.image_filename is not None
    assert credit.image_filename.startswith("credit_img_")
    assert credit.image_filename.endswith(".png")
    assert credit.verification_details_filename is not None
    assert credit.verification_details_filename.startswith("credit_verif_")
    assert credit.verification_details_filename.endswith(".pdf")
    # Check if files were actually saved (optional, as this tests service logic too)
    assert os.path.exists(os.path.join(image_path, credit.image_filename))
    assert os.path.exists(os.path.join(verif_path, credit.verification_details_filename))

def test_post_list_credit_missing_fields(client, logged_in_seller):
    response = client.post(url_for("seller.list_credit"), data={"title": "Incomplete"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Title, description, quantity, and price are required." in response.data
    assert b"List New Carbon Credit" in response.data # Stays on form

# --- Confirm Order Tests ---
@patch("src.routes.seller.generate_certificate_pdf")
@patch("src.routes.seller.sign_pdf_document")
def test_confirm_order_success(mock_sign_pdf, mock_generate_pdf, client, logged_in_seller, order_for_seller, seller_credit):
    mock_generate_pdf.return_value = "generated_dummy.pdf"
    mock_sign_pdf.return_value = "signed_dummy.pdf.p7m"
    
    initial_credit_quantity = seller_credit.quantity
    response = client.post(url_for("seller.confirm_order", order_id=order_for_seller.id), follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Seller Dashboard" in response.data
    assert b"Order #" + bytes(str(order_for_seller.id), "utf-8") + b" has been confirmed" in response.data
    
    updated_order = Order.query.get(order_for_seller.id)
    assert updated_order.status == OrderStatus.COMPLETED
    assert updated_order.pdf_certificate_filename == "generated_dummy.pdf"
    assert updated_order.signed_pdf_certificate_filename == "signed_dummy.pdf.p7m"
    
    updated_credit = CarbonCredit.query.get(seller_credit.id)
    assert updated_credit.quantity == initial_credit_quantity - order_for_seller.quantity_ordered
    
    mock_generate_pdf.assert_called_once_with(order_for_seller.id)
    mock_sign_pdf.assert_called_once_with("generated_dummy.pdf")

def test_confirm_order_insufficient_quantity(client, logged_in_seller, order_for_seller, seller_credit):
    # Modify credit quantity to be less than order quantity
    seller_credit.quantity = order_for_seller.quantity_ordered - 1
    db.session.commit()

    response = client.post(url_for("seller.confirm_order", order_id=order_for_seller.id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Not enough quantity available" in response.data
    updated_order = Order.query.get(order_for_seller.id)
    assert updated_order.status == OrderStatus.PENDING_SELLER_ACTION # Status should not change

# --- Reject Order Tests ---
def test_reject_order_success(client, logged_in_seller, order_for_seller):
    remarks = "Item out of stock temporarily."
    response = client.post(url_for("seller.reject_order", order_id=order_for_seller.id), data={
        "seller_remarks": remarks
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Seller Dashboard" in response.data
    assert b"Order #" + bytes(str(order_for_seller.id), "utf-8") + b" has been rejected." in response.data
    
    updated_order = Order.query.get(order_for_seller.id)
    assert updated_order.status == OrderStatus.REJECTED_BY_SELLER
    assert updated_order.seller_remarks == remarks

