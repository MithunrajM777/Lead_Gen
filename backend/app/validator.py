import os
import re
import dns.resolver
import smtplib
import socket
import httpx
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

# --- DISPOSABLE DOMAINS (Local Cache) ---
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "temp-mail.org", "10minutemail.com",
    "yopmail.com", "sharklasers.com", "maildrop.cc", "dispostable.com"
}


# --- ENCODING CLEANUP ---

def _clean_text(value: str) -> str:
    """Fix mojibake (ï¿½ artifacts) caused by double-encoding."""
    if not value:
        return ""
    text = value.strip()
    try:
        # Attempt to recover latin-1 bytes that were decoded as utf-8
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    # Remove non-printable control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()

# --- EMAIL VALIDATION ---

def is_disposable(email: str):
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return domain in DISPOSABLE_DOMAINS

def verify_smtp(email: str):
    """Attempt to verify mailbox existence via SMTP ping."""
    if not os.getenv("SMTP_ENABLED", "false").lower() == "true":
        return True, "SMTP verification skipped (disabled)"
    
    try:
        domain = email.split("@")[-1]
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(mx_records[0].exchange)
        
        # Connect to MX server
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_host)
        server.helo(server.local_hostname)
        server.mail(os.getenv("SMTP_SENDER", "verify@example.com"))
        code, message = server.rcpt(email)
        server.quit()
        
        if code == 250:
            return True, "Mailbox verified"
        return False, f"Mailbox may not exist (Code: {code})"
    except Exception as e:
        return True, f"SMTP verification inconclusive: {str(e)}"

def validate_business_email(email: str):
    if not email:
        return {"valid": False, "error": "No email provided"}
    
    if is_disposable(email):
        return {"valid": False, "email": email, "error": "Disposable email domain detected"}

    try:
        # Step 1: Syntax and MX check
        valid = validate_email(email, check_deliverability=True)
        norm_email = valid.normalized
        
        # Step 2: SMTP Verification (Advanced)
        smtp_valid, smtp_msg = verify_smtp(norm_email)
        
        return {
            "valid": smtp_valid, 
            "email": norm_email, 
            "error": None if smtp_valid else smtp_msg,
            "smtp_note": smtp_msg
        }
    except EmailNotValidError as e:
        return {"valid": False, "email": email, "error": str(e)}

# --- PHONE VALIDATION ---

def validate_business_phone(phone: str, country_code: str = "IN"):
    """Validate phone numbers. Defaults to India (IN). Supports E.164 input too."""
    if not phone:
        return {"valid": False, "error": "No phone provided"}
    # Strip common noise characters
    cleaned_phone = re.sub(r"[\s\-().]", "", phone.strip())
    try:
        parsed_number = phonenumbers.parse(cleaned_phone, country_code)
        if phonenumbers.is_valid_number(parsed_number):
            formatted_number = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
            return {
                "valid": True,
                "phone": formatted_number,
                "type": phonenumbers.number_type(parsed_number),
                "error": None
            }
        return {"valid": False, "phone": phone, "error": "Invalid phone format"}
    except Exception as e:
        return {"valid": False, "phone": phone, "error": str(e)}

# --- ADDRESS VALIDATION ---

def validate_business_address(address: str):
    if not address or len(address) < 5:
        return {"valid": False, "address": address, "error": "Address too short"}
    
    # Try Google Maps API Fallback (Architect Upgrade)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if api_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
            response = httpx.get(url, timeout=10.0)
            data = response.json()
            if data["status"] == "OK":
                result = data["results"][0]
                return {
                    "valid": True, 
                    "address": result["formatted_address"],
                    "latitude": result["geometry"]["location"]["lat"],
                    "longitude": result["geometry"]["location"]["lng"],
                    "error": None
                }
        except Exception as e:
            print(f"Google Maps Geocoding failed: {e}")

    # Fallback to OpenStreetMap (Nominatim)
    try:
        geolocator = Nominatim(user_agent="leadgen_pro_v2")
        location = geolocator.geocode(address)
        if location:
            return {
                "valid": True, 
                "address": location.address, 
                "latitude": location.latitude, 
                "longitude": location.longitude,
                "error": None
            }
        return {"valid": False, "address": address, "error": "Address verification failed"}
    except Exception:
        return {"valid": True, "address": address, "error": "Geolocator rate-limited"}

# --- MAIN CLEANING ENGINE ---

def clean_and_validate(data: dict):
    """
    Clean raw scraped data and assign a lead status:
      valid      — at least one of email/phone is formally verified
      unverified — email/phone present but verification inconclusive (SMTP disabled, etc.)
      invalid    — BOTH email AND phone are absent; no way to contact the lead
    """
    cleaned = {
        "company_name":  _clean_text(data.get("company_name", "Unknown Lead")),
        "phone":         _clean_text(data.get("phone", "")),
        "email":         _clean_text(data.get("email", "")).lower(),
        "address":       _clean_text(data.get("address", "")),
        "website":       _clean_text(data.get("website", "")),
        "rating":        data.get("rating"),
        "reviews_count": data.get("reviews_count", 0),
        "category":      _clean_text(data.get("category", "Business")),
        "source":        data.get("source", "scraped"),
    }

    email_res = validate_business_email(cleaned["email"])
    phone_res = validate_business_phone(cleaned["phone"])
    addr_res  = validate_business_address(cleaned["address"])

    has_email = bool(cleaned["email"])
    has_phone = bool(cleaned["phone"])
    email_ok  = email_res.get("valid", False)
    phone_ok  = phone_res.get("valid", False)

    # No contactable info at all → invalid
    if not has_email and not has_phone:
        status = "invalid"
    # At least one formally verified → valid
    elif email_ok or phone_ok:
        status = "valid"
    # Present but verification inconclusive (SMTP off, etc.) → unverified
    else:
        status = "unverified"

    return {
        **cleaned,
        "email":   email_res.get("email", cleaned["email"]),
        "phone":   phone_res.get("phone", cleaned["phone"]),
        "address": addr_res.get("address", cleaned["address"]),
        "latitude":  addr_res.get("latitude"),
        "longitude": addr_res.get("longitude"),
        "validation_status": status,
        "validation_details": {
            "email":   email_res,
            "phone":   phone_res,
            "address": addr_res,
        },
    }
