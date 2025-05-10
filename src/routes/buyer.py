import os
import sys
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from src.models.models import db, User, UserRole, CarbonCredit, CreditStatus, Order, OrderStatus

buyer_bp = Blueprint("buyer", __name__, template_folder="../templates/buyer", url_prefix="/buyer")

# --- Decorators for Access Control ---
def buyer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("role") != UserRole.BUYER.value:
            flash("You must be logged in as a buyer to access this page.", "danger")
            return redirect(url_for("auth.login"))
        user = User.query.get(session["user_id"])
        if not user or not user.is_active:
            flash("Your account is inactive. Please contact support.", "danger")
            session.clear()
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Buyer Routes ---
@buyer_bp.route("/dashboard")
@buyer_required
def dashboard():
    buyer_id = session["user_id"]
    orders_placed = Order.query.filter_by(buyer_id=buyer_id).order_by(Order.order_date.desc()).all()
    return render_template("buyer_dashboard.html", title="Buyer Dashboard", orders_placed=orders_placed)

@buyer_bp.route("/order/create/<int:credit_id>", methods=["POST"])
@buyer_required
def create_order(credit_id):
    credit = CarbonCredit.query.get_or_404(credit_id)
    if credit.status != CreditStatus.APPROVED:
        flash("This credit is not currently available for purchase.", "warning")
        return redirect(url_for("marketplace"))

    if credit.seller_id == session["user_id"]:
        flash("You cannot purchase your own listed credit.", "warning")
        return redirect(url_for("credit_detail", credit_id=credit.id))

    try:
        quantity_ordered = float(request.form.get("quantity"))
    except (ValueError, TypeError):
        flash("Invalid quantity specified.", "danger")
        return redirect(url_for("credit_detail", credit_id=credit.id))
        
    buyer_remarks = request.form.get("buyer_remarks", "")

    if quantity_ordered <= 0:
        flash("Quantity must be a positive value.", "danger")
        return redirect(url_for("credit_detail", credit_id=credit.id))

    if quantity_ordered > credit.quantity:
        flash(f"Requested quantity ({quantity_ordered}) exceeds available stock ({credit.quantity}).", "warning")
        return redirect(url_for("credit_detail", credit_id=credit.id))

    total_price = quantity_ordered * credit.price_per_unit

    new_order = Order(
        buyer_id=session["user_id"],
        credit_id=credit.id,
        seller_id=credit.seller_id, # Store the seller of the credit
        quantity_ordered=quantity_ordered,
        price_per_unit_at_order=credit.price_per_unit,
        total_price=total_price,
        status=OrderStatus.PENDING_SELLER_ACTION,
        buyer_remarks=buyer_remarks
    )

    try:
        db.session.add(new_order)
        db.session.commit()
        flash(f"Your purchase intent for {quantity_ordered} units of \"{credit.title}\" has been submitted. The seller will be notified.", "success")
        return redirect(url_for("buyer.dashboard"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error creating order: {str(e)}", "danger")
        return redirect(url_for("credit_detail", credit_id=credit.id))

@buyer_bp.route("/order/<int:order_id>")
@buyer_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != session["user_id"]:
        flash("You do not have permission to view this order.", "danger")
        return redirect(url_for("buyer.dashboard"))
    return render_template("view_order_buyer.html", title=f"Order #{order.id} Details", order=order)

# Cancelling an order if status allows
@buyer_bp.route("/order/<int:order_id>/cancel", methods=["POST"])
@buyer_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != session["user_id"]:
        flash("You do not have permission to modify this order.", "danger")
        return redirect(url_for("buyer.dashboard"))

    # Only allow cancellation if seller hasn't acted yet
    if order.status == OrderStatus.PENDING_SELLER_ACTION:
        order.status = OrderStatus.CANCELLED_BY_BUYER
        order.completion_date = db.func.now() # Use completion_date for cancellation time as well
        db.session.commit()
        flash(f"Order #{order.id} has been cancelled.", "success")
    else:
        flash("This order can no longer be cancelled as the seller has already processed it or it is completed.", "warning")
    return redirect(url_for("buyer.dashboard"))
