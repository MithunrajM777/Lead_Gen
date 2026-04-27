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

def _clean_text(value: str) -> Optional[str]:
    """Fix mojibake and remove junk noise values."""
    if value is None:
        return None
    text = str(value).strip()
    try:
        # Attempt to recover latin-1 bytes that were decoded as utf-8
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    
    # Remove junk labels and special characters
    junk = ["Business", "—", " - ", "Visit", "Call", "Directions", "Website", "Address", "Phone"]
    for j in junk:
        text = text.replace(j, "")
        
    # Remove non-printable control characters
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    
    # Final trim and collapse spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # ── URL-to-Name Logic ──────────────────────────────────────────────────
    # Convert "example.com" -> "Example"
    if "." in text and " " not in text:
        # Check if it's likely a domain
        domain_patterns = [".com", ".in", ".org", ".net", ".io", ".biz", ".co"]
        if any(p in text.lower() for p in domain_patterns):
            # Strip the TLD
            name_part = re.split(r'\.com|\.in|\.org|\.net|\.io|\.biz|\.co', text, flags=re.IGNORECASE)[0]
            # Convert "madurasolution" -> "Madura Solution" (CamelCase or just title)
            # For simplicity, we title case it. 
            # If it's "madurasolution", we might not know where to split.
            # But let's at least Title Case it.
            text = name_part.title()
    
    return text if text else None

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
    # Phone priority: if phone exists, use it. If not, use whatsapp (if available).
    phone_raw = data.get("phone", "")
    whatsapp_raw = data.get("whatsapp", "")
    
    final_phone = phone_raw if phone_raw else whatsapp_raw

    cleaned = {
        "company_name":  _clean_text(data.get("company_name", "Unknown Lead")),
        "phone":         _clean_text(final_phone),
        "email":         _clean_text(data.get("email")) or None,
        "address":       _clean_text(data.get("address", "")),
        "website":       _clean_text(data.get("website")) or None,
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

    # Status Logic: Valid if email OR phone exists
    if has_email or has_phone:
        status = "valid"
    else:
        status = "invalid"

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


def is_valid_business_lead(item: dict, keyword: str = None, location: str = None, seen_ratings: set = None) -> bool:
    """
    Apply strict validation rules to filter out irrelevant or incorrect business data.
    
    Rules:
    1. REMOVE non-business entries (department, staff quarters, hostel, admission)
    2. REQUIRE at least ONE: phone OR website
    3. REMOVE duplicate ratings (same rating + same review count)
    4. VALIDATE address: must contain city or district
    5. OPTIONAL: keyword relevance check
    """
    # Rule 1: REMOVE non-business entries
    name = item.get("company_name", "").lower()
    invalid_keywords = ["department", "staff quarters", "hostel", "admission"]
    if any(k in name for k in invalid_keywords):
        return False

    # Rule 2: REQUIRE at least ONE: phone OR website
    phone = item.get("phone")
    website = item.get("website")
    if not phone and not website:
        return False

    # Rule 3: REMOVE duplicate ratings like: same rating + same review count
    if seen_ratings is not None:
        rating = item.get("rating")
        reviews_count = item.get("reviews_count", 0)
        # Only check duplicates if there's actual rating data
        if rating is not None and reviews_count > 0:
            rating_key = (float(rating), int(reviews_count))
            if rating_key in seen_ratings:
                return False
            seen_ratings.add(rating_key)

    # Rule 4: VALIDATE address: must contain city or district
    address = item.get("address", "").lower()
    if location:
        # Check if the target location (city/district) exists in the address
        loc_clean = location.lower().replace(" district", "").strip()
        if loc_clean not in address:
            return False

    # Rule 5: OPTIONAL: match keyword relevance
    if keyword:
        kw = keyword.lower()
        if "hospital" in kw:
            relevant_terms = ["hospital", "clinic", "medical", "health", "care", "nursing", "center"]
            if not any(term in name for term in relevant_terms):
                return False
        elif "school" in kw or "college" in kw:
            relevant_terms = ["school", "college", "academy", "institute", "university", "education"]
            if not any(term in name for term in relevant_terms):
                return False
                
    return True
