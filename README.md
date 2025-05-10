# CarbonConnect - Deployment and Usage Manual

## 1. Project Overview

CarbonConnect is a web application designed to facilitate the buying and selling of carbon credits. It provides a platform for sellers to list their carbon credits, for buyers to purchase these credits, and for administrators to manage users and approve credit listings. Upon successful completion of a transaction, a digitally signed PDF certificate is generated for the buyer.

The application is built using Flask (Python) for the backend, **SQLite for the database**, and HTML/CSS/Bootstrap for the frontend. It is designed to be deployed using Docker and Docker Compose.

## 2. Directory Structure

The project (`carbon_connect_flask_app`) has the following main structure:

```
carbon_connect_flask_app/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md (This manual)
├── scripts/
│   └── init_db.py       # Database initialization script
├── src/
│   ├── __init__.py
│   ├── main.py          # Main Flask application, entry point
│   ├── models/
│   │   └── models.py    # SQLAlchemy database models
│   ├── routes/
│   │   ├── admin.py     # Admin panel routes
│   │   ├── auth.py      # Authentication routes (login, register, logout)
│   │   ├── buyer.py     # Buyer dashboard and order routes
│   │   └── seller.py    # Seller dashboard, credit listing, and order management routes
│   ├── services/
│   │   ├── pdf_service.py # PDF generation logic
│   │   └── signing_service.py # PDF signing logic
│   ├── static/
│   │   └── css/
│   │       └── style.css  # Custom CSS styles
│   ├── templates/
│   │   ├── admin/         # Admin panel HTML templates
│   │   ├── auth/          # Authentication HTML templates
│   │   ├── base.html      # Base HTML template for all pages
│   │   ├── buyer/         # Buyer dashboard HTML templates
│   │   ├── certificates/  # PDF certificate HTML template
│   │   │   └── pdf_template.html
│   │   ├── credit_detail.html # Carbon credit detail page
│   │   ├── index.html     # Homepage
│   │   ├── marketplace.html # Carbon credit marketplace page
│   │   ├── privacy_policy.html # Carbon credit privacy policy page
│   │   ├── terms_of_service.html # Carbon credit terms of service page
│   │   └── seller/        # Seller dashboard HTML templates
│   ├── certs/             # SSL certificates for PDF signing
│   │   ├── platform_certificate.pem
│   │   └── platform_private_key.pem
│   └── database/          # SQLite database file will be stored here
│       └── carbon_connect.db (created after initialization)
└── uploads/                 # Directory for user-uploaded files and generated PDFs
    ├── credits/             # Uploaded credit images
    ├── verifications/       # Uploaded verification documents
    └── certificates/
        ├── signed/          # Signed PDF certificates (.p7m)
        └── (unsigned PDFs)  # Generated (unsigned) PDF certificates
```

## 3. Prerequisites

To run this application, you will need the following installed on your server:

*   **Docker Engine**: Latest stable version.
*   **Docker Compose**: Latest stable version.
*   **OpenSSL Command-Line Tool**: Required by the application for PDF signing. This is included in the Docker image.

## 4. Setup and Installation

1.  **Clone or Extract the Project**:
    Obtain the `carbon_connect_flask_app` directory and place it on your server.

2.  **Navigate to the Project Directory**:
    Open a terminal and change to the root of the project directory:
    ```bash
    cd path/to/carbon_connect_flask_app
    ```

3.  **Environment Variables (Optional)**:
    The application uses a default secret key for Flask sessions. For a production environment, it is highly recommended to set a strong, random `FLASK_SECRET_KEY`. This can be done by creating a `.env` file in the `carbon_connect_flask_app` root directory with the following content:
    ```env
    FLASK_SECRET_KEY=your_very_strong_random_secret_key_here
    FLASK_ENV=production # Optional: set to 'production' for production mode
    ```
    The `docker-compose.yml` file is set up to read this `.env` file if it exists. If `FLASK_ENV` is not set, it defaults to `development` as per `docker-compose.yml`.

