# CarbonConnect: Technical Introduction and Architectural Overview

## 1. Introduction

CarbonConnect is a web-based platform designed to facilitate the transparent and efficient trading of carbon credits. It connects sellers of carbon credits with potential buyers, providing a marketplace, order management system, and a mechanism for generating digitally signed certificates of transaction. This document provides a technical overview of the project's design philosophy, system architecture, technology stack, and key implementation details, intended for developers and technical stakeholders.

## 2. Design Philosophy

The core design principles guiding the development of CarbonConnect include:

*   **Modularity**: The application is structured into distinct components (authentication, user roles, credit management, order processing, PDF services) to promote maintainability and ease of development.
*   **User-Centricity**: Clear workflows are defined for each user role (Buyer, Seller, Admin) to ensure an intuitive user experience.
*   **Data Integrity**: Emphasis is placed on accurate tracking of carbon credits, orders, and user information, with status transitions managed systematically.
*   **Security**: Basic security practices, such as password hashing and controlled access to functionalities based on user roles, are implemented. Digital signatures on certificates provide transaction authenticity.
*   **Deployability**: The application is containerized using Docker for consistent deployment across different environments.
*   **Simplicity (Initial Phase)**: For the initial version, SQLite is used as the database to simplify setup and deployment, with the understanding that it can be migrated to a more robust database system as the platform scales.

## 3. System Architecture

CarbonConnect follows a monolithic web application architecture using the Flask framework. The key components are:

### 3.1. Frontend

*   The frontend is primarily server-rendered using Flask and Jinja2 templates.
*   Bootstrap 5 is used for styling and responsive design, providing a clean and modern user interface.
*   Static assets (CSS, and any future JavaScript) are served by Flask.

### 3.2. Backend (Flask Application)

*   **Application Core (`src/main.py`)**: Initializes the Flask application, configures extensions (SQLAlchemy), registers blueprints, defines global context processors, and handles basic routes (homepage, policy pages, marketplace, credit details, file serving).
*   **Routing (`src/routes/`)**: Blueprints are used to organize routes by functionality:
    *   `auth.py`: Handles user registration, login, and logout.
    *   `admin.py`: Manages administrative functions like user management, credit approval, and viewing all orders.
    *   `seller.py`: Manages seller-specific functions like listing new carbon credits and managing received orders (confirm/reject).
    *   `buyer.py`: Manages buyer-specific functions like viewing their dashboard, placing purchase intents (which create orders), and downloading certificates.
*   **Database Models (`src/models/models.py`)**: Defines the data structures using SQLAlchemy ORM:
    *   `User`: Stores user information, including roles (Admin, Seller, Buyer).
    *   `CarbonCredit`: Represents carbon credits listed by sellers, including details, quantity, price, and status (Pending, Approved, Rejected, Sold).
    *   `Order`: Tracks purchase transactions, linking buyers, sellers, and credits, along with order status and generated certificate details.
    *   `UploadedFile`: (Initially conceptualized, but file paths are directly stored in `CarbonCredit` and `Order` models for simplicity in the current version).
    *   Enum types (`UserRole`, `CreditStatus`, `OrderStatus`) are used for managing predefined states.
*   **Services (`src/services/`)**:
    *   `pdf_service.py`: Responsible for generating PDF certificates using WeasyPrint from an HTML template (`src/templates/certificates/pdf_template.html`).
    *   `signing_service.py`: Handles the digital signing of generated PDF certificates using OpenSSL command-line tools. It uses a platform-specific private key and certificate stored in `src/certs/`.
*   **Database Initialization (`scripts/init_db.py`)**: A Flask CLI command (`flask init-db`) that creates all database tables based on the SQLAlchemy models and seeds initial data (e.g., default admin, seller, and buyer users).

### 3.3. Database (SQLite)

*   **SQLite** is used as the database engine for its simplicity and file-based nature, making it easy to set up and manage for development and small-scale deployments.
*   The database file (`carbon_connect.db`) is stored in `src/database/` and is persisted via Docker volume mapping.
*   **SQLAlchemy** acts as the Object-Relational Mapper (ORM), allowing interaction with the database using Python objects and abstracting direct SQL queries.

### 3.4. File Management

*   **Uploaded Files**: User-uploaded files (images for credits, verification documents) and system-generated PDF certificates are stored in the `uploads/` directory on the host, which is mapped into the Docker container.
    *   `uploads/credits/`: For carbon credit images.
    *   `uploads/verifications/`: For verification documents.
    *   `uploads/certificates/`: For unsigned generated PDF certificates.
    *   `uploads/certificates/signed/`: For digitally signed PDF certificates (as `.p7m` files).
*   **Serving Files**: Flask serves these files via a dedicated route (`/uploads/<subfolder>/<filename>`).
*   **Signing Certificates**: Platform-specific X.509 certificate and private key for signing PDFs are stored in `src/certs/`.

### 3.5. Key Processes and Workflows

