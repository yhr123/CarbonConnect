import pytest
import os
import tempfile

# Add project root to sys.path to allow imports from src
import sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from src.main import create_app
from src.models.models import db as _db # alias to avoid conflict with fixture
from src.models.models import User, UserRole

@pytest.fixture(scope='session')
def app():
    """Session-wide test Flask application."""
    # Use a temporary file for the SQLite database for testing
    db_fd, db_path = tempfile.mkstemp(suffix='.db', prefix='test_carbon_connect_')
    
    config_override = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler testing of forms if any
        "SECRET_KEY": "test_secret_key",
        "UPLOAD_FOLDER": tempfile.mkdtemp(prefix='test_uploads_') # Use temp dir for uploads
    }
    
    _app = create_app()
    _app.config.update(config_override)

    # Ensure upload subdirectories exist for testing services that might use them
    test_upload_folder = _app.config["UPLOAD_FOLDER"]
    subfolders = ["credits", "verifications", "certificates", "certificates/signed"]
    for subfolder in subfolders:
        os.makedirs(os.path.join(test_upload_folder, subfolder), exist_ok=True)

    # Also ensure certs dir exists for signing service (though it might be mocked)
    certs_dir = os.path.join(_app.root_path, "certs")
    if not os.path.exists(certs_dir):
        os.makedirs(certs_dir)
        # Create dummy cert files if signing_service is not fully mocked
        with open(os.path.join(certs_dir, "platform_certificate.pem"), "w") as f:
            f.write("-----BEGIN CERTIFICATE-----\nTestCertificate\n-----END CERTIFICATE-----")
        with open(os.path.join(certs_dir, "platform_private_key.pem"), "w") as f:
            f.write("-----BEGIN PRIVATE KEY-----\nTestPrivateKey\n-----END PRIVATE KEY-----")

    with _app.app_context():
        yield _app # provide the app object

    # Cleanup: close and remove the temporary database file
    os.close(db_fd)
    os.unlink(db_path)
    # Cleanup: remove temporary upload folder
    import shutil
    shutil.rmtree(test_upload_folder, ignore_errors=True)
    if os.path.exists(certs_dir) and "test_carbon_connect_" in certs_dir: # Basic safety check
        shutil.rmtree(certs_dir, ignore_errors=True)

@pytest.fixture(scope='function') # Changed to function scope for test isolation
def db(app):
    """Function-scoped database."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove() # Ensure session is closed
        _db.drop_all()       # Drop all tables after each test

@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    """A test runner for click commands."""
    return app.test_cli_runner()

# Example of a fixture to create a user, can be used in tests
@pytest.fixture(scope='function')
def new_user(db):
    def _new_user(username="testuser", email="test@example.com", password="password123", role=UserRole.BUYER, company_name=None, is_active=True):
        user = User(username=username, email=email, role=role, company_name=company_name, is_active=is_active)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return _new_user

@pytest.fixture(scope='function')
def new_admin_user(new_user):
    return new_user(username="adminuser", email="admin@example.com", role=UserRole.ADMIN)

@pytest.fixture(scope='function')
def new_seller_user(new_user):
    return new_user(username="selleruser", email="seller@example.com", role=UserRole.SELLER)

@pytest.fixture(scope='function')
def new_buyer_user(new_user):
    return new_user(username="buyeruser", email="buyer@example.com", role=UserRole.BUYER)

