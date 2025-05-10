import pytest
import os
import subprocess
from unittest.mock import patch, MagicMock

from src.services.signing_service import sign_pdf_document
from src.models.models import db # Required for app context, though not directly used here

# Dummy PDF filename for testing
DUMMY_UNSIGNED_PDF = "test_certificate_to_sign.pdf"

@pytest.fixture
def create_dummy_unsigned_pdf(app):
    """Creates a dummy unsigned PDF file in the test upload/certificates directory."""
    unsigned_pdf_folder = os.path.join(app.config["UPLOAD_FOLDER"], "certificates")
    # This folder should be created by the app fixture in conftest.py
    # os.makedirs(unsigned_pdf_folder, exist_ok=True)
    dummy_pdf_path = os.path.join(unsigned_pdf_folder, DUMMY_UNSIGNED_PDF)
    with open(dummy_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n%test content") # Minimal PDF content
    yield DUMMY_UNSIGNED_PDF # Return the filename
    # Cleanup: remove the dummy file
    if os.path.exists(dummy_pdf_path):
        os.remove(dummy_pdf_path)

@patch("src.services.signing_service.subprocess.Popen")
def test_sign_pdf_document_success(mock_subproc_popen, app, create_dummy_unsigned_pdf):
    """Test successful PDF signing."""
    unsigned_pdf_filename = create_dummy_unsigned_pdf
    
    # Mock Popen to simulate successful OpenSSL command
    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"stdout_output", b"stderr_output")
    mock_process.returncode = 0
    mock_subproc_popen.return_value = mock_process

    with app.app_context():
        # Ensure the signed certificates subdirectory exists
        signed_certs_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed")
        os.makedirs(signed_certs_path, exist_ok=True)
        
        signed_filename = sign_pdf_document(unsigned_pdf_filename)

    assert signed_filename is not None
    base_name, _ = os.path.splitext(unsigned_pdf_filename)
    assert signed_filename == f"{base_name}.pdf.p7m"

    mock_subproc_popen.assert_called_once()
    args, _ = mock_subproc_popen.call_args
    command_list = args[0]
    assert "openssl" in command_list
    assert "cms" in command_list
    assert "-sign" in command_list
    assert os.path.join(app.root_path, "certs", "platform_certificate.pem") in command_list
    assert os.path.join(app.root_path, "certs", "platform_private_key.pem") in command_list
    assert os.path.join(app.config["UPLOAD_FOLDER"], "certificates", unsigned_pdf_filename) in command_list
    assert os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed", signed_filename) in command_list

    # Check if the signed file was (mock) created - in a real test, we might check os.path.exists
    # but here we rely on the service returning the filename upon mocked success.


def test_sign_pdf_document_unsigned_pdf_not_found(app):
    """Test signing when the unsigned PDF does not exist."""
    with app.app_context():
        signed_filename = sign_pdf_document("non_existent_unsigned.pdf")
    assert signed_filename is None

@patch("src.services.signing_service.os.path.exists")
def test_sign_pdf_document_certs_not_found(mock_os_path_exists, app, create_dummy_unsigned_pdf):
    """Test signing when certificate or private key is missing."""
    unsigned_pdf_filename = create_dummy_unsigned_pdf
    
    # Simulate certs/keys not existing
    # os.path.exists will be called for unsigned_pdf_path, then certificate_path, then private_key_path
    # Let the first call (for unsigned_pdf_path) be True, subsequent ones (for certs) be False.
    mock_os_path_exists.side_effect = [True, False] # True for PDF, False for cert

    with app.app_context():
        signed_filename = sign_pdf_document(unsigned_pdf_filename)
    
    assert signed_filename is None
    # It should check existence of unsigned PDF, then cert, then key. If cert is false, it stops.
    assert mock_os_path_exists.call_count >= 2 

@patch("src.services.signing_service.subprocess.Popen")
def test_sign_pdf_document_openssl_failure(mock_subproc_popen, app, create_dummy_unsigned_pdf):
    """Test signing when OpenSSL command fails (returns non-zero exit code)."""
    unsigned_pdf_filename = create_dummy_unsigned_pdf

    mock_process = MagicMock()
    mock_process.communicate.return_value = (b"", b"OpenSSL error")
    mock_process.returncode = 1 # Simulate OpenSSL error
    mock_subproc_popen.return_value = mock_process

    with app.app_context():
        signed_certs_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed")
        os.makedirs(signed_certs_path, exist_ok=True)
        # Create a dummy file that would be created by openssl, to test its removal on failure
        base_name, _ = os.path.splitext(unsigned_pdf_filename)
        dummy_signed_path = os.path.join(signed_certs_path, f"{base_name}.pdf.p7m")
        with open(dummy_signed_path, "w") as f: f.write("dummy")

        signed_filename = sign_pdf_document(unsigned_pdf_filename)
    
    assert signed_filename is None
    mock_subproc_popen.assert_called_once()
    assert not os.path.exists(dummy_signed_path) # Check if dummy signed file was removed

@patch("src.services.signing_service.subprocess.Popen")
def test_sign_pdf_document_subprocess_exception(mock_subproc_popen, app, create_dummy_unsigned_pdf):
    """Test signing when subprocess.Popen raises an exception."""
    unsigned_pdf_filename = create_dummy_unsigned_pdf
    mock_subproc_popen.side_effect = OSError("Failed to start OpenSSL")

    with app.app_context():
        signed_certs_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates", "signed")
        os.makedirs(signed_certs_path, exist_ok=True)
        signed_filename = sign_pdf_document(unsigned_pdf_filename)
    
    assert signed_filename is None
    mock_subproc_popen.assert_called_once()

