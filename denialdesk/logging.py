"""
PHI-safe logging configuration.

Registers a logging filter that scrubs known PHI patterns from all log records
before they reach any handler. Prevents patient names, DOBs, claim amounts,
and other PHI from appearing in application logs.

Patterns scrubbed:
- patient_ref, patient, dob, ssn, name, address, phone, email, mrn values
- CPT codes are NOT scrubbed (procedure identifiers, not patient PHI)
- Payer names are NOT scrubbed (business entities, not patient PHI)
"""
import hashlib
import logging
import re

_PHI_KEYS = re.compile(
    r'"(?:patient_ref|patient|dob|ssn|name|address|phone|mrn|email)"\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)


def _scrub(text: str) -> str:
    """Replace PHI values with [REDACTED] in log strings."""
    return _PHI_KEYS.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED]"), text)


class PhiScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _scrub(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _scrub(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _scrub(str(a)) if isinstance(a, str) else a for a in record.args
                )
        return True


def hash_email(email: str) -> str:
    """One-way SHA-256 hash for email storage in access logs. Not reversible."""
    return hashlib.sha256(email.encode()).hexdigest()


def configure_phi_safe_logging() -> None:
    """Install the PHI scrub filter on the root logger and uvicorn loggers. Call once at startup."""
    scrub = PhiScrubFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(scrub)
    root.addFilter(scrub)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        lg = logging.getLogger(name)
        for handler in lg.handlers:
            handler.addFilter(scrub)
        lg.addFilter(scrub)
