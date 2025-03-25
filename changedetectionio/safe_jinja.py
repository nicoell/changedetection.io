"""
Safe Jinja2 render with max payload sizes

See https://jinja.palletsprojects.com/en/3.1.x/sandbox/#security-considerations
"""

import jinja2.sandbox
import typing as t
import os

JINJA2_MAX_RETURN_PAYLOAD_SIZE = 1024 * int(os.getenv("JINJA2_MAX_RETURN_PAYLOAD_SIZE_KB", 1024 * 10))


def render(template_str, **args: t.Any) -> str:
    jinja2_env = jinja2.sandbox.ImmutableSandboxedEnvironment(extensions=['jinja2_time.TimeExtension'])
    from changedetectionio.jinja_filter import parse_json
    from changedetectionio.jinja_filter import parse_html
    jinja2_env.filters['parse_json'] = parse_json
    jinja2_env.filters['parse_html'] = parse_html
    output = jinja2_env.from_string(template_str).render(args)
    return output[:JINJA2_MAX_RETURN_PAYLOAD_SIZE]

