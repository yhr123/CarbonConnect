import os
import sys
import uuid
import datetime # Added for strptime
from flask import Blueprint, render_template, session, redirect, url_for, flash, request, current_app
from werkzeug.utils import secure_filename
from functools import wraps

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from src.models.models import db, User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus, UploadedFile
from src.services.pdf_service import generate_certificate_pdf
from src.services.signing_service import sign_pdf_document

seller_bp = Blueprint("seller", __name__, template_folder="../templates/seller", url_prefix="/seller")

# --- Decorators for Access Control ---
def seller_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("role") != UserRole.SELLER.value:
            flash("You must be logged in as a seller to access this page.", "danger")
            return redirect(url_for("auth.login"))
        user = User.query.get(session["user_id"])
        if not user or not user.is_active:
            flash("Your account is inactive. Please contact support.", "danger")
            session.clear()
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]

# --- Seller Routes ---
@seller_bp.route("/dashboard")
@seller_required
def dashboard():
    seller_id = session["user_id"]
    listed_credits = CarbonCredit.query.filter_by(seller_id=seller_id).order_by(CarbonCredit.submitted_at.desc()).all()
    received_orders = Order.query.filter_by(seller_id=seller_id).order_by(Order.order_date.desc()).all()
    
    stats = {
        "total_listed": len(listed_credits),
        "pending_approval": sum(1 for lc in listed_credits if lc.status == CreditStatus.PENDING_APPROVAL),
        "approved_active": sum(1 for lc in listed_credits if lc.status == CreditStatus.APPROVED),
        "sold": sum(1 for lc in listed_credits if lc.status == CreditStatus.SOLD),
        "total_orders": len(received_orders),
        "pending_action_orders": sum(1 for ro in received_orders if ro.status == OrderStatus.PENDING_SELLER_ACTION),
        "confirmed_orders": sum(1 for ro in received_orders if ro.status == OrderStatus.CONFIRMED_BY_SELLER or ro.status == OrderStatus.COMPLETED)
    }

    return render_template("seller_dashboard.html", 
                           title="Seller Dashboard", 
                           listed_credits=listed_credits, 
                           received_orders=received_orders,
                           stats=stats)

@seller_bp.route("/credits/list", methods=["GET", "POST"])
@seller_required
def list_credit():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        quantity = request.form.get("quantity", type=float)
        price_per_unit = request.form.get("price_per_unit", type=float)
        unit = request.form.get("unit", "ton CO2e")
        source_project_type = request.form.get("source_project_type")
        source_project_location = request.form.get("source_project_location")
        validity_start_date_str = request.form.get("validity_start_date")
        validity_end_date_str = request.form.get("validity_end_date")
        
        image_file = request.files.get("image_filename")
        verification_file = request.files.get("verification_details_filename")

        if not all([title, description, quantity, price_per_unit]):
            flash("Title, description, quantity, and price are required.", "danger")
            return redirect(url_for("seller.list_credit"))

        if quantity <= 0 or price_per_unit <= 0:
            flash("Quantity and price must be positive values.", "danger")
            return redirect(url_for("seller.list_credit"))

        image_filename_saved = None
        if image_file and image_file.filename != "" and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            ext = filename.rsplit(".", 1)[1].lower()
            image_filename_saved = f"credit_img_{uuid.uuid4().hex}.{ext}"
            image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "credits", image_filename_saved)
            os.makedirs(os.path.dirname(image_path), exist_ok=True) # Ensure directory exists
            image_file.save(image_path)
        elif image_file and image_file.filename != "":
            flash("Invalid image file type.", "danger")
            return redirect(url_for("seller.list_credit"))

        verification_filename_saved = None
        if verification_file and verification_file.filename != "" and allowed_file(verification_file.filename):
            filename = secure_filename(verification_file.filename)
            ext = filename.rsplit(".", 1)[1].lower()
            verification_filename_saved = f"credit_verif_{uuid.uuid4().hex}.{ext}"
            verification_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "verifications", verification_filename_saved)
            os.makedirs(os.path.dirname(verification_path), exist_ok=True) # Ensure directory exists
            verification_file.save(verification_path)
        elif verification_file and verification_file.filename != "":
            flash("Invalid verification document file type.", "danger")
            return redirect(url_for("seller.list_credit"))

        parsed_start_date = None
        if validity_start_date_str:
            try:
                parsed_start_date = datetime.datetime.strptime(validity_start_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid start date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("seller.list_credit"))

        parsed_end_date = None
        if validity_end_date_str:
            try:
                parsed_end_date = datetime.datetime.strptime(validity_end_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid end date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("seller.list_credit"))

        new_credit = CarbonCredit(
            seller_id=session["user_id"],
            title=title,
            description=description,
            quantity=quantity,
            price_per_unit=price_per_unit,
            unit=unit,
            source_project_type=source_project_type,
            source_project_location=source_project_location,
            image_filename=image_filename_saved,
            validity_start_date=parsed_start_date,
            validity_end_date=parsed_end_date,
            verification_details_filename=verification_filename_saved,
            status=CreditStatus.PENDING_APPROVAL
        )
        
        try:
            db.session.add(new_credit)
            db.session.commit()
            flash("New carbon credit listed successfully! It is now pending admin approval.", "success")
            return redirect(url_for("seller.dashboard"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error listing credit: {str(e)}")
            flash(f"Error listing credit: {str(e)}", "danger")
            # Clean up uploaded files if saving to DB failed
            if image_filename_saved and os.path.exists(os.path.join(current_app.config["UPLOAD_FOLDER"], "credits", image_filename_saved)):
                os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], "credits", image_filename_saved))
            if verification_filename_saved and os.path.exists(os.path.join(current_app.config["UPLOAD_FOLDER"], "verifications", verification_filename_saved)):
                os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], "verifications", verification_filename_saved))
            return redirect(url_for("seller.list_credit"))

    return render_template("list_credit.html", title="List New Carbon Credit")

