import os
import re
import io
import shutil

import fitz
import pytesseract

from PIL import Image, ImageOps, ImageEnhance
from pypdf import PdfReader, PdfWriter


# =========================================================
# 1. KONFIGURASI TESSERACT OCR (CROSS-PLATFORM)
# =========================================================

if os.name == 'nt':
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    # Untuk Linux / Streamlit Cloud / Docker
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "/usr/bin/tesseract"

OCR_LANGUAGE = "eng"


# =========================================================
# 2. NORMALISASI TEKS
# =========================================================

def normalize_text(text):
    text = text.upper()
    text = text.replace("P8/", "PB/")
    text = text.replace("P B /", "PB/")
    text = text.replace("P8 /", "PB/")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================================================
# 3. MEMBACA PDF DAN OCR
# =========================================================

def read_pdf_pages(pdf_bytes):
    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    pages_text = []

    for index, page in enumerate(document):
        text = page.get_text("text")

        # OCR jika PDF merupakan hasil scan
        if len(text.strip()) < 80:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(3, 3),
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            image = ImageOps.grayscale(image)
            image = ImageEnhance.Contrast(image).enhance(2)

            text = pytesseract.image_to_string(
                image,
                lang=OCR_LANGUAGE,
                config="--oem 3 --psm 6"
            )

            if len(text.strip()) < 30:
                text = pytesseract.image_to_string(
                    image,
                    lang=OCR_LANGUAGE,
                    config="--oem 3 --psm 11"
                )

        pages_text.append({
            "page": index + 1,
            "text": normalize_text(text)
        })

    document.close()
    return pages_text


# =========================================================
# 4. MENDETEKSI NOMOR SPB DAN DRPP
# =========================================================

