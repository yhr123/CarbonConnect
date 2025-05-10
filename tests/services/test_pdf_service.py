import pytest
import os
from unittest.mock import patch, MagicMock

from src.services.pdf_service import generate_certificate_pdf
from src.models.models import Order, User, CarbonCredit, OrderStatus, CreditStatus, UserRole, db

# Fixture for a sample order, buyer, seller, and credit
@pytest.fixture
def sample_order_for_pdf(db, new_buyer_user, new_seller_user, new_carbon_credit):
    buyer = new_buyer_user(username="pdfbuyer", email="pdfbuyer@example.com")
    seller = new_seller_user(username="pdfseller", email="pdfseller@example.com")
    credit = new_carbon_credit(seller=seller, title="PDF Test Credit", quantity=50.0, price_per_unit=10.0, status=CreditStatus.APPROVED)
    
    order = Order(
        buyer_id=buyer.id,
        seller_id=seller.id,
        credit_id=credit.id,
        quantity_ordered=5.0,
        price_per_unit_at_order=10.0,
        total_price=50.0,
        status=OrderStatus.CONFIRMED_BY_SELLER # A status where PDF might be generated
    )
    db.session.add(order)
    db.session.commit()
    return order

@patch("src.services.pdf_service.HTML") # Mock weasyprint.HTML
@patch("src.services.pdf_service.render_template") # Mock flask.render_template
def test_generate_certificate_pdf_success(mock_render_template, mock_weasyprint_html, app, db, sample_order_for_pdf):
    """Test successful PDF generation."""
    order = sample_order_for_pdf
    mock_render_template.return_value = "<html><body>Mocked PDF Content</body></html>"
    
    # Mock the HTML object and its write_pdf method
    mock_html_instance = MagicMock()
    mock_weasyprint_html.return_value = mock_html_instance
    mock_html_instance.write_pdf.return_value = b"dummy pdf bytes" # Simulate PDF bytes

    with app.app_context(): # Ensure app context for current_app.config and url_for
        # current_app.config["UPLOAD_FOLDER"] is set up in conftest.py app fixture
        # Ensure the certificates subdirectory exists within the temp UPLOAD_FOLDER
        certificates_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates")
        os.makedirs(certificates_path, exist_ok=True)

        pdf_filename = generate_certificate_pdf(order.id)

    assert pdf_filename is not None
    assert pdf_filename.startswith(f"CarbonConnect_Certificate_Order_{order.id}_")
    assert pdf_filename.endswith(".pdf")

    mock_render_template.assert_called_once_with(
        "certificates/pdf_template.html",
        order=order,
        buyer=order.buyer_user,
        seller=order.seller_user,
        credit=order.carbon_credit,
        generation_date=pytest.approx(order.order_date, abs=datetime.timedelta(seconds=10)) # Approximate check
    )
    mock_weasyprint_html.assert_called_once_with(string="<html><body>Mocked PDF Content</body></html>", base_url=app.config["SERVER_NAME"] or "/")
    
    # Check that write_pdf was called on the mock_html_instance
    # The actual path will be inside the temp UPLOAD_FOLDER
    # We don't need to check the exact path here, just that it was called.
    mock_html_instance.write_pdf.assert_called_once()
    
    # Verify the file was "created" (mocked creation)
    # In a real scenario with unmocked write_pdf, you would check os.path.exists
    # Here, we trust the mock and the returned filename.

@patch("src.services.pdf_service.render_template")
def test_generate_certificate_pdf_order_not_found(mock_render_template, app, db):
    """Test PDF generation when order is not found."""
    with app.app_context():
        pdf_filename = generate_certificate_pdf(99999) # Non-existent order ID
    assert pdf_filename is None
    mock_render_template.assert_not_called()

@patch("src.services.pdf_service.HTML")
@patch("src.services.pdf_service.render_template")
def test_generate_certificate_pdf_weasyprint_exception(mock_render_template, mock_weasyprint_html, app, db, sample_order_for_pdf):
    """Test PDF generation when WeasyPrint raises an exception."""
    order = sample_order_for_pdf
    mock_render_template.return_value = "<html></html>"
    mock_weasyprint_html.side_effect = Exception("WeasyPrint PDF generation failed")

    with app.app_context():
        certificates_path = os.path.join(app.config["UPLOAD_FOLDER"], "certificates")
        os.makedirs(certificates_path, exist_ok=True)
        pdf_filename = generate_certificate_pdf(order.id)
    
    assert pdf_filename is None
    mock_render_template.assert_called_once()
    mock_weasyprint_html.assert_called_once()

@patch("src.services.pdf_service.os.makedirs") # Mock os.makedirs to simulate failure
@patch("src.services.pdf_service.render_template")
def test_generate_certificate_pdf_makedirs_exception(mock_render_template, mock_makedirs, app, db, sample_order_for_pdf):
    """Test PDF generation when os.makedirs raises an exception."""
    order = sample_order_for_pdf
    mock_render_template.return_value = "<html></html>"
    mock_makedirs.side_effect = OSError("Failed to create directory")

    with app.app_context():
        # No need to actually create dirs as makedirs is mocked to fail
        pdf_filename = generate_certificate_pdf(order.id)

    assert pdf_filename is None
    # render_template might still be called before makedirs, depending on implementation order
    # In the current pdf_service, render_template is called before path creation for the file itself.
    mock_render_template.assert_called_once()
