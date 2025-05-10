import os
import subprocess
from flask import current_app
import uuid

def sign_pdf_document(pdf_filename):
    """
    Signs a given PDF document using OpenSSL command-line tools.
    Assumes platform_certificate.pem and platform_private_key.pem are in src/certs/.
    Saves the signed PDF (in .p7m format or as a PDF with embedded signature)
    to the designated signed certificates upload folder.
    Returns the filename of the signed PDF or None if an error occurs.
    """
    unsigned_pdf_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates")
    unsigned_pdf_path = os.path.join(unsigned_pdf_folder, pdf_filename)

    if not os.path.exists(unsigned_pdf_path):
        current_app.logger.error(f"Unsigned PDF {unsigned_pdf_path} not found for signing.")
        return None

    # Define paths for certificates and keys
    certs_dir = os.path.join(current_app.root_path, "certs") # current_app.root_path is /app in Docker, or project root/src in venv
    certificate_path = os.path.join(certs_dir, "platform_certificate.pem")
    private_key_path = os.path.join(certs_dir, "platform_private_key.pem")

    if not os.path.exists(certificate_path) or not os.path.exists(private_key_path):
        current_app.logger.error(f"Signing certificate or private key not found in {certs_dir}.")
        return None

    # Define filename and path for the signed PDF
    # OpenSSL CMS typically creates a .p7m file (detached signature) or can embed it.
    base_name, ext = os.path.splitext(pdf_filename)
    # signed_pdf_filename = f"{base_name}_signed.pdf" # If OpenSSL can output a signed PDF directly
    signed_p7m_filename = f"{base_name}.pdf.p7m" # Standard for detached CMS signatures
    
    signed_certificates_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "certificates", "signed")
    # signed_pdf_filepath = os.path.join(signed_certificates_folder, signed_pdf_filename)
    signed_p7m_filepath = os.path.join(signed_certificates_folder, signed_p7m_filename)

    try:
        # Command to sign the PDF using OpenSSL CMS
        # This creates a detached signature in .p7m format.
        # To embed, it's more complex and might require tools like `pdftk` or `PortableSigner`
        # For now, we'll use the detached signature method as it's standard with OpenSSL CLI.
        # openssl cms -sign -signer <certificate_path> -inkey <private_key_path> -in <unsigned_pdf_path> -outform DER -out <signed_p7m_filepath> -nodetach -binary
        # Using -nodetach -binary creates an S/MIME message with the content included.
        # For a simple signature that can be verified, -binary is important for PDF.
        # The output will be a PKCS#7 structure.
        
        # Using DER format for the output signature file.
        # The command `openssl smime -sign` is also an option for S/MIME signatures.
        # `openssl dgst -sha256 -sign private_key.pem -out signature.bin input.pdf` creates a raw signature.
        # `openssl cms -sign -signer cert.pem -inkey key.pem -in input.pdf -binary -outform DER -out signed.p7s` is more appropriate.

        cmd = [
            "openssl", "cms", "-sign",
            "-signer", certificate_path,
            "-inkey", private_key_path,
            "-in", unsigned_pdf_path,
            "-binary", # Important for binary files like PDF
            "-outform", "DER", # or PEM
            "-nodetach", # Embeds the original document in the PKCS#7 structure
            "-out", signed_p7m_filepath
        ]
        
        # For a detached signature (smaller .p7m file, original PDF needed separately):
        # cmd = [
        #     "openssl", "cms", "-sign",
        #     "-signer", certificate_path,
        #     "-inkey", private_key_path,
        #     "-in", unsigned_pdf_path,
        #     "-binary",
        #     "-outform", "DER",
        #     "-out", signed_p7m_filepath 
        #     # No -nodetach for detached
        # ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            current_app.logger.error(f"OpenSSL signing failed for {pdf_filename}. Error: {stderr.decode()}")
            if os.path.exists(signed_p7m_filepath):
                os.remove(signed_p7m_filepath)
            return None
        
        current_app.logger.info(f"Successfully signed PDF: {pdf_filename}, output: {signed_p7m_filepath}")
        return signed_p7m_filename # Return the .p7m filename

    except Exception as e:
        current_app.logger.error(f"Exception during PDF signing for {pdf_filename}: {str(e)}")
        if os.path.exists(signed_p7m_filepath):
            try:
                os.remove(signed_p7m_filepath)
            except OSError as oe:
                current_app.logger.error(f"Error removing partial signed file {signed_p7m_filepath}: {str(oe)}")
        return None

# TODO: Aim for a signed PDF instead of a .p7m file.