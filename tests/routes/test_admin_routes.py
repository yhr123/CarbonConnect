import pytest
from flask import url_for, session
from src.models.models import User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus, db

# Helper function to log in a user
def login(client, username, password):
    return client.post(url_for("auth.login"), data={"username": username, "password": password}, follow_redirects=True)

# --- Access Control Tests ---
def test_admin_dashboard_unauthenticated(client):
    response = client.get(url_for("admin.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as an administrator to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

def test_admin_dashboard_as_buyer(client, new_buyer_user):
    user = new_buyer_user(username="testbuyer_for_admin_access", password="password")
    login(client, "testbuyer_for_admin_access", "password")
    response = client.get(url_for("admin.dashboard"), follow_redirects=True)
    assert response.status_code == 200 # Or 403 if not redirecting with flash
    assert b"You must be logged in as an administrator to access this page." in response.data
    # Depending on how auth_required redirects, it might go to index or login
    # For now, let's assume it flashes and might redirect to a non-admin page or show an error on current page if not redirected.
    # The current admin_required redirects to auth.login
    assert b"Login to CarbonConnect" in response.data

def test_admin_dashboard_as_seller(client, new_seller_user):
    user = new_seller_user(username="testseller_for_admin_access", password="password")
    login(client, "testseller_for_admin_access", "password")
    response = client.get(url_for("admin.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as an administrator to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data

def test_admin_dashboard_as_admin(client, new_admin_user):
    admin = new_admin_user(username="testadmin_login", password="adminpass")
    login(client, "testadmin_login", "adminpass")
    response = client.get(url_for("admin.dashboard"))
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data

# --- Manage Users Tests ---
def test_manage_users_page(client, new_admin_user, new_buyer_user):
    admin = new_admin_user(username="manageuseradmin", password="adminpass")
    login(client, "manageuseradmin", "adminpass")
    # Create a user to be managed
    managed_user = new_buyer_user(username="managed_user", email="managed@example.com")
    
    response = client.get(url_for("admin.manage_users"))
    assert response.status_code == 200
    assert b"Manage Users" in response.data
    assert bytes(managed_user.username, 'utf-8') in response.data

def test_toggle_user_activation(client, new_admin_user, new_buyer_user):
    admin = new_admin_user(username="toggleadmin", password="adminpass")
    login(client, "toggleadmin", "adminpass")
    user_to_toggle = new_buyer_user(username="toggle_user", email="toggle@example.com", is_active=True)
    
    # Deactivate user
    response = client.post(url_for("admin.toggle_user_activation", user_id=user_to_toggle.id), follow_redirects=True)
    assert response.status_code == 200
    assert b"Manage Users" in response.data # Back to manage users page
    toggled_user = User.query.get(user_to_toggle.id)
    assert toggled_user.is_active is False
    assert bytes(f"User {user_to_toggle.username} status changed to inactive.", "utf-8") in response.data

    # Activate user
    response = client.post(url_for("admin.toggle_user_activation", user_id=user_to_toggle.id), follow_redirects=True)
    assert response.status_code == 200
    toggled_user = User.query.get(user_to_toggle.id)
    assert toggled_user.is_active is True
    assert bytes(f"User {user_to_toggle.username} status changed to active.", "utf-8") in response.data

# --- Approve Carbon Credits Tests ---
@pytest.fixture
def pending_credit(db, new_seller_user):
    seller = new_seller_user(username="credit_seller", email="creditseller@example.com")
    credit = CarbonCredit(
        seller_id=seller.id, title="Pending Approval Credit", description="Test desc",
        quantity=100, price_per_unit=10, unit="tCO2e", status=CreditStatus.PENDING_APPROVAL
    )
    db.session.add(credit)
    db.session.commit()
    return credit

def test_credits_approval_page(client, new_admin_user, pending_credit):
    admin = new_admin_user(username="approvaladmin", password="adminpass")
    login(client, "approvaladmin", "adminpass")
    response = client.get(url_for("admin.approve_credits"))
    assert response.status_code == 200
    assert b"Approve Carbon Credits" in response.data
    assert bytes(pending_credit.title, "utf-8") in response.data

def test_approve_credit(client, new_admin_user, pending_credit):
    admin = new_admin_user(username="approve_action_admin", password="adminpass")
    login(client, "approve_action_admin", "adminpass")
    
    response = client.post(url_for("admin.decide_credit", credit_id=pending_credit.id, decision="approve"), follow_redirects=True)
    assert response.status_code == 200
    approved_credit = CarbonCredit.query.get(pending_credit.id)
    assert approved_credit.status == CreditStatus.APPROVED
    assert approved_credit.admin_id_reviewer == admin.id
    assert b"Credit approved successfully." in response.data

def test_reject_credit(client, new_admin_user, pending_credit):
    admin = new_admin_user(username="reject_action_admin", password="adminpass")
    login(client, "reject_action_admin", "adminpass")
    
    response = client.post(url_for("admin.decide_credit", credit_id=pending_credit.id, decision="reject"), data={
        "admin_remarks": "Insufficient documentation"
    }, follow_redirects=True)
    assert response.status_code == 200
    rejected_credit = CarbonCredit.query.get(pending_credit.id)
    assert rejected_credit.status == CreditStatus.REJECTED
    assert rejected_credit.admin_id_reviewer == admin.id
    assert rejected_credit.admin_remarks == "Insufficient documentation"
    assert b"Credit rejected successfully." in response.data

# --- View All Orders Test ---
@pytest.fixture
def sample_order_for_admin(db, new_buyer_user, new_seller_user, pending_credit): # Use pending_credit as it has a seller
    buyer = new_buyer_user(username="order_buyer_admin_view", email="obav@example.com")
    # Ensure credit is approved for an order to be placed typically, or use a different credit
    credit = CarbonCredit.query.get(pending_credit.id)
    credit.status = CreditStatus.APPROVED # Manually approve for this test setup
    db.session.commit()

    order = Order(
        buyer_id=buyer.id, seller_id=credit.seller_id, credit_id=credit.id,
        quantity_ordered=10, price_per_unit_at_order=credit.price_per_unit, 
        total_price=10 * credit.price_per_unit, status=OrderStatus.PENDING_SELLER_ACTION
    )
    db.session.add(order)
    db.session.commit()
    return order

def test_view_all_orders_page(client, new_admin_user, sample_order_for_admin):
    admin = new_admin_user(username="viewordersadmin", password="adminpass")
    login(client, "viewordersadmin", "adminpass")
    response = client.get(url_for("admin.view_orders"))
    assert response.status_code == 200
    assert b"View All Orders" in response.data
    assert bytes(f"Order #{sample_order_for_admin.id}", "utf-8") in response.data
    assert bytes(sample_order_for_admin.buyer_user.username, "utf-8") in response.data

