import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger("ai_content")

# Jinja2 env — unchanged, keeps existing template
_template_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)


def render_email_html(
    title: str,
    summary: str,
    content: str,
    subscriber_name: str,
) -> str:
    """Render the Jinja2 email template into an HTML string."""
    template = _jinja_env.get_template("email.html")
    return template.render(
        title=title,
        summary=summary,
        content=content,
        subscriber_name=subscriber_name,
    )


def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
) -> str:
    """
    Send a single HTML email via SMTP (STARTTLS).

    Returns a pseudo message-id on success.
    Raises on any failure so Celery's existing retry logic fires.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = settings.EMAIL_FROM
    msg["To"]      = f"{to_name} <{to_email}>"
    msg.set_content("Please use an HTML-capable email client.")
    msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(msg)

        message_id = f"smtp-{to_email}-{subject[:20]}"
        logger.info(f"Email sent via SMTP to {to_email}")
        return message_id

    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error sending to {to_email}: {exc}")
        raise  # let Celery retry