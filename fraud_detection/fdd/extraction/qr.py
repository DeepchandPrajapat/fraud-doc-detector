"""QR detection + decoding, including UIDAI Aadhaar Secure QR.

Aadhaar Secure QR format (UIDAI spec):
  big decimal integer -> bytes -> gzip-decompress ->
  [text fields separated by 0xFF] [JPEG2000 photo] [optional email/mobile hashes] [256-byte RSA signature]
The signature covers every byte before it. Signature verification itself happens in F1;
here we only decode and split out signed_bytes / signature.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zlib

import cv2
import numpy as np

from fdd.schemas import QRData

SECURE_FIELDS_V2 = [
    "version", "email_mobile_indicator", "reference_id", "name", "dob", "gender",
    "care_of", "district", "landmark", "house", "location", "pincode", "post_office",
    "state", "street", "sub_district", "vtc", "last_4_mobile",
]
SECURE_FIELDS_V1 = SECURE_FIELDS_V2[1:-1]   # legacy: no version tag, no last_4_mobile
SIGNATURE_LEN = 256


def detect_qr_strings(img: np.ndarray) -> list[str]:
    """Try several preprocessing variants; dense Aadhaar QRs often need upscaling."""
    detector = cv2.QRCodeDetector()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    variants = [gray]
    if max(gray.shape) < 2500:
        variants.append(cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
    variants.append(cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 31, 10))
    found: list[str] = []
    for v in variants:
        try:
            ok, texts, _, _ = detector.detectAndDecodeMulti(v)
        except cv2.error:
            ok, texts = False, []
        if ok:
            found.extend(t for t in texts if t)
        if found:
            break
    return list(dict.fromkeys(found))


def _parse_dob(s: str) -> str:
    m = re.match(r"(\d{2})[-/](\d{2})[-/](\d{4})", s)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else s


def decode_aadhaar_secure(raw: str) -> QRData:
    data = int(raw).to_bytes((int(raw).bit_length() + 7) // 8, "big")
    plain = zlib.decompress(data, 16 + zlib.MAX_WBITS)
    signed, signature = plain[:-SIGNATURE_LEN], plain[-SIGNATURE_LEN:]

    parts = signed.split(b"\xff")
    is_v2 = parts[0].startswith(b"V")
    names = SECURE_FIELDS_V2 if is_v2 else SECURE_FIELDS_V1
    payload = {k: parts[i].decode("iso-8859-1") for i, k in enumerate(names) if i < len(parts)}
    if not is_v2:
        payload["version"] = "V1"
    if "dob" in payload:
        payload["dob"] = _parse_dob(payload["dob"])
    # reference_id = last 4 digits of Aadhaar + timestamp
    ref = payload.get("reference_id", "")
    payload["aadhaar_last4"] = ref[:4] if ref[:4].isdigit() else None
    return QRData(raw=raw, kind="aadhaar_secure", payload=payload,
                  signed_bytes=signed, signature=signature)


def decode_aadhaar_xml(raw: str) -> QRData:
    root = ET.fromstring(raw.split("?>", 1)[-1].strip())
    attrs = dict(root.attrib)
    payload = {
        "uid": attrs.get("uid"), "name": attrs.get("name"), "gender": attrs.get("gender"),
        "dob": _parse_dob(attrs.get("dob", "")) if attrs.get("dob") else attrs.get("yob"),
        "care_of": attrs.get("co"), "pincode": attrs.get("pc"), "state": attrs.get("state"),
    }
    return QRData(raw=raw, kind="aadhaar_xml", payload=payload)


def decode_qr(raw: str) -> QRData:
    s = raw.strip()
    try:
        if s.isdigit() and len(s) > 500:
            return decode_aadhaar_secure(s)
        if "PrintLetterBarcodeData" in s:
            return decode_aadhaar_xml(s)
    except Exception as e:  # noqa: BLE001 - malformed QR is itself a signal for F1/F12
        return QRData(raw=raw, kind="aadhaar_invalid", payload={"error": str(e)})
    if re.match(r"https?://", s, re.IGNORECASE):
        return QRData(raw=raw, kind="url", payload={"url": s})
    return QRData(raw=raw, kind="text", payload={"text": s})


def extract_qr(pages: list[np.ndarray]) -> list[QRData]:
    out = []
    for img in pages:
        out.extend(decode_qr(s) for s in detect_qr_strings(img))
    return out
