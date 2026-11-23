import re
from pathlib import Path

_HOME = str(Path.home())
_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
_KEY_RE = re.compile(
    r'\b(sk-[a-zA-Z0-9_-]{20,}|ghp_[a-zA-Z0-9]+|AKIA[A-Z0-9]{16}'
    r'|Bearer\s+[a-zA-Z0-9._-]{16,})\b'
)
_HOME_RE = re.compile(re.escape(_HOME))


def redact(text: str) -> str:
    text = _HOME_RE.sub("~user~", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _KEY_RE.sub("[KEY]", text)
    return text
