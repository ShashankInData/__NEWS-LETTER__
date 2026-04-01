import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path
import logging

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Path to the templates/ directory (sibling of delivery/)
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _build_html(newsletter: list, analysis: dict = None) -> str:
    """Render the newsletter_email.html Jinja2 template."""
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    template = _jinja_env.get_template("newsletter_email.html")
    return template.render(
        now=now,
        newsletter=newsletter,
        analysis=analysis or {},
    )


def send_email(
    newsletter: list,
    analysis: dict,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    from_email: str = None,
) -> bool:
    """Send newsletter + analysis as an HTML email via SMTP."""
    if from_email is None:
        from_email = smtp_user

    now = datetime.now(timezone.utc).strftime("%b %d, %Y")
    theme = analysis.get("weekly_theme", "AI/ML Digest") if analysis else "AI/ML Digest"
    subject = f"AI Pulse — {theme} ({now})"

    html_body = _build_html(newsletter, analysis)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Pulse <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"Sending email to {to_email} via {smtp_host}:{smtp_port}")
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
