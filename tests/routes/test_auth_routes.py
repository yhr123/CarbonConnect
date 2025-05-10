import pytest
from flask import session, url_for
from src.models.models import User, UserRole, db

# --- Registration Tests ---
def test_get_register_page(client):
    """Test GET request to the registration page."""
    response = client.get(url_for("auth.register"))
    assert response.status_code == 200
    assert b"Register an Account" in response.data
    assert b"Register as Buyer" in response.data # Check for role selection

def test_successful_buyer_registration(client):
    """Test successful registration of a new buyer."""
    response = client.post(url_for("auth.register"), data={
        "username": "newbuyer",
        "email": "newbuyer@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "BUYER"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful! Please log in." in response.data
    assert b"Login to CarbonConnect" in response.data # Should redirect to login page
    user = User.query.filter_by(username="newbuyer").first()
    assert user is not None
    assert user.email == "newbuyer@example.com"
    assert user.role == UserRole.BUYER

def test_successful_seller_registration(client):
    """Test successful registration of a new seller with company name."""
    response = client.post(url_for("auth.register"), data={
        "username": "newseller",
        "email": "newseller@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "SELLER",
        "company_name": "Seller Inc."
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Registration successful! Please log in." in response.data
    user = User.query.filter_by(username="newseller").first()
    assert user is not None
    assert user.role == UserRole.SELLER
    assert user.company_name == "Seller Inc."

@pytest.mark.parametrize("missing_field", ["username", "email", "password", "confirm_password"])
def test_registration_missing_fields(client, missing_field):
    """Test registration with missing required fields."""
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "BUYER"
    }
    del data[missing_field]
    response = client.post(url_for("auth.register"), data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"All fields except company name are required." in response.data
    assert b"Register an Account" in response.data # Stays on registration page

def test_registration_password_mismatch(client):
    """Test registration with mismatched passwords."""
    response = client.post(url_for("auth.register"), data={
        "username": "mismatchuser",
        "email": "mismatch@example.com",
        "password": "password123",
        "confirm_password": "password456",
        "role": "BUYER"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Passwords do not match." in response.data

def test_registration_duplicate_username(client, new_user):
    """Test registration with a username that already exists."""
    existing_user = new_user(username="existinguser", email="unique_email@example.com")
    response = client.post(url_for("auth.register"), data={
        "username": "existinguser",
        "email": "newemail@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "BUYER"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Username already exists." in response.data

def test_registration_duplicate_email(client, new_user):
    """Test registration with an email that already exists."""
    existing_user = new_user(username="unique_user", email="existingemail@example.com")
    response = client.post(url_for("auth.register"), data={
        "username": "newusername",
        "email": "existingemail@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "role": "BUYER"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Email address already registered." in response.data

# --- Login Tests ---
def test_get_login_page(client):
    """Test GET request to the login page."""
    response = client.get(url_for("auth.login"))
    assert response.status_code == 200
    assert b"Login to CarbonConnect" in response.data

def test_successful_login_buyer(client, new_buyer_user):
    """Test successful login for a buyer and redirection to buyer dashboard."""
    user = new_buyer_user(username="loginbuyer", password="buyerpass")
    response = client.post(url_for("auth.login"), data={
        "username": "loginbuyer",
        "password": "buyerpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Login successful!" in response.data
    assert b"Buyer Dashboard" in response.data # Check for buyer dashboard content
    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id
        assert sess["role"] == UserRole.BUYER.value

def test_successful_login_seller(client, new_seller_user):
    """Test successful login for a seller and redirection to seller dashboard."""
    user = new_seller_user(username="loginseller", password="sellerpass")
    response = client.post(url_for("auth.login"), data={
        "username": "loginseller",
        "password": "sellerpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Login successful!" in response.data
    assert b"Seller Dashboard" in response.data
    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id
        assert sess["role"] == UserRole.SELLER.value

def test_successful_login_admin(client, new_admin_user):
    """Test successful login for an admin and redirection to admin dashboard."""
    user = new_admin_user(username="loginadmin", password="adminpass")
    response = client.post(url_for("auth.login"), data={
        "username": "loginadmin",
        "password": "adminpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Login successful!" in response.data
    assert b"Admin Dashboard" in response.data
    with client.session_transaction() as sess:
        assert sess["user_id"] == user.id
        assert sess["role"] == UserRole.ADMIN.value

def test_login_invalid_username(client):
    """Test login with a non-existent username."""
    response = client.post(url_for("auth.login"), data={
        "username": "nonexistentuser",
        "password": "password123"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username or password." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess

def test_login_incorrect_password(client, new_user):
    """Test login with an incorrect password."""
    user = new_user(username="userwithpass", password="correctpass")
    response = client.post(url_for("auth.login"), data={
        "username": "userwithpass",
        "password": "wrongpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username or password." in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess

@pytest.mark.parametrize("missing_field", ["username", "password"])
def test_login_missing_fields(client, missing_field):
    """Test login with missing username or password."""
    data = {"username": "testuser", "password": "password123"}
    del data[missing_field]
    response = client.post(url_for("auth.login"), data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Username and password are required." in response.data

# --- Logout Tests ---
def test_logout(client, new_user):
    """Test successful logout."""
    # First, log in the user
    user = new_user(username="logoutuser", password="logoutpass")
    client.post(url_for("auth.login"), data={"username": "logoutuser", "password": "logoutpass"})
    
    with client.session_transaction() as sess:
        assert "user_id" in sess

    response = client.get(url_for("auth.logout"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out." in response.data
    assert b"Login to CarbonConnect" in response.data # Should redirect to login page
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "username" not in sess
        assert "role" not in sess

# --- Access Control Test (Example) ---
def test_access_protected_route_unauthenticated(client):
    """Test accessing a protected route (e.g., seller dashboard) when not logged in."""
    response = client.get(url_for("seller.dashboard"), follow_redirects=True)
    assert response.status_code == 200
    assert b"You must be logged in as a seller to access this page." in response.data
    assert b"Login to CarbonConnect" in response.data # Redirects to login