def extract_spb_number(text):
    text = normalize_text(text)

    patterns = [
        r"(\d{3,6})\s*/\s*P\s*[B8]\s*/\s*(\d{5,8})\s*/\s*(20\d{2})",
        r"(\d{3,6})\s*P\s*[B8]\s*(\d{5,8})\s*(20\d{2})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            nomor = match.group(1)
            kode = match.group(2)
            tahun = match.group(3)
            return f"{nomor}/PB/{kode}/{tahun}"

    return None


def extract_drpp_number(text):
    text = normalize_text(text)

    patterns = [
        r"(\d{3,6})\s*/\s*DRPP\s*/\s*(\d{5,8})\s*/\s*(20\d{2})",
        r"(\d{3,6})\s*DRPP\s*(\d{5,8})\s*(20\d{2})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


# =========================================================
# 5. DETEKSI HALAMAN SPB, DRPP, KUITANSI & BUKTI
# =========================================================

def is_spb_page(text):
    text = normalize_text(text)

    if "LAMPIRAN SURAT PERINTAH BAYAR" in text:
        return False

    pattern = r"S[UO]RAT\s+P[ER]R[I1]N[T7]AH\s+B[A4]Y[A4]R"
    return bool(re.search(pattern, text))


def is_drpp_cover(text):
    text = normalize_text(text)
    keywords = [
        "DAFTAR RINCIAN PERMINTAAN PEMBAYARAN",
        "DAFTAR RINCIAN PERMINTAAN"
    ]

    if "LAMPIRAN DAFTAR RINCIAN" in text:
        return False

    return any(keyword in text for keyword in keywords)


def is_drpp_attachment(text):
    text = normalize_text(text)
    keywords = [
        "LAMPIRAN DAFTAR RINCIAN PERMINTAAN PEMBAYARAN",
        "LAMPIRAN DAFTAR RINCIAN PERMINTAAN"
    ]
    return any(keyword in text for keyword in keywords)


def is_receipt_page(text):
    text = normalize_text(text)
    keywords = ["KUITANSI BUKTI PEMBAYARAN", "KUITANSI", "LAMPIRAN KUITANSI"]
    return any(keyword in text for keyword in keywords)


def is_payment_proof_page(text):
    text = normalize_text(text)
    strong_keywords = [
        "FUND TRANSFER", "BUKTI TRANSFER", "BUKTI TRANSAKSI", "TOTAL TRANSFER AMOUNT"
    ]

    if any(keyword in text for keyword in strong_keywords):
        return True

    secondary_keywords = [
        "TRANSACTION STATUS", "TRANSFER AMOUNT", "TRANSACTION ID",
        "REFERENCE NUMBER", "STATUS TRANSAKSI"
    ]

    found = sum(keyword in text for keyword in secondary_keywords)
    return found >= 2


# =========================================================
# 6. ANALISIS DAN DETEKSI KELOMPOK
# =========================================================

def analyze_pages(pages):
    spb_pages = []
    drpp_covers = []
    drpp_attachments = []
    receipt_pages = []
    payment_pages = []
    diagnostics = []

    for item in pages:
        page_number = item["page"]
        text = item["text"]

        is_spb = is_spb_page(text)
        spb_number = extract_spb_number(text) if is_spb else None

        cover = is_drpp_cover(text)
        attachment = is_drpp_attachment(text)
        receipt = is_receipt_page(text)
        payment = is_payment_proof_page(text)

        if cover:
            drpp_covers.append(page_number)
        if attachment:
            drpp_attachments.append(page_number)
        if receipt:
            receipt_pages.append(page_number)
        if payment:
            payment_pages.append(page_number)
        if is_spb:
            spb_pages.append({
                "page": page_number,
                "number": spb_number
            })

        types = []
        if cover:
            types.append("DRPP")
        if attachment:
            types.append("Lampiran DRPP")
        if is_spb:
            types.append(f"SPB {spb_number or 'Nomor belum terbaca'}")
        if receipt:
            types.append("Kuitansi")
        if payment:
            types.append("Bukti pembayaran")

        diagnostics.append({
            "page": page_number,
            "types": ", ".join(types) if types else "Belum dikenali"
        })

    return {
        "spb_pages": spb_pages,
        "drpp_covers": drpp_covers,
        "drpp_attachments": drpp_attachments,
        "receipt_pages": receipt_pages,
        "payment_pages": payment_pages,
        "diagnostics": diagnostics
    }


def detect_groups(pages):
    analysis = analyze_pages(pages)

    valid_spb = [
        item for item in analysis["spb_pages"]
        if item["number"] is not None
    ]
    valid_spb.sort(key=lambda x: x["page"])

    unique_spb = []
    seen = set()

    for item in valid_spb:
        key = (item["page"], item["number"])
        if key not in seen:
            unique_spb.append(item)
            seen.add(key)

    valid_spb = unique_spb

    if not valid_spb:
        return [], {
            **analysis,
            "common_covers": [],
            "common_attachments": [],
            "drpp_number": None,
            "error": "Nomor SPB tidak berhasil ditemukan."
        }

    first_spb_page = valid_spb[0]["page"]

    common_covers = [
        p for p in analysis["drpp_covers"]
        if p < first_spb_page
    ]

    common_attachments = [
        p for p in analysis["drpp_attachments"]
        if p < first_spb_page
    ]

    drpp_number = None
    for cover_p in common_covers:
        p_item = next((p for p in pages if p["page"] == cover_p), None)
        if p_item:
            num = extract_drpp_number(p_item["text"])
            if num:
                drpp_number = num
                break

    total_pages = pages[-1]["page"]
    groups = []

    for index, spb in enumerate(valid_spb):
        start = spb["page"]
        if index + 1 < len(valid_spb):
            hard_end = valid_spb[index + 1]["page"] - 1
        else:
            hard_end = total_pages

        proofs = [
            p for p in analysis["payment_pages"]
            if start <= p <= hard_end
        ]

        if proofs:
            end = min(proofs)
            end_reason = "Bukti pembayaran terdeteksi"
            needs_review = False
        else:
            end = hard_end
            end_reason = "Batas SPB berikutnya / akhir PDF"
            needs_review = True

        groups.append({
            "number": spb["number"],
            "start": start,
            "end": end,
            "spb_page": start,
            "end_reason": end_reason,
            "needs_review": needs_review
        })

    return groups, {
        **analysis,
        "common_covers": common_covers,
        "common_attachments": common_attachments,
        "drpp_number": drpp_number,
        "error": None
    }


# =========================================================
# 7. PEMISAHAN PDF
# =========================================================

def split_pdf(
    pdf_bytes,
    groups,
    common_covers=None,
    common_attachments=None,
    drpp_number=None
):
    if common_covers is None:
        common_covers = []

    if common_attachments is None:
        common_attachments = []

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    results = {}

    all_drpp_pages = sorted(
        set(common_covers + common_attachments)
    )

    if not all_drpp_pages:
        raise ValueError(
            "Halaman DRPP dan lampirannya belum ditemukan."
        )

    def create_pdf(page_numbers):
        writer = PdfWriter()
        for page_number in page_numbers:
            if page_number < 1 or page_number > total_pages:
                raise ValueError(
                    f"Halaman {page_number} tidak valid."
                )
            writer.add_page(reader.pages[page_number - 1])

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    # 1 File DRPP gabungan
    if drpp_number:
        drpp_filename = f"DRPP {drpp_number}.pdf"
    else:
        drpp_filename = "DRPP Gabungan.pdf"

    results[drpp_filename] = create_pdf(all_drpp_pages)

    # File SPB per kelompok
    groups = sorted(groups, key=lambda g: int(g["start"]))
    previous_end = 0

    for group in groups:
        nomor = group["number"].split("/")[0]
        start = int(group["start"])
        end = int(group["end"])

        if start < 1 or end > total_pages or start > end:
            raise ValueError(f"Rentang halaman SPB {nomor} tidak valid.")

        if start <= previous_end:
            raise ValueError("Rentang halaman SPB saling bertumpang tindih.")

        previous_end = end
        spb_filename = f"SPB {nomor}.pdf"
        spb_pages = list(range(start, end + 1))
        results[spb_filename] = create_pdf(spb_pages)

    return results