@seller_bp.route("/orders/<int:order_id>/confirm", methods=["POST"])
@seller_required
def confirm_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != session["user_id"]:
        flash("You do not have permission to modify this order.", "danger")
        return redirect(url_for("seller.dashboard"))
    
    if order.status == OrderStatus.PENDING_SELLER_ACTION:
        credit = CarbonCredit.query.get(order.credit_id)
        if credit and credit.status == CreditStatus.APPROVED and credit.quantity >= order.quantity_ordered:
            generated_pdf_filename = None
            signed_pdf_filename = None
            try:
                generated_pdf_filename = generate_certificate_pdf(order.id)
                if not generated_pdf_filename:
                    flash("Failed to generate PDF certificate for the order.", "danger")
                    return redirect(url_for("seller.dashboard"))
                
                order.pdf_certificate_filename = generated_pdf_filename
                current_app.logger.info(f"Generated PDF {generated_pdf_filename} for order {order.id}")

                signed_pdf_filename = sign_pdf_document(generated_pdf_filename)
                if not signed_pdf_filename:
                    flash("Failed to sign the PDF certificate.", "danger")
                    return redirect(url_for("seller.dashboard"))
                
                order.signed_pdf_certificate_filename = signed_pdf_filename
                current_app.logger.info(f"Signed PDF {signed_pdf_filename} for order {order.id}")

                credit.quantity -= order.quantity_ordered
                if credit.quantity == 0:
                    credit.status = CreditStatus.SOLD
                
                order.status = OrderStatus.COMPLETED
                order.seller_action_date = datetime.datetime.utcnow() # Use Python datetime
                order.completion_date = datetime.datetime.utcnow() # Use Python datetime
                
                db.session.commit()
                flash(f"Order #{order.id} has been confirmed and certificate generated & signed.", "success")
            
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error during order confirmation for order {order.id}: {str(e)}")
                flash(f"An unexpected error occurred while confirming the order: {str(e)}", "danger")
                if generated_pdf_filename and os.path.exists(os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates", generated_pdf_filename)):
                    if not signed_pdf_filename:
                        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates", generated_pdf_filename))
                if signed_pdf_filename and os.path.exists(os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates", "signed", signed_pdf_filename)):
                     os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates", "signed", signed_pdf_filename))
                order.pdf_certificate_filename = None
                order.signed_pdf_certificate_filename = None

        elif credit and credit.quantity < order.quantity_ordered:
            flash(f"Not enough quantity available for credit \"{credit.title}\". Order cannot be confirmed.", "warning")
        elif not credit or credit.status != CreditStatus.APPROVED:
            flash(f"The credit associated with this order is no longer available or approved.", "warning")
        else:
            flash("Could not confirm order due to an issue with the credit.", "danger")
    else:
        flash("This order is not pending your action or has already been processed.", "warning")
    return redirect(url_for("seller.dashboard"))

@seller_bp.route("/orders/<int:order_id>/reject", methods=["POST"])
@seller_required
def reject_order(order_id):
    order = Order.query.get_or_404(order_id)
    seller_remarks = request.form.get("seller_remarks", "Rejected by seller.")
    if order.seller_id != session["user_id"]:
        flash("You do not have permission to modify this order.", "danger")
        return redirect(url_for("seller.dashboard"))

    if order.status == OrderStatus.PENDING_SELLER_ACTION:
        order.status = OrderStatus.REJECTED_BY_SELLER
        order.seller_action_date = datetime.datetime.utcnow() # Use Python datetime
        order.seller_remarks = seller_remarks
        db.session.commit()
        flash(f"Order #{order.id} has been rejected.", "success")
    else:
        flash("This order is not pending your action or has already been processed.", "warning")
    return redirect(url_for("seller.dashboard"))

# TODO: Add routes for editing credits (if status allows), viewing specific order details for seller