*   **User Registration & Authentication**: Standard email/password registration with role selection. Session-based authentication.
*   **Carbon Credit Lifecycle**: Seller lists credit -> Admin reviews -> Admin Approves/Rejects. Approved credits are visible in the marketplace.
*   **Order Lifecycle**: Buyer expresses purchase intent -> Order created (Pending Seller Action) -> Seller Confirms/Rejects. If confirmed, quantity is updated, PDF is generated and signed, order becomes Completed. If rejected, status reflects rejection.
*   **PDF Generation & Signing**: Upon seller confirmation of an order, a PDF certificate is generated from an HTML template populated with order details. This PDF is then digitally signed using OpenSSL and the platform's credentials. The buyer can then download the signed certificate.

## 4. Technology Stack & Key Libraries

*   **Backend**: Python 3.11, Flask (web framework)
*   **Database**: SQLite
*   **ORM**: SQLAlchemy
*   **Templating**: Jinja2 (integrated with Flask)
*   **PDF Generation**: WeasyPrint (converts HTML/CSS to PDF)
*   **Digital Signatures**: OpenSSL (command-line tool, invoked via `subprocess`)
*   **Frontend Styling**: Bootstrap 5
*   **WSGI Server (Development)**: Werkzeug (Flask's default development server)
*   **Containerization**: Docker, Docker Compose
*   **Password Hashing**: Werkzeug Security (`generate_password_hash`, `check_password_hash` with `pbkdf2:sha256`)

## 5. Security Considerations (Brief Overview)

*   **Password Hashing**: User passwords are hashed using `pbkdf2:sha256`.
*   **Input Validation**: Basic input validation is performed in forms and routes (e.g., required fields, data types).
*   **Role-Based Access Control (RBAC)**: Decorators (`@admin_required`, `@seller_required`, `@buyer_required`) are used to protect routes and ensure only authorized users can access specific functionalities.
*   **File Uploads**: `secure_filename` from Werkzeug is used to sanitize filenames. File extensions are checked against an allowed list.
*   **Digital Signatures**: Provide authenticity and integrity for transaction certificates.
*   **Secret Key Management**: Flask's `SECRET_KEY` is configurable via an environment variable or a `.env` file for production.

## 6. Scalability and Future Enhancements

*   **Database Migration**: For larger-scale deployments, migrating from SQLite to a more robust database system like PostgreSQL or MySQL would be a primary consideration.
*   **Background Tasks**: PDF generation and signing, especially if they become time-consuming, could be offloaded to background workers (e.g., using Celery with Redis/RabbitMQ) to improve API responsiveness.
*   **API Development**: Exposing a RESTful API could allow third-party integrations or the development of a separate frontend application (e.g., a SPA using React/Vue/Angular).
*   **Enhanced Security**: Implementing more comprehensive security measures, including full CSRF protection across all state-changing requests, rate limiting, and more detailed input sanitization. (e.g., Flask-WTF (if forms were used extensively) would provide CSRF protection).
*   **Advanced Search/Filtering**: Improving marketplace search capabilities.
*   **Testing**: Implementing a comprehensive suite of unit and integration tests.
*   **Logging and Monitoring**: Enhancing logging and integrating monitoring tools for production environments.

## 7. Singleton Classes and Coupling Analysis

This section analyzes the CarbonConnect codebase for the presence of Singleton patterns and various types of coupling, as requested.

### 7.1. Singleton Pattern

A Singleton pattern ensures that a class has only one instance and provides a global point of access to it. In the context of the CarbonConnect Flask application, explicit user-defined Singleton classes are not prevalent. However, several components behave like or are managed as singletons by the Flask framework and its extensions:

*   **Flask Application Object (`app`)**: The core `Flask` application instance, created in `src/main.py` via `create_app()`, acts as a central registry and is effectively a singleton within the application context. While you get it by calling `create_app()`, during the lifecycle of a request, `current_app` proxy points to this single instance.

    ```python
    # src/main.py
    def create_app():
        app = Flask(__name__, template_folder="templates", static_folder="static")
        # ... configurations ...
        db.init_app(app) # Initialize SQLAlchemy with the app
        # ... blueprint registration ...
        return app

    # In other parts of the app, especially within request contexts or when app context is pushed:
    # from flask import current_app
    # current_app.logger.info("Accessing the app instance")
    ```

*   **Flask-SQLAlchemy `db` Object**: The `db = SQLAlchemy()` instance, typically defined in `src/models/models.py` (or initialized in `main.py` and then imported), is a singleton that manages database connections and sessions for the application. It's initialized once and then imported and used throughout the application to define models and interact with the database.

    ```python
    # src/models/models.py
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy() # This object acts as a singleton for database operations

    class User(db.Model):
        # ... model definition ...
    ```
    When `db.init_app(app)` is called, this `db` object is configured for the specific app instance.

*   **Configuration Object (`current_app.config`)**: Flask's configuration is loaded into a dictionary-like object that is unique per application instance and accessed globally via `current_app.config`.

 The framework's design and the use of application contexts and proxies provide singleton-like access to core services.

### 7.2. Coupling Analysis

Coupling refers to the degree of interdependence between software modules. Lower coupling is generally desirable as it leads to more maintainable, testable, and reusable code.

#### 7.2.1. Content Coupling

Content coupling occurs when one module directly modifies or relies on the internal workings (e.g., local data) of another module. This is the tightest form of coupling and is generally avoided in well-structured object-oriented or modular programming.

There is no Content Coupling in the `CarbonConnect` project.

#### 7.2.2. Common Coupling

Common coupling occurs when two or more modules share access to the same global data. Changes to this global data can affect all modules that use it, making debugging and reasoning about the system harder.

*   **Flask `session` Object**: The Flask `session` object is a form of common coupling. Multiple routes and modules (e.g., `auth.py`, various route protection decorators, and templates via context processors) read from and write to the `session` to manage user authentication state (`user_id`, `username`, `role`).

    ```python
    # src/routes/auth.py - Writing to session
    @auth_bp.route("/login", methods=["GET", "POST"])
    def login():
        # ...
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role.value
            # ...

    # src/routes/seller.py - Reading from session (in decorator)
    def seller_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session or session.get("role") != UserRole.SELLER.value:
                # ... redirect ...
            return f(*args, **kwargs)
        return decorated_function
    ```
    While necessary for web applications, extensive reliance on the session for passing non-authentication-related data between unrelated parts of the application could increase common coupling.

*   **Flask `current_app.config`**: The application configuration is globally accessible. While mostly read-only after startup, if modules were to modify it at runtime (not typical), it would be a strong form of common coupling.

*   **Database Object (`db`)**: The `db` object from Flask-SQLAlchemy is globally imported and used by various modules (`models.py`, all route files for queries). This provides a common point of access to the database. While it is a shared resource, interactions are generally through well-defined ORM methods, which mitigates some risks of raw global data access. However, the state of the database itself is a shared global state.

#### 7.2.3. Control Coupling

Control coupling occurs when one module passes a control flag or command to another, dictating its behavior. The calling module needs to know about the internal logic of the called module.

*   **Route Arguments and Query Parameters**: Some routes might exhibit a form of control coupling through query parameters that dictate behavior. For example, in `src/main.py`'s `marketplace` route:

    ```python
    # src/main.py
    @app.route("/marketplace")
    def marketplace():
        # ...
        sort_by = request.args.get("sort_by", "latest") # sort_by controls query ordering
        # ...
        if sort_by == "price_asc":
            query = query.order_by(CarbonCredit.price_per_unit.asc())
        elif sort_by == "price_desc":
            query = query.order_by(CarbonCredit.price_per_unit.desc())
        # ...
    ```
    Here, the `sort_by` parameter acts as a control flag influencing the database query logic.

*   **Role Parameter in Registration**: The `register` route in `src/routes/auth.py` accepts a `role` query parameter to pre-select the user role on the registration form. This parameter controls which role is initially selected in the template.

    ```python
    # src/routes/auth.py
    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        # ... (POST logic) ...
        selected_role = request.args.get("role", "buyer") # Control flag from URL
        return render_template("register.html", title="Register", selected_role=selected_role)
    ```

*   **Conditional Rendering in Templates based on `current_user.role`**: Many templates change their displayed elements or available actions based on `current_user.role`. While this is typical for UI, the Python code passing `current_user` (which contains the role) to the template is essentially passing control information that dictates template rendering logic.

#### 7.2.4. Stamp Coupling

Stamp coupling (or Data Structure coupling) occurs when a module passes a data structure (e.g., an object, a dictionary) to another module, but the called module only uses a portion of that data structure. This can lead to unnecessary dependencies on the whole structure.

*   **Passing Full Model Objects to Templates**: Many routes pass entire SQLAlchemy model objects (e.g., `User`, `CarbonCredit`, `Order`) to Jinja2 templates. The templates often only use a subset of the object's attributes.

    ```python
    # src/main.py
    @app.route("/credit/<int:credit_id>")
    def credit_detail(credit_id):
        credit = CarbonCredit.query.get_or_404(credit_id)
        # The entire 'credit' object is passed, template might only use a few fields
        return render_template("credit_detail.html", title=f"Credit Detail - {credit.title}", credit=credit)
    ```
    For example, `credit_detail.html` might display `credit.title`, `credit.description`, `credit.price_per_unit`, but not necessarily all fields like `credit.admin_remarks` or `credit.updated_at` if the user is not an admin.

* **Passing `request.form` or `request.args`**: While `request.form` and `request.args` are MultiDicts (similar to dictionaries), if a function receives the entire `request.form` but only processes one or two specific keys, it could be considered a mild form of stamp coupling. The current code mostly uses `request.form.get("specific_key")`, which is more targeted.

#### 7.2.5. Data Coupling

Data coupling occurs when modules share data only through parameters (e.g., passing simple data types or objects where all parts of the object are used). This is generally a good form of coupling.

*   **Many function calls**: Most function calls that pass specific IDs, strings, or numbers exhibit data coupling.
    
    ```python
    # src/services/pdf_service.py
    def generate_certificate_pdf(order_id):
        # 'order_id' is simple data passed as a parameter.
        order = Order.query.get(order_id)
        # ... uses order details ...
    ```
    
*   **Form data retrieval**: Retrieving specific fields from `request.form` like `username = request.form.get("username")` is an example of data coupling with the request object's form data.
