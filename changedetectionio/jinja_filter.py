import os

from wtforms.validators import ValidationError

JINJA2_MAX_JSON_SIZE_KB = 1024 * int(os.getenv("JINJA2_MAX_JSON_SIZE_KB", 1024 * 10))

def parse_json(value):
    """
        Parses the given string as JSON, with size and exception handling.
        Returns a Python object on success, or None on error.
    """
    import json
    if value is None or not value:
        return ""
    if len(value) > JINJA2_MAX_JSON_SIZE_KB:
        raise ValidationError(f"parse_json: Input size ({len(value)} bytes) exceeds {JINJA2_MAX_JSON_SIZE_KB}.")
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValidationError(f"JSON decode error: {e}") from e
    except Exception as e:
        # Catching a broad Exception to be safe, though typically ValueError/JSONDecodeError are primary.
        raise ValidationError(f"Unexpected error in parse_json: {e}") from e


JINJA2_MAX_HTML_SIZE_KB = 1024 * int(os.getenv("JINJA2_MAX_HTML_SIZE_KB", 1024 * 10))

def parse_html(value):
    if value is None or not value:
        return ""
    if len(value) > JINJA2_MAX_HTML_SIZE_KB:
        raise ValidationError(f"parse_html: Input size ({len(value)} bytes) exceeds {JINJA2_MAX_HTML_SIZE_KB}.")
    try:
        from lxml.html import HTMLParser, fromstring
        parser = HTMLParser(resolve_entities=False)
        return fromstring(value, parser=parser)
    except Exception as e:
        raise ValidationError(f"HTML parse error: {e}") from e
