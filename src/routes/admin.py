import os
import sys
from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from src.models.models import db, User, UserRole, CarbonCredit, CreditStatus, Order

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin", url_prefix="/admin")

# --- Decorators for Access Control ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("role") != UserRole.ADMIN.value:
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Routes ---
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    pending_credits = CarbonCredit.query.filter_by(status=CreditStatus.PENDING_APPROVAL).count()
    approved_credits = CarbonCredit.query.filter_by(status=CreditStatus.APPROVED).count()
    total_users = User.query.count()
    total_orders = Order.query.count()
    return render_template("admin_dashboard.html", 
                           title="Admin Dashboard", 
                           pending_credits=pending_credits,
                           approved_credits=approved_credits,
                           total_users=total_users,
                           total_orders=total_orders)

@admin_bp.route("/users")
@admin_required
def manage_users():
    page = request.args.get("page", 1, type=int)
    users_pagination = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("manage_users.html", title="Manage Users", users_pagination=users_pagination)

@admin_bp.route("/user/<int:user_id>/toggle_active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == UserRole.ADMIN and User.query.filter_by(role=UserRole.ADMIN, is_active=True).count() == 1 and user.is_active:
        flash("Cannot deactivate the only active admin account.", "danger")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        # Corrected f-string syntax below
        status_text = 'active' if user.is_active else 'inactive'
        flash(f"User {user.username} status changed to {status_text}.", "success")
    return redirect(url_for("admin.manage_users"))

@admin_bp.route("/credits_approval")
@admin_required
def credits_for_approval():
    pending_credits = CarbonCredit.query.filter_by(status=CreditStatus.PENDING_APPROVAL).order_by(CarbonCredit.submitted_at.asc()).all()
    return render_template("credits_approval.html", title="Approve Carbon Credits", credits=pending_credits)

@admin_bp.route("/credit/<int:credit_id>/approve", methods=["POST"])
@admin_required
def approve_credit(credit_id):
    credit = CarbonCredit.query.get_or_404(credit_id)
    admin_remarks = request.form.get("admin_remarks", "Approved by admin.")
    if credit.status == CreditStatus.PENDING_APPROVAL:
        credit.status = CreditStatus.APPROVED
        credit.admin_id_reviewer = session["user_id"]
        credit.approved_or_rejected_at = db.func.now()
        credit.admin_remarks = admin_remarks
        db.session.commit()
        flash(f"Credit '{credit.title}' has been approved.", "success")
    else:
        flash("This credit is not pending approval.", "warning")
    return redirect(url_for("admin.credits_for_approval"))

@admin_bp.route("/credit/<int:credit_id>/reject", methods=["POST"])
@admin_required
def reject_credit(credit_id):
    credit = CarbonCredit.query.get_or_404(credit_id)
    admin_remarks = request.form.get("admin_remarks")
    if not admin_remarks:
        flash("Rejection remarks are required.", "danger")
        return redirect(url_for("admin.credits_for_approval"))

    if credit.status == CreditStatus.PENDING_APPROVAL:
        credit.status = CreditStatus.REJECTED
        credit.admin_id_reviewer = session["user_id"]
        credit.approved_or_rejected_at = db.func.now()
        credit.admin_remarks = admin_remarks
        db.session.commit()
        flash(f"Credit '{credit.title}' has been rejected.", "success")
    else:
        flash("This credit is not pending approval.", "warning")
    return redirect(url_for("admin.credits_for_approval"))

@admin_bp.route("/orders")
@admin_required
def view_all_orders():
    page = request.args.get("page", 1, type=int)
    orders_pagination = Order.query.order_by(Order.order_date.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("view_orders_admin.html", title="All Orders", orders_pagination=orders_pagination)


