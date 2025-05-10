import pytest
import os
from flask import url_for, session
from unittest.mock import patch

from src.models.models import User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus, db

# Helper function to log in a user
def login(client, username, password):
    return client.post(url_for("auth.login"), data={"username": username, "password": password}, follow_redirects=True)

@pytest.fixture
def logged_in_buyer(client, new_buyer_user):
    buyer = new_buyer_user(username="loginbuyertest", password="buyerpass")
    login(client, "loginbuyertest", "buyerpass")
    return buyer

@pytest.fixture
def approved_credit_for_buyer(db, new_seller_user):
    seller = new_seller_user(username="seller_for_buyer_credit", email="sfb_credit@example.com")
    credit = CarbonCredit(
        seller_id=seller.id, title="Marketplace Credit", description="Available for purchase",
        quantity=100, price_per_unit=15, unit="tCO2e", status=CreditStatus.APPROVED
    )
    db.session.add(credit)
    db.session.commit()
    return credit

@pytest.fixture
def buyer_order(db, logged_in_buyer, approved_credit_for_buyer):
    order = Order(
        buyer_id=logged_in_buyer.id, 
        seller_id=approved_credit_for_buyer.seller_id, 
        credit_id=approved_credit_for_buyer.id,
        quantity_ordered=5, 
        price_per_unit_at_order=approved_credit_for_buyer.price_per_unit,
        total_price=5 * approved_credit_for_buyer.price_per_unit, 
        status=OrderStatus.PENDING_SELLER_ACTION
    )
    db.session.add(order)
    db.session.commit()
    return order

@pytest.fixture
def completed_buyer_order_with_cert(db, logged_in_buyer, approved_credit_for_buyer, app):
    order = Order(
        buyer_id=logged_in_buyer.id, 
        seller_id=approved_credit_for_buyer.seller_id, 
        credit_id=approved_credit_for_buyer.id,
        quantity_ordered=2, 
        price_per_unit_at_order=approved_credit_for_buyer.price_per_unit,
        total_price=2 * approved_credit_for_buyer.price_per_unit, 
        status=OrderStatus.COMPLETED,
        pdf_certificate_filename="dummy_cert.pdf",
        signed_pdf_certificate_filename="dummy_cert.pdf.p7m"
    )
    db.session.add(order)
    db.session.commit()

    # Create dummy certificate files for download test
    # These paths are based on app.config["UPLOAD_FOLDER"] from conftest.py
    unsigned_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", order.pdf_certificate_filename)
    signed_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed", order.signed_pdf_certificate_filename)
    os.makedirs(os.path.dirname(unsigned_path), exist_ok=True)
    os.makedirs(os.path.dirname(signed_path), exist_ok=True)
    with open(unsigned_path, "wb") as f_unsigned:
        f_unsigned.write(b"dummy unsigned pdf data")
    with open(signed_path, "wb") as f_signed:
        f_signed.write(b"dummy signed p7m data")
        
    return order

