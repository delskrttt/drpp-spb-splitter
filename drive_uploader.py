import io
import os
import re
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def extract_folder_id(url_or_id):
    """Mengekstrak Folder ID dari URL Google Drive atau mengambil ID langsung."""
    if not url_or_id:
        return None
    
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
        
    return url_or_id.strip()


def _get_user_credentials():
    """Autentikasi menggunakan OAuth 2.0 milik akun Google pengguna."""
    creds = None
    token_path = os.path.join(BASE_DIR, "token.json")
    
    possible_secrets = [
        os.path.join(BASE_DIR, "client_secret.json"),
        os.path.join(BASE_DIR, "client_secret.json.json")
    ]
    
    client_secret_path = None
    for p in possible_secrets:
        if os.path.exists(p):
            client_secret_path = p
            break

    # 1. Cek jika token otorisasi sudah tersimpan sebelumnya
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # 2. Jika belum ada atau kadaluarsa, lakukan login OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret_path:
                raise RuntimeError(
                    "File client_secret.json tidak ditemukan di folder proyek. "
                    "Pastikan Anda telah mengunduh kredensial Desktop App dari Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Simpan token login agar tidak perlu login ulang di masa mendatang
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def upload_files_to_shared_drive(files, target_folder=None):
    folder_id = extract_folder_id(target_folder)
    if not folder_id:
        raise RuntimeError("Link atau ID folder Google Drive belum dimasukkan.")

    creds = _get_user_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    uploaded = []
    for filename, content in files.items():
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype="application/pdf",
            resumable=True
        )
        metadata = {
            "name": filename,
            "mimeType": "application/pdf",
            "parents": [folder_id]
        }
        created = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink"
        ).execute()

        uploaded.append({
            "id": created["id"],
            "name": created["name"],
            "webViewLink": created.get(
                "webViewLink",
                f"https://drive.google.com/file/d/{created['id']}/view"
            )
        })
    return uploaded