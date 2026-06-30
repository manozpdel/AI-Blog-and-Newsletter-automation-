import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SyncSessionLocal
from app.models.email_log import EmailLog, EmailStatus
from app.models.newsletter import Newsletter
from app.models.subscriber import Subscriber
from app.services.email_service import render_email_html, send_email
from app.workers.celery_app import celery_app

logger = logging.getLogger("ai_content")


def _get_newsletter_sync(newsletter_id: int) -> dict:
    with SyncSessionLocal() as db:
        newsletter = db.get(Newsletter, newsletter_id)
        if newsletter is None:
            raise ValueError(f"Newsletter {newsletter_id} not found")
        article = newsletter.article
        return {
            "id": newsletter.id,
            "summary": newsletter.content,           
            "article_content": article.content,       
            "article_title": article.title or "AI Newsletter",
        }


def _get_active_subscribers_sync() -> list[dict]:
    with SyncSessionLocal() as db:
        result = db.execute(
            select(Subscriber).where(Subscriber.is_active == True)  # noqa: E712
        )
        subscribers = result.scalars().all()
        return [{"id": s.id, "name": s.name, "email": s.email} for s in subscribers]


def _create_email_log_sync(subscriber_id: int, newsletter_id: int) -> int:
    with SyncSessionLocal() as db:
        log = EmailLog(
            subscriber_id=subscriber_id,
            newsletter_id=newsletter_id,
            status=EmailStatus.PENDING,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log.id


def _update_email_log_sync(
    log_id: int,
    status: str,
    provider_message_id: str | None = None,
    error_message: str | None = None,
) -> None:
    with SyncSessionLocal() as db:
        log = db.get(EmailLog, log_id)
        if log is None:
            return
        log.status = status
        if provider_message_id:
            log.provider_message_id = provider_message_id
        if error_message:
            log.error_message = error_message
        if status == EmailStatus.SENT:
            log.sent_at = datetime.now(timezone.utc)
        db.commit()


# ---------------------------------------------------------------------------
# Task 1: Dispatch — queues one send task per active subscriber
# ---------------------------------------------------------------------------


@celery_app.task(name="email.dispatch_newsletter", queue="email_queue", bind=True)
def dispatch_newsletter_emails(self, newsletter_id: int) -> dict:
    newsletter = _get_newsletter_sync(newsletter_id)
    subscribers = _get_active_subscribers_sync()

    if not subscribers:
        logger.info(f"No active subscribers for newsletter {newsletter_id}")
        return {"newsletter_id": newsletter_id, "queued": 0}

    queued = 0
    for subscriber in subscribers:
        log_id = _create_email_log_sync(subscriber["id"], newsletter_id)
        send_newsletter_to_subscriber.apply_async(
            kwargs={
                "log_id": log_id,
                "newsletter_id": newsletter_id,
                "subscriber_id": subscriber["id"],
                "subscriber_name": subscriber["name"],
                "subscriber_email": subscriber["email"],
                "article_title": newsletter["article_title"],
                "newsletter_summary": newsletter["summary"],
                "article_content": newsletter["article_content"],   # ← full article
            },
            queue="email_queue",
        )
        queued += 1

    logger.info(f"Queued {queued} email tasks for newsletter {newsletter_id}")
    return {"newsletter_id": newsletter_id, "queued": queued}


# ---------------------------------------------------------------------------
# Task 2: Send — sends exactly one email, retries on failure
# ---------------------------------------------------------------------------


@celery_app.task(
    name="email.send_newsletter",
    queue="email_queue",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def send_newsletter_to_subscriber(
    self,
    log_id: int,
    newsletter_id: int,
    subscriber_id: int,
    subscriber_name: str,
    subscriber_email: str,
    article_title: str,
    newsletter_summary: str,
    article_content: str,        # ← renamed/new param
) -> dict:
    _update_email_log_sync(
        log_id, EmailStatus.RETRYING if self.request.retries > 0 else EmailStatus.PENDING
    )

    try:
        html = render_email_html(
            title=article_title,
            summary=newsletter_summary,
            content=article_content,     # ← full article goes here now
            subscriber_name=subscriber_name,
        )
        message_id = send_email(
            to_email=subscriber_email,
            to_name=subscriber_name,
            subject=f"📰 {article_title}",
            html_body=html,
        )
        _update_email_log_sync(log_id, EmailStatus.SENT, provider_message_id=message_id)
        return {"log_id": log_id, "subscriber_email": subscriber_email, "status": EmailStatus.SENT}

    except Exception as exc:
        logger.warning(f"Email to {subscriber_email} failed (attempt {self.request.retries + 1}): {exc}")
        _update_email_log_sync(log_id, EmailStatus.FAILED, error_message=str(exc))
        raise


# ---------------------------------------------------------------------------
# Task 3: Retry failed emails for a specific newsletter
# ---------------------------------------------------------------------------


@celery_app.task(name="email.retry_failed", queue="email_queue", bind=True)
def retry_failed_emails(self, newsletter_id: int) -> dict:
    with SyncSessionLocal() as db:
        result = db.execute(
            select(EmailLog).where(
                EmailLog.newsletter_id == newsletter_id,
                EmailLog.status == EmailStatus.FAILED,
            )
        )
        failed_logs = result.scalars().all()

        newsletter = db.get(Newsletter, newsletter_id)
        if newsletter is None:
            return {"retried": 0}

        article = newsletter.article
        article_title = article.title or "AI Newsletter"
        newsletter_summary = newsletter.content
        article_content = article.content

        requeued = 0
        for log in failed_logs:
            subscriber = db.get(Subscriber, log.subscriber_id)
            if subscriber is None:
                continue
            log.status = EmailStatus.PENDING
            db.commit()

            send_newsletter_to_subscriber.apply_async(
                kwargs={
                    "log_id": log.id,
                    "newsletter_id": newsletter_id,
                    "subscriber_id": subscriber.id,
                    "subscriber_name": subscriber.name,
                    "subscriber_email": subscriber.email,
                    "article_title": article_title,
                    "newsletter_summary": newsletter_summary,
                    "article_content": article_content,
                },
                queue="email_queue",
            )
            requeued += 1

    return {"newsletter_id": newsletter_id, "requeued": requeued}