# --- Access Control Tests ---
def test_buyer_dashboard_unauthenticated(client):
    response = client.get(url_for("buyer.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a buyer to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

def test_buyer_dashboard_as_seller(client, new_seller_user):
    login(client, new_seller_user(username="seller_access_buyer", password="pass").username, "pass")
    response = client.get(url_for("buyer.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a buyer to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

# --- Buyer Dashboard ---
def test_get_buyer_dashboard(client, logged_in_buyer, buyer_order):
    response = client.get(url_for("buyer.dashboard"))
    assert response.status_code == 200
    assert b"Buyer Dashboard" in response.data
    assert bytes(f"Order #{buyer_order.id}", "utf-8") in response.data
    assert bytes(buyer_order.carbon_credit.title, "utf-8") in response.data

# --- Purchase Intent (Create Order) ---
def test_create_order_success(client, logged_in_buyer, approved_credit_for_buyer):
    response = client.post(url_for("buyer.create_order", credit_id=approved_credit_for_buyer.id), data={
        "quantity": "3"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Order placed successfully!" in response.data
    assert b"Buyer Dashboard" in response.data # Redirects to buyer dashboard
    order = Order.query.filter_by(buyer_id=logged_in_buyer.id, credit_id=approved_credit_for_buyer.id).first()
    assert order is not None
    assert order.quantity_ordered == 3
    assert order.status == OrderStatus.PENDING_SELLER_ACTION

def test_create_order_insufficient_credit(client, logged_in_buyer, approved_credit_for_buyer):
    response = client.post(url_for("buyer.create_order", credit_id=approved_credit_for_buyer.id), data={
        "quantity": str(approved_credit_for_buyer.quantity + 1) # Order more than available
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Not enough quantity available for this credit." in response.data
    assert bytes(approved_credit_for_buyer.title, "utf-8") in response.data # Should be on credit detail page

def test_create_order_credit_not_approved(client, logged_in_buyer, new_seller_user, db):
    seller = new_seller_user(username="seller_not_approved_credit", email="snac@example.com")
    pending_credit = CarbonCredit(
        seller_id=seller.id, title="Pending Credit for Order", quantity=10, price_per_unit=5, status=CreditStatus.PENDING_APPROVAL
    )
    db.session.add(pending_credit)
    db.session.commit()
    response = client.post(url_for("buyer.create_order", credit_id=pending_credit.id), data={"quantity": "1"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"This credit is not currently available for purchase." in response.data
    assert b"Carbon Credit Marketplace" in response.data # Redirects to marketplace

# --- View Order ---
def test_view_order_page(client, logged_in_buyer, buyer_order):
    response = client.get(url_for("buyer.view_order", order_id=buyer_order.id))
    assert response.status_code == 200
    assert bytes(f"Order #{buyer_order.id} Details", "utf-8") in response.data
    assert bytes(buyer_order.carbon_credit.title, "utf-8") in response.data

def test_view_order_unauthorized(client, new_buyer_user, buyer_order):
    # buyer_order belongs to logged_in_buyer, try to access with another_buyer
    another_buyer = new_buyer_user(username="anotherbuyer", email="another@example.com", password="pass")
    login(client, "anotherbuyer", "pass")
    response = client.get(url_for("buyer.view_order", order_id=buyer_order.id), follow_redirects=True)
    assert response.status_code == 200
    assert b"You do not have permission to view this order." in response.data
    assert b"Buyer Dashboard" in response.data # Redirects to their own dashboard

# --- Cancel Order ---
def test_cancel_order_success(client, logged_in_buyer, buyer_order):
    assert buyer_order.status == OrderStatus.PENDING_SELLER_ACTION
    response = client.post(url_for("buyer.cancel_order", order_id=buyer_order.id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Order cancelled successfully." in response.data
    assert b"Buyer Dashboard" in response.data
    updated_order = Order.query.get(buyer_order.id)
    assert updated_order.status == OrderStatus.CANCELLED_BY_BUYER

def test_cancel_order_already_processed(client, logged_in_buyer, buyer_order, db):
    buyer_order.status = OrderStatus.COMPLETED # Simulate order already processed
    db.session.commit()
    response = client.post(url_for("buyer.cancel_order", order_id=buyer_order.id), follow_redirects=True)
    assert response.status_code == 200
    assert b"This order cannot be cancelled as it is already processed or not pending action." in response.data
    updated_order = Order.query.get(buyer_order.id)
    assert updated_order.status == OrderStatus.COMPLETED # Status should not change

# --- Download Certificate ---
# The actual download is handled by main.uploaded_file, here we test the link generation in view_order
def test_download_certificate_link_present(client, logged_in_buyer, completed_buyer_order_with_cert):
    response = client.get(url_for("buyer.view_order", order_id=completed_buyer_order_with_cert.id))
    assert response.status_code == 200
    assert bytes(f"Order #{completed_buyer_order_with_cert.id} Details", "utf-8") in response.data
    # Check for the download link for the signed certificate
    expected_link_href = url_for("uploaded_file", subfolder="certificates/signed", filename=completed_buyer_order_with_cert.signed_pdf_certificate_filename)
    assert bytes(f"href=\"{expected_link_href}\"", "utf-8") in response.data
    assert b"Download Signed Certificate (.p7m)" in response.data

    # Test actual file download (this tests the main.uploaded_file route indirectly via the link)
    # Ensure the dummy file exists (created by completed_buyer_order_with_cert fixture)
    download_response = client.get(expected_link_href)
    assert download_response.status_code == 200
    assert download_response.data == b"dummy signed p7m data"
    assert download_response.mimetype == "application/pkcs7-mime" # Check based on .p7m extension

