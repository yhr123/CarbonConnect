import pytest
import datetime
from src.models.models import db, Order, OrderStatus, CarbonCredit, CreditStatus, UserRole

@pytest.fixture(scope='function')
def new_order(db, new_buyer_user, new_seller_user, new_carbon_credit):
    """Fixture to create a new order for testing."""
    def _new_order(buyer=None, seller=None, credit=None, **kwargs):
        if buyer is None:
            buyer = new_buyer_user()
        if seller is None:
            seller = new_seller_user() # Ensure seller is different from buyer if not specified
            if seller.id == buyer.id:
                 seller = new_seller_user(username="anotherseller", email="another_seller@example.com")

        if credit is None:
            # Ensure the credit belongs to the seller for consistency
            credit = new_carbon_credit(seller=seller, status=CreditStatus.APPROVED, quantity=200.0)
        
        default_data = {
            "buyer_id": buyer.id,
            "seller_id": seller.id,
            "credit_id": credit.id,
            "quantity_ordered": 10.0,
            "price_per_unit_at_order": credit.price_per_unit,
            "total_price": 10.0 * credit.price_per_unit,
            "status": OrderStatus.PENDING_SELLER_ACTION,
            "order_date": datetime.datetime.utcnow()
        }
        default_data.update(kwargs)
        order = Order(**default_data)
        db.session.add(order)
        db.session.commit()
        return order
    return _new_order

def test_new_order_creation(new_order, new_buyer_user, new_seller_user, new_carbon_credit):
    """Test creating a new Order instance."""
    buyer = new_buyer_user(username="orderbuyer", email="orderbuyer@example.com")
    seller = new_seller_user(username="orderseller", email="orderseller@example.com")
    credit = new_carbon_credit(seller=seller, title="Order Test Credit", quantity=100.0, price_per_unit=20.0, status=CreditStatus.APPROVED)
    
    order = new_order(
        buyer=buyer,
        seller=seller,
        credit=credit,
        quantity_ordered=5.0,
        price_per_unit_at_order=20.0,
        total_price=100.0
    )
    
    assert order.id is not None
    assert order.buyer_id == buyer.id
    assert order.seller_id == seller.id
    assert order.credit_id == credit.id
    assert order.quantity_ordered == 5.0
    assert order.price_per_unit_at_order == 20.0
    assert order.total_price == 100.0
    assert order.status == OrderStatus.PENDING_SELLER_ACTION
    assert order.order_date is not None
    assert order.buyer_user is not None
    assert order.seller_user is not None
    assert order.carbon_credit is not None

def test_order_repr(new_order):
    """Test the __repr__ method of the Order model."""
    order = new_order()
    assert repr(order) == f"<Order {order.id} - Buyer: {order.buyer_user.username} - Credit: {order.carbon_credit.title} - Status: {OrderStatus.PENDING_SELLER_ACTION.value}>"

def test_order_default_status(db, new_buyer_user, new_seller_user, new_carbon_credit):
    """Test that the default status is PENDING_SELLER_ACTION."""
    buyer = new_buyer_user()
    seller = new_seller_user(username="defaultseller", email="defaultseller@example.com")
    credit = new_carbon_credit(seller=seller, status=CreditStatus.APPROVED)

    order = Order(
        buyer_id=buyer.id,
        seller_id=seller.id,
        credit_id=credit.id,
        quantity_ordered=1.0,
        price_per_unit_at_order=credit.price_per_unit,
        total_price=credit.price_per_unit
    )
    db.session.add(order)
    db.session.commit()
    retrieved_order = Order.query.get(order.id)
    assert retrieved_order.status == OrderStatus.PENDING_SELLER_ACTION

def test_order_pdf_urls(new_order, app):
    """Test the pdf_certificate_url and signed_pdf_certificate_url properties."""
    # Test with no PDF filenames
    order_no_pdfs = new_order()
    assert order_no_pdfs.pdf_certificate_url is None
    assert order_no_pdfs.signed_pdf_certificate_url is None

    # Test with unsigned PDF
    unsigned_pdf_name = "unsigned_cert.pdf"
    order_with_unsigned = new_order(pdf_certificate_filename=unsigned_pdf_name)
    expected_unsigned_url = f"/uploads/certificates/{unsigned_pdf_name}"
    assert order_with_unsigned.pdf_certificate_url == expected_unsigned_url
    assert order_with_unsigned.signed_pdf_certificate_url is None # Signed should still be None

    # Test with signed PDF
    signed_pdf_name = "signed_cert.pdf.p7m"
    order_with_signed = new_order(pdf_certificate_filename="some_unsigned.pdf", signed_pdf_certificate_filename=signed_pdf_name)
    expected_signed_url = f"/uploads/certificates/signed/{signed_pdf_name}"
    assert order_with_signed.signed_pdf_certificate_url == expected_signed_url
