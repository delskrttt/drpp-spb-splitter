import base64
import os
import io
import zipfile
import streamlit as st
import fitz

from pdf_processor import (
    read_pdf_pages,
    detect_groups,
    split_pdf
)
from drive_uploader import upload_files_to_shared_drive


# =========================================================
# 1. KONFIGURASI STREAMLIT & CUSTOM CSS (GLASSMORPHISM UI)
# =========================================================

st.set_page_config(
    page_title="DRPP & SPB Automatic Splitter",
    page_icon="📑",
    layout="wide"
)


def apply_custom_ui(image_path="background.jpg"):
    encoded_string = ""
    if os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()

    bg_css = f'url("data:image/png;base64,{encoded_string}")' if encoded_string else "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)"

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Plus Jakarta Sans', sans-serif;
    }}

    .stApp {{
        background-image: {bg_css};
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    .stMainBlockContainer {{
        background: rgba(15, 23, 42, 0.82);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 20px;
        padding: 3rem 2.5rem;
        margin-top: 2rem;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
    }}

    h1 {{
        color: #F8FAFC !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
    }}

    h2, h3 {{
        color: #E2E8F0 !important;
        font-weight: 700 !important;
    }}

    div.stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.4) !important;
        transition: all 0.3s ease !important;
    }}

    div.stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(79, 70, 229, 0.6) !important;
        background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%) !important;
    }}

    div.stButton > button[kind="secondary"] {{
        background: rgba(255, 255, 255, 0.05) !important;
        color: #F1F5F9 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 12px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }}

    div.stButton > button[kind="secondary"]:hover {{
        background: rgba(255, 255, 255, 0.12) !important;
        border-color: #6366F1 !important;
        color: #FFFFFF !important;
        transform: translateY(-2px) !important;
    }}

    [data-testid="stMetric"] {{
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 1.2rem;
        border-radius: 14px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }}

    [data-testid="stMetricValue"] {{
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        color: #818CF8 !important;
    }}

    [data-testid="stMetricLabel"] {{
        color: #94A3B8 !important;
        font-weight: 600 !important;
    }}

    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {{
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        color: #F8FAFC !important;
    }}

    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within {{
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important;
    }}

    [data-testid="stFileUploader"] section {{
        background-color: rgba(255, 255, 255, 0.02) !important;
        border: 2px dashed rgba(99, 102, 241, 0.4) !important;
        border-radius: 14px !important;
        padding: 2rem !important;
        transition: all 0.3s ease !important;
    }}

    [data-testid="stFileUploader"] section:hover {{
        border-color: #818CF8 !important;
        background-color: rgba(99, 102, 241, 0.05) !important;
    }}

    hr {{
        border-color: rgba(255, 255, 255, 0.08) !important;
        margin: 2rem 0 !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


apply_custom_ui("background.jpg")

os.makedirs("uploads", exist_ok=True)
os.makedirs("hasil", exist_ok=True)


# =========================================================
# 2. DIALOG MODAL UPLOAD GOOGLE DRIVE
# =========================================================

@st.dialog("☁️ Upload Dokumen ke Google Drive")
def modal_upload_drive():
    st.write("Masukkan link folder Google Drive tempat dokumen akan disimpan:")

    drive_link = st.text_input(
        "Link Folder Google Drive",
        placeholder="https://drive.google.com/drive/folders/1VaUe-Hj0VX36l-tGJDVJnQGyidCWZQvK?usp=drive_link"
    )

    st.caption(
        "ℹ️ **Catatan**: Login Google akan otomatis terbuka di browser jika ini adalah kali pertama Anda mengunggah."
    )

    st.divider()

    if st.button("🚀 MULAI UPLOAD", type="primary", use_container_width=True):
        if not drive_link.strip():
            st.error("Silakan tempelkan link folder Google Drive terlebih dahulu.")
        else:
            try:
                with st.spinner("Sedang mengunggah seluruh file ke Google Drive..."):
                    uploaded_files = upload_files_to_shared_drive(
                        st.session_state["results"],
                        target_folder=drive_link
                    )

                st.session_state["uploaded_gdrive"] = uploaded_files
                st.success(f"Berhasil mengunggah {len(uploaded_files)} file ke Google Drive!")
                st.rerun()

            except Exception as error:
                st.error(f"Gagal mengunggah: {error}")


# =========================================================
# 3. HEADER APLIKASI
# =========================================================

st.title("📑 DRPP & SPB Automatic Splitter")

st.markdown(
    """
    Aplikasi otomatis untuk memisahkan dokumen pembayaran berdasarkan nomor **Surat Perintah Bayar (SPB)**.
    
    <div style="background: rgba(99, 102, 241, 0.08); border-left: 4px solid #6366F1; padding: 1rem 1.2rem; border-radius: 8px; margin-top: 1rem;">
        <span style="color: #E2E8F0; font-size: 0.95rem;">
            <strong>Output Otomatis:</strong><br>
            • <b>1 File DRPP</b> (Daftar Rincian Permintaan Pembayaran + Lampiran)<br>
            • <b>File SPB Mandiri</b> (Lengkap dengan kuitansi & bukti transfer untuk tiap nomor SPB)
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()


# =========================================================
# 4. FUNGSI UTILITAS (PARSER & ZIP)
# =========================================================

def parse_page_list(value, total_pages):
    if not value.strip():
        return []

    pages = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        if "-" in item:
            start, end = item.split("-", 1)
            start = int(start.strip())
            end = int(end.strip())

            if start > end:
                raise ValueError("Rentang halaman tidak valid.")

            pages.extend(range(start, end + 1))
        else:
            pages.append(int(item))

    pages = sorted(set(pages))

    for page in pages:
        if page < 1 or page > total_pages:
            raise ValueError(f"Halaman {page} berada di luar PDF.")

    return pages


def create_zip(results):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in results.items():
            zip_file.writestr(filename, content)

    buffer.seek(0)
    return buffer.getvalue()


# =========================================================
# 5. UPLOAD PDF (1 FILE)
# =========================================================

st.subheader("1. Upload Dokumen PDF")

uploaded_file = st.file_uploader(
    "Pilih file DRPP / SPB",
    type=["pdf"],
    accept_multiple_files=False
)

if uploaded_file:
    pdf_bytes = uploaded_file.getvalue()

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(document)
    document.close()

    col1, col2 = st.columns(2)
    col1.metric("Total Halaman PDF", total_pages)
    col2.metric("Ukuran File", f"{len(pdf_bytes) / (1024 * 1024):.2f} MB")

    st.success(f"✓ Dokumen berhasil dimuat: **{uploaded_file.name}**")

    st.divider()

    # =====================================================
    # 6. DETEKSI OTOMATIS
    # =====================================================

    st.subheader("2. Deteksi Dokumen")

    if st.button("🔍 MULAI DETEKSI SPB", type="primary", use_container_width=True):
        for key in [
            "pages", "groups", "information", "source_pdf",
            "results", "zip_result", "uploaded_gdrive"
        ]:
            st.session_state.pop(key, None)

        try:
            with st.spinner("Sedang membaca halaman PDF dan menjalankan OCR..."):
                pages = read_pdf_pages(pdf_bytes)
                groups, information = detect_groups(pages)

            st.session_state["pages"] = pages
            st.session_state["groups"] = groups
            st.session_state["information"] = information
            st.session_state["source_pdf"] = pdf_bytes

            st.success("Pembacaan dokumen berhasil diselesaikan.")

        except Exception as error:
            st.error(f"Gagal membaca PDF: {error}")

    # =====================================================
    # 7. MENAMPILKAN HASIL DETEKSI
    # =====================================================

    if "groups" in st.session_state:
        groups = st.session_state["groups"]
        information = st.session_state["information"]

        st.divider()
        st.subheader("3. Hasil Deteksi Dokumen")

        if information["error"]:
            st.error(information["error"])
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Jumlah SPB", len(groups))
            col2.metric("Cover DRPP", len(information["common_covers"]))
            col3.metric("Lampiran DRPP", len(information["common_attachments"]))

            st.markdown("#### Daftar SPB Terdeteksi")

            for group in groups:
                with st.container():
                    st.markdown(f"**📄 SPB {group['number']}**")
                    st.write(f"Halaman: **{group['start']}** s/d **{group['end']}**")
                    st.caption(f"Status: {group['end_reason']}")

                    if group["needs_review"]:
                        st.warning("⚠️ Bukti pembayaran tidak terdeteksi. Periksa halaman akhir secara manual.")
                    else:
                        st.success("✓ Bukti pembayaran terdeteksi.")

        # =================================================
        # 8. HALAMAN DRPP DAN LAMPIRAN
        # =================================================

        st.divider()
        st.subheader("4. Pemeriksaan Halaman DRPP")

        col_d1, col_d2 = st.columns(2)
        col_d1.info(f"**Halaman Utama DRPP:** {information['common_covers']}")
        col_d2.info(f"**Halaman Lampiran DRPP:** {information['common_attachments']}")

        # =================================================
        # 9. DIAGNOSTIK
        # =================================================

        st.divider()
        st.subheader("5. Diagnostik Semua Halaman")

        st.dataframe(
            information["diagnostics"],
            use_container_width=True,
            hide_index=True
        )

        # =================================================
        # 10. KOREKSI RENTANG
        # =================================================

        st.divider()
        st.subheader("6. Koreksi Rentang Halaman")

        st.warning(
            "Pastikan halaman akhir SPB mencakup seluruh kuitansi & bukti transfer."
        )

        default_ranges = "\n".join(
            [f"{g['number']}|{g['start']}|{g['end']}" for g in groups]
        )

        edited_ranges = st.text_area(
            "Format: Nomor SPB | Halaman Awal | Halaman Akhir",
            value=default_ranges,
            height=160
        )

        col_k1, col_k2 = st.columns(2)
        with col_k1:
            cover_default = ",".join(str(p) for p in information["common_covers"])
            cover_text = st.text_input("Halaman Utama DRPP", value=cover_default)

        with col_k2:
            attachment_default = ",".join(str(p) for p in information["common_attachments"])
            attachment_text = st.text_input("Halaman Lampiran DRPP", value=attachment_default)

        # =================================================
        # 11. PROSES PEMISAHAN
        # =================================================

        st.divider()
        st.subheader("7. Eksekusi Pemisahan PDF")

        if st.button("📂 PROSES PEMISAHAN PDF", type="primary", use_container_width=True):
            try:
                cover_pages = parse_page_list(cover_text, total_pages)
                attachment_pages = parse_page_list(attachment_text, total_pages)

                if not cover_pages:
                    raise ValueError("Halaman utama DRPP belum ditentukan.")

                if not attachment_pages:
                    raise ValueError("Halaman lampiran DRPP belum ditentukan.")

                if set(cover_pages) & set(attachment_pages):
                    raise ValueError("Halaman DRPP dan lampirannya tidak boleh sama.")

                lines = [
                    line.strip()
                    for line in edited_ranges.strip().splitlines()
                    if line.strip()
                ]

                if len(lines) != len(groups):
                    raise ValueError("Jumlah kelompok SPB tidak sesuai.")

                final_groups = []
                for index, line in enumerate(lines):
                    parts = [x.strip() for x in line.split("|")]
                    if len(parts) != 3:
                        raise ValueError("Format koreksi harus NOMOR|AWAL|AKHIR.")

                    number, start, end = parts
                    detected = groups[index]

                    start = int(start)
                    end = int(end)

                    if number != detected["number"]:
                        raise ValueError("Nomor SPB tidak boleh diubah.")

                    if start != detected["start"]:
                        raise ValueError(f"Halaman awal SPB {number} harus {detected['start']}.")

                    if end > detected["end"]:
                        raise ValueError(f"SPB {number} tidak boleh melewati halaman {detected['end']}.")

                    if end < start:
                        raise ValueError("Halaman akhir tidak valid.")

                    final_groups.append({
                        "number": number,
                        "start": start,
                        "end": end
                    })

                drpp_pages = set(cover_pages + attachment_pages)
                for group in final_groups:
                    spb_pages = set(range(group["start"], group["end"] + 1))
                    if drpp_pages & spb_pages:
                        raise ValueError(f"Ada halaman DRPP yang masuk ke rentang SPB {group['number']}.")

                with st.spinner("Sedang membuat file PDF..."):
                    drpp_num = st.session_state.get("information", {}).get("drpp_number")
                    results = split_pdf(
                        st.session_state["source_pdf"],
                        final_groups,
                        cover_pages,
                        attachment_pages,
                        drpp_number=drpp_num
                    )

                    for filename, content in results.items():
                        output_path = os.path.join("hasil", filename)
                        with open(output_path, "wb") as file:
                            file.write(content)

                    zip_result = create_zip(results)

                st.session_state["results"] = results
                st.session_state["zip_result"] = zip_result
                st.success(f"🎉 Berhasil membuat {len(results)} file PDF!")

            except Exception as error:
                st.error(f"Gagal memproses PDF: {error}")

        # =================================================
        # 12. HASIL DAN DOWNLOAD
        # =================================================

        if "results" in st.session_state:
            results = st.session_state["results"]

            st.divider()
            st.subheader("8. Hasil Pemisahan Dokumen")

            categories = {
                "Daftar Rincian Permintaan Pembayaran + Lampiran": [],
                "Surat Perintah Bayar": []
            }

            for filename, content in results.items():
                if filename.startswith("DRPP"):
                    categories["Daftar Rincian Permintaan Pembayaran + Lampiran"].append((filename, content))
                elif filename.startswith("SPB"):
                    categories["Surat Perintah Bayar"].append((filename, content))

            col1, col2, col3 = st.columns(3)
            col1.metric("Total File Hasil", len(results))
            col2.metric("DRPP + Lampiran", len(categories["Daftar Rincian Permintaan Pembayaran + Lampiran"]))
            col3.metric("File SPB", len(categories["Surat Perintah Bayar"]))

            st.divider()

            for category, files in categories.items():
                with st.expander(f"📁 {category} ({len(files)} file)", expanded=True):
                    for filename, content in files:
                        st.download_button(
                            label=f"📥 Download {filename}",
                            data=content,
                            file_name=filename,
                            mime="application/pdf",
                            key=f"download_{filename}",
                            use_container_width=True
                        )

            st.divider()
            st.subheader("Opsi Penyimpanan & Download Semua Dokumen")

            col_zip, col_drive = st.columns(2)

            with col_zip:
                st.download_button(
                    label="📦 DOWNLOAD SEMUA FILE (ZIP)",
                    data=st.session_state["zip_result"],
                    file_name="Hasil_Pemisahan_DRPP_SPB.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )

            with col_drive:
                if st.button("☁️ UPLOAD KE GOOGLE DRIVE", type="secondary", use_container_width=True):
                    modal_upload_drive()

            if "uploaded_gdrive" in st.session_state:
                with st.expander("🔗 Lihat Dokumen di Google Drive", expanded=True):
                    for file_info in st.session_state["uploaded_gdrive"]:
                        st.markdown(f"- 📄 [{file_info['name']}]({file_info['webViewLink']})")

else:
    st.info("Upload dokumen PDF untuk memulai proses pemisahan.")

# =========================================================
# 13. FOOTER
# =========================================================

st.divider()
st.caption("DRPP & SPB Automatic Splitter | Python + Streamlit + Tesseract OCR")