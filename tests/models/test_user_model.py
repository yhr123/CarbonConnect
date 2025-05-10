import pytest
from src.models.models import User, UserRole, db
from werkzeug.security import check_password_hash

def test_new_user_creation(new_user):
    """Test creating a new user with the fixture."""
    user = new_user(username="testuser1", email="test1@example.com", password="password123", role=UserRole.BUYER)
    assert user.id is not None
    assert user.username == "testuser1"
    assert user.email == "test1@example.com"
    assert user.role == UserRole.BUYER
    assert user.is_active is True
    assert check_password_hash(user.password_hash, "password123")

def test_user_repr(new_user):
    """Test the __repr__ method of the User model."""
    user = new_user(username="repruser", email="repr@example.com")
    assert repr(user) == f"<User repruser (repr@example.com) - Role: {UserRole.BUYER.value}>"

def test_user_password_hashing(new_user):
    """Test that the password is correctly hashed and can be verified."""
    user = new_user(password="secure_password")
    assert user.password_hash is not None
    assert user.password_hash != "secure_password"
    assert check_password_hash(user.password_hash, "secure_password")
    assert not check_password_hash(user.password_hash, "wrong_password")

def test_user_default_is_active(db):
    """Test that a new user is active by default."""
    user = User(username="activeuser", email="active@example.com", role=UserRole.SELLER)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    retrieved_user = User.query.filter_by(username="activeuser").first()
    assert retrieved_user.is_active is True

def test_user_company_name(new_user):
    """Test setting and retrieving company name."""
    user_with_company = new_user(company_name="Test Inc.")
    assert user_with_company.company_name == "Test Inc."
    user_without_company = new_user(username="no_company_user")
    assert user_without_company.company_name is None

def test_user_role_assignment(new_user):
    """Test different roles can be assigned."""
    admin = new_user(username="admintest", email="admin_test@example.com", role=UserRole.ADMIN)
    seller = new_user(username="sellertest", email="seller_test@example.com", role=UserRole.SELLER)
    buyer = new_user(username="buyertest", email="buyer_test@example.com", role=UserRole.BUYER)

    assert admin.role == UserRole.ADMIN
    assert seller.role == UserRole.SELLER
    assert buyer.role == UserRole.BUYER

def test_user_email_uniqueness(db, new_user):
    """Test that email addresses must be unique."""
    new_user(email="unique@example.com")
    with pytest.raises(Exception): # SQLAlchemy raises IntegrityError, caught as general Exception for simplicity
        duplicate_user = User(username="anotheruser", email="unique@example.com", role=UserRole.BUYER)
        duplicate_user.set_password("password")
        db.session.add(duplicate_user)
        db.session.commit()

def test_user_username_uniqueness(db, new_user):
    """Test that usernames must be unique."""
    new_user(username="unique_username")
    with pytest.raises(Exception):
        duplicate_user = User(username="unique_username", email="another@example.com", role=UserRole.BUYER)
        duplicate_user.set_password("password")
        db.session.add(duplicate_user)
        db.session.commit()

