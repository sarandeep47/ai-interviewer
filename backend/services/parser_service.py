import io
import logging
from pypdf import PdfReader
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import pytesseract and check if it's functional
HAS_PYTESSERACT = False
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    pass

# Try to import PyMuPDF
HAS_FITZ = False
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    pass

# PaddleOCR cached engine holder
_paddle_ocr_engine = None

class ResumeParserError(Exception):
    pass

def ocr_image(image: Image.Image) -> str:
    """Performs OCR on a PIL Image using Tesseract, falling back to PaddleOCR."""
    errors = []
    
    # 1. Try Tesseract
    if HAS_PYTESSERACT:
        try:
            text = pytesseract.image_to_string(image)
            if text and text.strip():
                logger.info("OCR successfully completed using Tesseract.")
                return text.strip()
        except Exception as e:
            err_msg = f"Tesseract OCR failed: {str(e)}"
            errors.append(err_msg)
            logger.warning(err_msg)
            
    # 2. Try PaddleOCR (fallback)
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        
        logger.info("Attempting PaddleOCR fallback...")
        global _paddle_ocr_engine
        if _paddle_ocr_engine is None:
            # show_log=False to prevent console clutter
            _paddle_ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            
        img_np = np.array(image)
        result = _paddle_ocr_engine.ocr(img_np, cls=True)
        text_lines = []
        if result:
            for line in result:
                if line:
                    for res in line:
                        if res and len(res) > 1 and isinstance(res[1], tuple):
                            text_lines.append(res[1][0])
                            
        text = "\n".join(text_lines)
        if text and text.strip():
            logger.info("OCR successfully completed using PaddleOCR.")
            return text.strip()
    except Exception as e:
        err_msg = f"PaddleOCR fallback failed: {str(e)}"
        errors.append(err_msg)
        logger.warning(err_msg)
        
    # If both engines failed
    error_summary = " | ".join(errors) or "No OCR engines configured or available."
    raise ResumeParserError(f"All OCR engines failed: {error_summary}")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from a digital PDF using pypdf."""
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error in pypdf extraction: {str(e)}")
        raise ResumeParserError(f"Failed to read digital PDF: {str(e)}")

def extract_text_from_scanned_pdf(file_bytes: bytes) -> str:
    """Renders scanned PDF pages to images using PyMuPDF and runs OCR on them."""
    if not HAS_FITZ:
        raise ResumeParserError("PyMuPDF (fitz) is not installed. Scanned PDF parsing is unavailable.")
        
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = ""
        for i, page in enumerate(doc):
            logger.info(f"Running OCR on scanned PDF page {i+1}/{len(doc)}")
            # Render page to a high-res image (2x zoom matrix) for accurate OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            page_text = ocr_image(image)
            full_text += page_text + "\n"
            
        return full_text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from scanned PDF: {str(e)}")
        raise ResumeParserError(f"Failed to OCR scanned PDF: {str(e)}")

def extract_text_from_image(file_bytes: bytes) -> str:
    """Extracts text from an image using OCR."""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        return ocr_image(image)
    except Exception as e:
        logger.warning(f"Image OCR failed: {str(e)}")
        raise ResumeParserError(str(e))

def parse_resume(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """
    Main entry point for parsing resume files. Handles digital PDFs, scanned PDFs (via OCR),
    and resume images (PNG, JPG, etc.).
    """
    filename_lc = filename.lower()
    
    # 1. Handle PDF
    if filename_lc.endswith('.pdf') or content_type == 'application/pdf':
        try:
            text = extract_text_from_pdf(file_bytes)
            # If the text is very short, it's likely a scanned PDF
            if len(text) < 150:
                logger.info("PDF text extraction yielded very short content. Attempting backend OCR on scanned PDF...")
                try:
                    ocr_text = extract_text_from_scanned_pdf(file_bytes)
                    if ocr_text and len(ocr_text.strip()) >= 50:
                        return {
                            "success": True,
                            "text": ocr_text,
                            "method": "backend_ocr"
                        }
                    else:
                        raise ResumeParserError("Scanned PDF OCR extracted insufficient text.")
                except Exception as ocr_err:
                    logger.warning(f"Backend scanned PDF OCR failed: {str(ocr_err)}")
                    # Return client OCR fallback trigger
                    return {
                        "success": False,
                        "method": "client_ocr_required",
                        "error": f"Scanned PDF OCR failed: {str(ocr_err)}. Please upload a text-based PDF or convert to image for client-side OCR."
                    }
            return {
                "success": True,
                "text": text,
                "method": "pdf_text"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    # 2. Handle Images
    elif any(filename_lc.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp']) or 'image' in content_type:
        try:
            text = extract_text_from_image(file_bytes)
            if not text:
                return {
                    "success": False,
                    "method": "client_ocr_required",
                    "error": "Backend OCR completed but extracted no text. Try client-side OCR."
                }
            return {
                "success": True,
                "text": text,
                "method": "backend_ocr"
            }
        except Exception as e:
            return {
                "success": False,
                "method": "client_ocr_required",
                "error": f"Backend OCR failed: {str(e)}. Proceeding with client-side OCR fallback."
            }
            
    # 3. Unsupported format
    else:
        return {
            "success": False,
            "error": "Unsupported file format. Please upload a PDF, PNG, JPG, or JPEG file."
        }
