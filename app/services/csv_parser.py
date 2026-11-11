import csv
import io
import re
from typing import List, Dict, Any, Tuple, Optional

# Standard normalization aliases
HEADER_ALIASES = {
    'email': ['email', 'email address', 'work email', 'recipient email', 'e-mail', 'mail', 'contact email'],
    'first_name': ['first name', 'first_name', 'firstname', 'given name', 'fname'],
    'last_name': ['last name', 'last_name', 'lastname', 'surname', 'family name', 'lname'],
    'name': ['name', 'full name', 'fullname', 'contact name', 'person name'],
    'company': ['company', 'company name', 'company_name', 'organization', 'organisation', 'account', 'business'],
    'phone': ['phone', 'phone number', 'phone_no', 'mobile', 'cell', 'telephone', 'contact number'],
    'title': ['title', 'job title', 'designation', 'role', 'position'],
    'location': ['location', 'city', 'country', 'region', 'address', 'state']
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_header_name(header: str) -> str:
    """Normalizes header string into a safe identifier (lowercase, underscore)."""
    h = header.strip().lower()
    h = re.sub(r'[^\w\s]', '', h)
    h = re.sub(r'\s+', '_', h)
    return h or 'column'


def match_standard_alias(header: str) -> Optional[str]:
    """Matches a header string against known standard aliases."""
    clean = header.strip().lower()
    for standard_name, aliases in HEADER_ALIASES.items():
        if clean in aliases:
            return standard_name
    return None


def parse_csv_content(
    file_bytes: bytes,
    max_rows: int = 10000,
    max_file_size_mb: int = 10
) -> Dict[str, Any]:
    """
    Parses a CSV file with:
    - UTF-8 and UTF-8 BOM support
    - Arbitrary headers preserved
    - Header normalization & alias matching
    - Dynamic placeholder discovery
    - Email validation & duplicate detection
    - Row count & size limit enforcement
    """
    if len(file_bytes) > max_file_size_mb * 1024 * 1024:
        raise ValueError(f"File size exceeds maximum allowed limit of {max_file_size_mb}MB.")

    # Handle UTF-8 BOM
    if file_bytes.startswith(b'\xef\xbb\xbf'):
        text_content = file_bytes[3:].decode('utf-8', errors='replace')
    else:
        try:
            text_content = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text_content = file_bytes.decode('latin-1', errors='replace')

    # Parse with csv.reader
    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)

    if not rows:
        raise ValueError("The uploaded CSV file is empty.")

    # Locate first non-empty header row
    header_row_index = -1
    raw_headers = []
    for idx, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_row_index = idx
            raw_headers = [c.strip() for c in row]
            break

    if header_row_index == -1 or not raw_headers:
        raise ValueError("Could not find a valid header row in the CSV file.")

    # Build header mapping and placeholder list
    detected_headers = []
    mapping_suggestions = {}
    normalized_keys = []
    seen_keys = set()

    for idx, raw_h in enumerate(raw_headers):
        clean_raw = raw_h if raw_h else f"Column_{idx+1}"
        norm_key = normalize_header_name(clean_raw)
        
        # Avoid collisions in normalized keys
        base_key = norm_key
        counter = 1
        while norm_key in seen_keys:
            norm_key = f"{base_key}_{counter}"
            counter += 1
        seen_keys.add(norm_key)

        alias_match = match_standard_alias(clean_raw)

        detected_headers.append({
            'index': idx,
            'raw_name': clean_raw,
            'normalized_key': norm_key,
            'suggested_field': alias_match or norm_key,
            'placeholder': f"{{{{{norm_key}}}}}"
        })
        normalized_keys.append(norm_key)
        if alias_match:
            mapping_suggestions[alias_match] = norm_key

    # Find email column candidate
    email_column_key = None
    if 'email' in mapping_suggestions:
        email_column_key = mapping_suggestions['email']
    else:
        # Check by content heuristic or header substring
        for h in detected_headers:
            if 'email' in h['raw_name'].lower() or 'mail' in h['raw_name'].lower():
                email_column_key = h['normalized_key']
                break

    # Parse data rows
    data_rows = rows[header_row_index + 1:]
    if len(data_rows) > max_rows:
        raise ValueError(f"CSV row count ({len(data_rows)}) exceeds maximum allowed limit of {max_rows} rows.")

    valid_recipients = []
    invalid_recipients = []
    seen_emails = set()
    total_parsed_rows = 0

    for row_idx, row in enumerate(data_rows, start=header_row_index + 2):
        # Skip completely empty rows
        if not any(c.strip() for c in row):
            continue

        total_parsed_rows += 1
        row_dict = {}
        for col_idx, norm_k in enumerate(normalized_keys):
            val = row[col_idx].strip() if col_idx < len(row) else ''
            row_dict[norm_k] = val

        # Extract email
        raw_email = row_dict.get(email_column_key, '') if email_column_key else ''
        if not raw_email:
            # Fallback scan for an email-like value across columns if not mapped
            for k, v in row_dict.items():
                if '@' in v and EMAIL_REGEX.match(v):
                    raw_email = v
                    break

        norm_email = raw_email.strip().lower()

        if not norm_email:
            invalid_recipients.append({
                'row_number': row_idx,
                'email': '',
                'reason': 'Missing email address',
                'data': row_dict
            })
            continue

        if not EMAIL_REGEX.match(norm_email):
            invalid_recipients.append({
                'row_number': row_idx,
                'email': norm_email,
                'reason': 'Invalid email address format',
                'data': row_dict
            })
            continue

        if norm_email in seen_emails:
            invalid_recipients.append({
                'row_number': row_idx,
                'email': norm_email,
                'reason': 'Duplicate email in CSV',
                'data': row_dict
            })
            continue

        seen_emails.add(norm_email)
        valid_recipients.append({
            'row_number': row_idx,
            'email': norm_email,
            'data': row_dict
        })

    return {
        'total_rows_read': total_parsed_rows,
        'valid_count': len(valid_recipients),
        'invalid_count': len(invalid_recipients),
        'detected_headers': detected_headers,
        'email_column_key': email_column_key,
        'placeholders': [h['placeholder'] for h in detected_headers],
        'valid_recipients': valid_recipients,
        'invalid_recipients': invalid_recipients,
        'sample_preview': valid_recipients[:5]
    }
