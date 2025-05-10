import pytest
import datetime
from src.models.models import db, CarbonCredit, CreditStatus, UserRole

@pytest.fixture(scope='function')
def new_carbon_credit(db, new_seller_user):
    """Fixture to create a new carbon credit for testing."""
    def _new_carbon_credit(seller=None, **kwargs):
        if seller is None:
            seller = new_seller_user()
        
        default_data = {
            "seller_id": seller.id,
            "title": "Test Credit",
            "description": "A test carbon credit.",
            "quantity": 100.0,
            "price_per_unit": 10.50,
            "unit": "ton CO2e",
            "source_project_type": "Reforestation",
            "source_project_location": "Amazon Rainforest",
            "validity_start_date": datetime.date(2023, 1, 1),
            "validity_end_date": datetime.date(2024, 12, 31),
            "status": CreditStatus.PENDING_APPROVAL # Default status
        }
        default_data.update(kwargs)
        credit = CarbonCredit(**default_data)
        db.session.add(credit)
        db.session.commit()
        return credit
    return _new_carbon_credit

def test_new_carbon_credit_creation(new_carbon_credit):
    """Test creating a new CarbonCredit instance."""
    credit = new_carbon_credit(
        title="Solar Farm Credits",
        quantity=500.0,
        price_per_unit=12.75
    )
    assert credit.id is not None
    assert credit.title == "Solar Farm Credits"
    assert credit.quantity == 500.0
    assert credit.price_per_unit == 12.75
    assert credit.status == CreditStatus.PENDING_APPROVAL
    assert credit.seller_id is not None
    assert credit.seller is not None # Test relationship loading
    assert credit.seller.role == UserRole.SELLER

def test_carbon_credit_repr(new_carbon_credit):
    """Test the __repr__ method of the CarbonCredit model."""
    credit = new_carbon_credit(title="Unique Credit Title")
    assert repr(credit) == f"<CarbonCredit {credit.id} - Unique Credit Title (Pending Approval)>"

def test_carbon_credit_default_status(db, new_seller_user):
    """Test that the default status is PENDING_APPROVAL."""
    seller = new_seller_user()
    credit = CarbonCredit(
        seller_id=seller.id,
        title="Default Status Credit",
        description="Test default status",
        quantity=50.0,
        price_per_unit=5.0,
        unit="tCO2e"
    )
    db.session.add(credit)
    db.session.commit()
    retrieved_credit = CarbonCredit.query.get(credit.id)
    assert retrieved_credit.status == CreditStatus.PENDING_APPROVAL

def test_carbon_credit_image_url(new_carbon_credit, app):
    """Test the image_url property."""
    # Test with no image
    credit_no_image = new_carbon_credit(image_filename=None)
    assert credit_no_image.image_url is None

    # Test with an image
    image_name = "test_image.png"
    credit_with_image = new_carbon_credit(image_filename=image_name)
    expected_url = f"/uploads/credits/{image_name}"
    assert credit_with_image.image_url == expected_url

def test_carbon_credit_verification_url(new_carbon_credit, app):
    """Test the verification_details_url property."""
    # Test with no verification file
    credit_no_verif = new_carbon_credit(verification_details_filename=None)
    assert credit_no_verif.verification_details_url is None

    # Test with a verification file
    verif_name = "test_verification.pdf"
    credit_with_verif = new_carbon_credit(verification_details_filename=verif_name)
    expected_url = f"/uploads/verifications/{verif_name}"
    assert credit_with_verif.verification_details_url == expected_url

def test_carbon_credit_dates(new_carbon_credit):
    """Test validity start and end dates."""
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 12, 31)
    credit = new_carbon_credit(validity_start_date=start, validity_end_date=end)
    assert credit.validity_start_date == start
    assert credit.validity_end_date == end
