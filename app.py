from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient, ContentSettings
from werkzeug.utils import secure_filename
import os
import datetime

# --- Configuration ---
CONTAINER_NAME = "lanternfly-images"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Get connection string from environment variable (or paste for local testing)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# --- Create Blob Service Client ---
bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
cc = bsc.get_container_client(CONTAINER_NAME)

# Make sure container exists and is public-read
if not cc.exists():
    cc.create_container(public_access="blob")

# --- Flask App ---
app = Flask(__name__)

# Utility: generate timestamped, safe filename
def make_blob_name(filename: str) -> str:
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe = secure_filename(filename)
    return f"{timestamp}-{safe}"

# Utility: check if uploaded file is an image
def is_image(file):
    return file.mimetype.startswith("image/")

# --- API Routes ---

# Upload endpoint
@app.post("/api/v1/upload")
def upload():
    try:
        # Get file from form
        f = request.files.get("file")
        if not f:
            return jsonify(ok=False, error="No file uploaded"), 400

        # Validate image type
        if not is_image(f):
            return jsonify(ok=False, error="Invalid file type"), 400

        # Check file size
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify(ok=False, error="File too large"), 400

        # Create blob name and upload
        blob_name = make_blob_name(f.filename)
        blob_client = cc.get_blob_client(blob_name)
        blob_client.upload_blob(
            f,
            overwrite=True,
            content_settings=ContentSettings(content_type=f.mimetype)
        )

        # Construct public URL
        url = f"{cc.url}/{blob_name}"
        print(f"[UPLOAD] {blob_name} uploaded successfully")
        return jsonify(ok=True, url=url)

    except Exception as e:
        print("[ERROR]", e)
        return jsonify(ok=False, error=str(e)), 500


# Gallery endpoint
@app.get("/api/v1/gallery")
def gallery():
    try:
        urls = [f"{cc.url}/{b.name}" for b in cc.list_blobs()]
        return jsonify(ok=True, gallery=urls)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


# Health endpoint
@app.get("/api/v1/health")
def health():
    return jsonify(ok=True, status="healthy"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

