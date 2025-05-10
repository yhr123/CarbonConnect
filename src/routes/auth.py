import os
import sys
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Add project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from src.models.models import db, User, UserRole

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role_str = request.form.get("role", "buyer") # Default to buyer
        company_name = request.form.get("company_name")

        if not username or not email or not password or not confirm_password:
            flash("All fields except company name are required.", "danger")
            return redirect(url_for("auth.register", role=role_str))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register", role=role_str))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("auth.register", role=role_str))

        if User.query.filter_by(email=email).first():
            flash("Email address already registered.", "danger")
            return redirect(url_for("auth.register", role=role_str))
        
        try:
            role = UserRole[role_str.upper()]
        except KeyError:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("auth.register"))

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        
        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            role=role,
            company_name=company_name if company_name else None
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred during registration: {str(e)}", "danger")
            return redirect(url_for("auth.register", role=role_str))

    # Pass role to template for pre-selection
    selected_role = request.args.get("role", "buyer")
    return render_template("register.html", title="Register", selected_role=selected_role)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role.value # Store role value (string)
            flash("Login successful!", "success")
            
            next_url = request.args.get("next")
            if next_url:
                 return redirect(next_url)

            if user.role == UserRole.ADMIN:
                return redirect(url_for("admin.dashboard"))
            elif user.role == UserRole.SELLER:
                return redirect(url_for("seller.dashboard"))
            elif user.role == UserRole.BUYER:
                return redirect(url_for("buyer.dashboard")) # Redirect buyer to buyer dashboard
            else:
                return redirect(url_for("index")) # Fallback to homepage
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("auth.login"))

    return render_template("login.html", title="Login")

@auth_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login")) # Redirect to login page after logout

