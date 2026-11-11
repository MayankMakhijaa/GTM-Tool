import re
import html
from typing import Dict, Any, List, Tuple, Optional
from bs4 import BeautifulSoup

# Strict allowed tags for rich email HTML formatting
ALLOWED_TAGS = {
    'p', 'br', 'span', 'div', 'b', 'strong', 'i', 'em', 'u', 's', 'strike',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'blockquote', 'pre', 'code', 'img'
}

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height', 'style'],
    'span': ['style', 'class'],
    'div': ['style', 'class'],
    'p': ['style', 'class'],
    'table': ['style', 'class', 'border', 'cellpadding', 'cellspacing', 'width'],
    'td': ['style', 'class', 'width', 'align', 'valign'],
    'th': ['style', 'class', 'width', 'align', 'valign']
}

# Regex for dynamic placeholder: {{variable}} or {{ variable }}
PLACEHOLDER_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def sanitize_email_html(raw_html: str) -> str:
    """
    Sanitizes user-provided email HTML to prevent XSS and script injection.
    Strips scripts, iframes, objects, forms, and on* event handlers.
    """
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, 'html.parser')

    # Remove script and malicious tags
    for tag in soup(['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'link', 'meta']):
        tag.decompose()

    # Clean attributes on all remaining tags
    for element in soup.find_all():
        if element.name not in ALLOWED_TAGS:
            # Unwrap tag content instead of deleting it
            element.unwrap()
            continue

        allowed_attrs = ALLOWED_ATTRIBUTES.get(element.name, ['style', 'class'])
        current_attrs = dict(element.attrs)
        for attr, val in current_attrs.items():
            # Disallow all on* handlers
            if attr.lower().startswith('on') or attr.lower().startswith('data-'):
                del element[attr]
            elif attr not in allowed_attrs:
                del element[attr]
            elif attr == 'href':
                # Check javascript: protocol
                if isinstance(val, str) and (val.strip().lower().startswith('javascript:') or val.strip().lower().startswith('data:')):
                    element['href'] = '#'

    return str(soup)


def extract_template_placeholders(text: str) -> List[str]:
    """Finds all unique placeholder names in the given template text."""
    if not text:
        return []
    return sorted(list(set(PLACEHOLDER_REGEX.findall(text))))


def render_template_string(
    template: str,
    recipient_data: Dict[str, Any],
    fallback_value: str = "",
    is_html: bool = False
) -> Tuple[str, List[str]]:
    """
    Safely renders a template string with recipient's CSV data.
    - Missing or empty values are replaced with fallback_value (never 'undefined' or 'null').
    - Reports any placeholders that had missing values.
    - If is_html=True, performs HTML escaping on inserted placeholder values.
    Returns: (rendered_string, missing_placeholder_names)
    """
    if not template:
        return "", []

    missing_keys = []

    def replace_match(match):
        var_name = match.group(1).lower().strip()
        val = recipient_data.get(var_name)
        
        # If not found directly, try without underscores
        if val is None or str(val).strip() == "":
            missing_keys.append(var_name)
            replacement = fallback_value
        else:
            replacement = str(val).strip()

        if is_html:
            replacement = html.escape(replacement)

        return replacement

    rendered = PLACEHOLDER_REGEX.sub(replace_match, template)
    return rendered, sorted(list(set(missing_keys)))


def render_email_preview(
    subject_template: str,
    body_html_template: str,
    body_text_template: Optional[str],
    recipient_data: Dict[str, Any],
    fallback_value: str = ""
) -> Dict[str, Any]:
    """
    Renders preview for a single recipient, checking subject and body.
    Returns rendered subject, body_html, body_text, and missing placeholders flagged.
    """
    rendered_subject, missing_subj = render_template_string(
        subject_template, recipient_data, fallback_value=fallback_value, is_html=False
    )
    
    rendered_html, missing_html = render_template_string(
        body_html_template, recipient_data, fallback_value=fallback_value, is_html=True
    )

    rendered_text = ""
    missing_text = []
    if body_text_template:
        rendered_text, missing_text = render_template_string(
            body_text_template, recipient_data, fallback_value=fallback_value, is_html=False
        )
    else:
        # Generate plain text from HTML
        soup = BeautifulSoup(rendered_html, 'html.parser')
        rendered_text = soup.get_text(separator="\n").strip()

    all_missing = sorted(list(set(missing_subj + missing_html + missing_text)))

    return {
        'rendered_subject': rendered_subject,
        'rendered_body_html': rendered_html,
        'rendered_body_text': rendered_text,
        'missing_placeholders': all_missing,
        'has_missing_values': len(all_missing) > 0
    }