4.  **Build and Start Docker Container**:
    Use Docker Compose to build the image and start the application service:
    ```bash
    docker-compose up --build -d
    ```
    *   `--build`: Forces Docker Compose to rebuild the image if the `Dockerfile` or context has changed.
    *   `-d`: Runs the container in detached mode (in the background).

    The Flask application will be accessible at `http://localhost:5000` (or your server's IP address on port 5000).

## 5. Database Initialization

After the Docker container is running, you need to initialize the SQLite database. This will create the necessary tables and seed initial data (e.g., an admin user). The SQLite database file (`carbon_connect.db`) will be created in the `src/database/` directory on your host machine, as this path is volume-mounted into the container.

1.  **Execute the `init-db` command inside the Flask app container**:
    ```bash
    docker-compose exec flask_app flask init-db
    ```
    You should see output indicating that the database initialization has completed. This will create or update the `carbon_connect.db` file in `carbon_connect_flask_app/src/database/`.

## 6. Application Usage

### 6.1. Accessing the Application

Open your web browser and navigate to `http://localhost:5000` (or your server's IP/domain on port 5000).

### 6.2. User Roles and Default Credentials

The `init_db.py` script creates the following default users:

*   **Admin**:
    *   Username: `admin`
    *   Password: `AdminPassword123!`
*   **Seller**:
    *   Username: `test_seller`
    *   Password: `SellerPassword123!`
*   **Buyer**:
    *   Username: `test_buyer`
    *   Password: `BuyerPassword123!`

It is strongly recommended to change these default passwords after your first login.

### 6.3. Key Workflows

*   **Registration**: New users can register by clicking the "Register" link in the navigation bar. They will need to provide a username, email, password, and select their role (Buyer or Seller). Company name is optional.
*   **Login/Logout**: Existing users can log in using their credentials. A "Logout" link is available after logging in.
*   **Marketplace**: The `/marketplace` page displays all approved carbon credits. Users can filter and sort these credits.
*   **Credit Detail**: Clicking on a credit in the marketplace shows its detailed information.

*   **Seller Workflow**:
    1.  **Login** as a Seller.
    2.  Navigate to the **Seller Dashboard** (link in the navbar).
    3.  Click "List New Carbon Credit".
    4.  Fill in the credit details, including title, description, quantity, price, project information, and optionally upload a promotional image and verification document.
    5.  Submit the credit. It will be in "Pending Approval" status.
    6.  From the dashboard, sellers can view their listed credits and their status.
    7.  When an order is placed for their credit, it appears in the "Orders Received" section.
    8.  Sellers can **Confirm** or **Reject** pending orders.
        *   If **Confirmed**: The system reduces the credit quantity. If all quantity is sold, the credit status changes to "SOLD". A PDF certificate is generated and digitally signed. The order status becomes "COMPLETED".
        *   If **Rejected**: The order status becomes "REJECTED BY SELLER".

*   **Buyer Workflow**:
    1.  **Login** as a Buyer.
    2.  Browse the **Marketplace** or view a specific **Credit Detail** page.
    3.  On the credit detail page, enter the desired quantity and click "Purchase Intent".
    4.  The order is submitted and will be in "Pending Seller Action" status.
    5.  Buyers can view their orders on their **Buyer Dashboard**.
    6.  If an order is **COMPLETED** (confirmed by the seller and PDF generated), a "Download Certificate" link will appear for the signed PDF (.p7m file).
    7.  Buyers can cancel an order if it's still "Pending Seller Action".

*   **Admin Workflow**:
    1.  **Login** as an Admin.
    2.  Navigate to the **Admin Dashboard**.
    3.  **Manage Users**: View all users, activate/deactivate user accounts.
    4.  **Approve Carbon Credits**: View credits pending approval. Admins can view details, **Approve**, or **Reject** them. Rejection requires remarks.
    5.  **View All Orders**: See a list of all orders in the system and their details.

## 7. File Management and Data Persistence

*   **Uploads Directory**: All user-uploaded files (credit images, verification documents) and system-generated files (PDF certificates) are stored in the `carbon_connect_flask_app/uploads/` directory on the host. This directory is volume-mounted into the Docker container at `/app/uploads/`, ensuring data persistence across container restarts.
    *   `uploads/credits/`: Stores images for carbon credit listings.
    *   `uploads/verifications/`: Stores verification documents for carbon credits.
    *   `uploads/certificates/`: Stores the generated (unsigned) PDF certificates.
    *   `uploads/certificates/signed/`: Stores the digitally signed PDF certificates (as .p7m files).
*   **Database Persistence**: The SQLite database file (`carbon_connect.db`) is stored in `carbon_connect_flask_app/src/database/` on the host. This directory is volume-mounted into the Docker container at `/app/src/database/`, ensuring the database persists across container restarts.
*   **Accessing Files**: Uploaded files are served by Flask through the `/uploads/<subfolder>/<filename>` route. For example, an image `uploads/credits/my_image.png` would be accessible at `http://localhost:5000/uploads/credits/my_image.png`.
*   **Signing Certificates**: The `platform_certificate.pem` and `platform_private_key.pem` files located in `src/certs/` are used for digitally signing the PDF certificates. Ensure these are kept secure.

## 8. Troubleshooting

*   **`docker-compose up` fails**: Check Docker and Docker Compose installation. Ensure no other service is using port 5000. Check `docker-compose logs flask_app` for errors.
*   **Database initialization error (`flask init-db`)**: Ensure Docker container is running (`docker-compose ps`). Check logs of the `flask_app` container (`docker-compose logs flask_app`) for specific Python errors. Verify the `src/database` directory on the host is writable by the user running the Docker container (typically the user who ran `docker-compose up`).
*   **File upload issues**: Check permissions of the `uploads/` directory on the host machine. Ensure it's writable. The `docker-compose.yml` mounts this directory, so host permissions are key.
*   **PDF generation/signing fails**: Check Flask application logs (`docker-compose logs flask_app`). Ensure `WeasyPrint` and `OpenSSL` are correctly installed in the Docker image (they are by default). Verify paths to signing certificates in `src/certs/`.

## 9. Stopping the Application

To stop the application and remove the container:

```bash
docker-compose down
```

To stop without removing the container (so it can be started again quickly):

```bash
docker-compose stop
```
