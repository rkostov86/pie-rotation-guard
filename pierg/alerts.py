"""Send alerts by ntfy (phone) and Gmail SMTP (email); open/check GitHub issues."""
import json
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage

PRIORITY = {"ROUTINE": "default", "WATCH": "high", "SWITCH": "urgent", "DATA_ERROR": "high", "REMINDER": "high"}
TAGS = {"ROUTINE": "white_check_mark", "WATCH": "eyes", "SWITCH": "rotating_light",
        "DATA_ERROR": "warning", "REMINDER": "bell"}


def _ntfy(kind, title, body):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        raise RuntimeError("NTFY_TOPIC secret missing")
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), method="POST")
    req.add_header("Title", title.encode("ascii", "ignore").decode())
    req.add_header("Priority", PRIORITY.get(kind, "default"))
    req.add_header("Tags", TAGS.get(kind, "information_source"))
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def _email(title, body):
    user, pwd, to = (os.environ.get(k) for k in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_EMAIL_TO"))
    if not (user and pwd and to):
        raise RuntimeError("email secrets missing (SMTP_USER / SMTP_APP_PASSWORD / ALERT_EMAIL_TO)")
    msg = EmailMessage()
    msg["Subject"] = f"[pie-guard] {title}"
    msg["From"], msg["To"] = user, to
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(user, pwd.replace(" ", ""))
        s.send_message(msg)


def send(kind, title, body):
    """Send on both channels. Fails only if BOTH fail (so one broken channel still alerts you)."""
    errors = []
    for fn in (lambda: _ntfy(kind, title, body), lambda: _email(title, body)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    if len(errors) == 2:
        raise RuntimeError("all alert channels failed: " + " | ".join(errors))
    return errors  # partial failures are logged by the caller


def _gh(method, path, payload=None):
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        raise RuntimeError("GITHUB_REPOSITORY / GITHUB_TOKEN not set")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def open_issue(title, body):
    return _gh("POST", "/issues", {"title": title, "body": body, "labels": []})["number"]


def issue_is_open(number):
    return _gh("GET", f"/issues/{number}").get("state") == "open"
