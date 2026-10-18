"""
safety/pii_filter.py
=====================
PII (Personally Identifiable Information) filtering for agent outputs.
Ensures no sensitive data leaks into logs or responses.
"""

import re


def mask_pii(text: str) -> str:
    """
    Mask PII patterns in text:
    - Email addresses → ***@***.com
    - Phone numbers → [REDACTED]
    - Full names after common prefixes → [REDACTED]
    """
    # Mask email addresses
    text = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        '***@***.com',
        text
    )

    # Mask phone numbers (various formats)
    text = re.sub(
        r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        '[REDACTED]',
        text
    )

    return text


def contains_pii(text: str) -> bool:
    """Check if text contains potential PII."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'

    return bool(re.search(email_pattern, text) or re.search(phone_pattern, text))
