import os
from flask import render_template, current_app
from weasyprint import HTML, CSS
from datetime import datetime
import uuid

from src.models.models import Order, User, CarbonCredit

def generate_certificate_pdf(order_id):
    """
    Generates a PDF certificate for a given order ID.
    Saves the PDF to the designated certificates upload folder.
    Returns the filename of the generated PDF or None if an error occurs.
    """
    order = Order.query.get(order_id)
    if not order:
        current_app.logger.error(f"Order with ID {order_id} not found for PDF generation.")
        return None

    buyer = User.query.get(order.buyer_id)
    seller = User.query.get(order.seller_id) # This is the seller_id stored in the order
    credit = CarbonCredit.query.get(order.credit_id)

    if not all([buyer, seller, credit]):
        current_app.logger.error(f"Missing buyer, seller, or credit for Order ID {order_id}.")
        return None

    generation_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Render HTML template with order data
    # Ensure the template path is correct relative to the templates folder
    html_string = render_template(
        "certificates/pdf_template.html", 
        order=order,
        buyer=buyer,
        seller=seller, # Pass the seller associated with the order
        credit=credit,
        generation_time=generation_time
    )

    # Define filename and path
    # Using a UUID to ensure unique filenames
    pdf_filename = f"CarbonConnect_Certificate_Order_{order.id}_{uuid.uuid4().hex[:8]}.pdf"
    certificates_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates")
    pdf_filepath = os.path.join(certificates_folder, pdf_filename)

    try:
        # WeasyPrint setup for fonts (if not globally configured via CSS @font-face with absolute file paths)
        # The @font-face in pdf_template.html uses file:/// which should work if paths are correct.
        # font_config = FontConfiguration()
        # css = CSS(string=\
        #     """@font-face {
        #            font-family: \'Noto Sans CJK SC\"; 
        #            src: url(\"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc\") format(\"truetype\");
        #        }
        #        body { font-family: \'Noto Sans CJK SC\"; }""", 
        #        font_config=font_config)
        
        # html = HTML(string=html_string, base_url=os.path.dirname(os.path.abspath(__file__)))
        # Using base_url=current_app.root_path might be more robust if static assets are referenced from template
        html = HTML(string=html_string, base_url=current_app.root_path)
        html.write_pdf(pdf_filepath) #, stylesheets=[css]) # Pass stylesheets if CSS is defined separately
        
        current_app.logger.info(f"Successfully generated PDF: {pdf_filepath} for Order ID {order.id}")
        return pdf_filename
    except Exception as e:
        current_app.logger.error(f"Error generating PDF for Order ID {order.id}: {str(e)}")
        # Attempt to remove partially created file if error occurs
        if os.path.exists(pdf_filepath):
            try:
                os.remove(pdf_filepath)
            except OSError as oe:
                current_app.logger.error(f"Error removing partial PDF {pdf_filepath}: {str(oe)}")
        return None

