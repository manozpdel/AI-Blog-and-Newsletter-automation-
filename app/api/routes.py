import csv
import io

from celery import chain
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.email_log import EmailLog, EmailStatus
from app.models.models import Article, ArticleStatus, Topic
from app.models.newsletter import Newsletter
from app.models.subscriber import Subscriber
from app.schemas.schemas import (
    ArticleOut,
    GenerateNewsletterResponse,
    NewsletterOut,
    TaskQueuedResponse,
    TaskStatusResponse,
    TopicCreate,
    TopicOut,
)
from app.schemas.subscriber import (
    CSVImportResult,
    EmailLogOut,
    EmailStatistics,
    SubscriberCreate,
    SubscriberOut,
    SubscriberUpdate,
)
from app.services.llm_service import generate_newsletter_summary
from app.tasks.content_tasks import (
    generate_article_task,
    generate_outline_task,
    generate_title_task,
)
from app.workers.celery_app import celery_app

router = APIRouter(dependencies=[Depends(rate_limit)])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------


@router.post("/topics", response_model=TopicOut, status_code=201, tags=["topics"])
async def create_topic(payload: TopicCreate, db: AsyncSession = Depends(get_db)):
    topic = Topic(name=payload.name, tone=payload.tone)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


@router.get("/topics", response_model=list[TopicOut], tags=["topics"])
async def list_topics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topic).order_by(Topic.id.desc()))
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


@router.post("/generate/{topic_id}", response_model=TaskQueuedResponse, tags=["generate"])
async def generate_article(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    article = Article(topic_id=topic.id, status=ArticleStatus.PENDING.value)
    db.add(article)
    await db.commit()
    await db.refresh(article)

    workflow = chain(
        generate_title_task.s(article.id, topic.id),
        generate_outline_task.s(),
        generate_article_task.s(),
    )
    async_result = workflow.apply_async()
    return TaskQueuedResponse(task_id=async_result.id, status="queued")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.get("/tasks/stats", tags=["tasks"])
async def get_task_stats():
    inspect = celery_app.control.inspect(timeout=2)
    try:
        active_raw    = inspect.active()    or {}
        scheduled_raw = inspect.scheduled() or {}
        reserved_raw  = inspect.reserved()  or {}
        active    = sum(len(v) for v in active_raw.values())
        scheduled = sum(len(v) for v in scheduled_raw.values())
        reserved  = sum(len(v) for v in reserved_raw.values())
    except Exception:
        active = scheduled = reserved = 0
    return {"active": active, "scheduled": scheduled, "reserved": reserved, "failed": 0}


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse, tags=["tasks"])
async def get_task_status(task_id: str):
    async_result = AsyncResult(task_id, app=celery_app)
    result_payload = None
    if async_result.state == "SUCCESS":
        result_payload = async_result.result
    elif async_result.state == "FAILURE":
        result_payload = str(async_result.result)
    return TaskStatusResponse(
        task_id=task_id,
        state=async_result.state,
        result=result_payload,
    )


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


@router.get("/articles", response_model=list[ArticleOut], tags=["articles"])
async def list_articles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).order_by(Article.id.desc()))
    return result.scalars().all()


@router.get("/articles/{article_id}", response_model=ArticleOut, tags=["articles"])
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


# ---------------------------------------------------------------------------
# Newsletters  (trigger email dispatch after saving — Task 5)
# ---------------------------------------------------------------------------


@router.post(
    "/generate-newsletter/{article_id}",
    response_model=GenerateNewsletterResponse,
    tags=["newsletters"],
)
async def generate_newsletter(article_id: int, db: AsyncSession = Depends(get_db)):
    from app.tasks.email_tasks import dispatch_newsletter_emails  # avoid circular import

    article = await db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if not article.content:
        raise HTTPException(status_code=400, detail="Article has no content yet")

    summary = await generate_newsletter_summary(
        title=article.title or "", article=article.content
    )
    newsletter = Newsletter(article_id=article.id, content=summary)
    db.add(newsletter)
    await db.commit()
    await db.refresh(newsletter)

    # Automatically kick off email delivery to all active subscribers
    dispatch_newsletter_emails.apply_async(
        args=[newsletter.id], queue="email_queue"
    )

    return GenerateNewsletterResponse(
        newsletter_id=newsletter.id, article_id=article.id, content=newsletter.content
    )


@router.get("/newsletters", response_model=list[NewsletterOut], tags=["newsletters"])
async def list_newsletters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Newsletter).order_by(Newsletter.id.desc()))
    return result.scalars().all()


@router.get("/newsletters/{newsletter_id}", response_model=NewsletterOut, tags=["newsletters"])
async def get_newsletter(newsletter_id: int, db: AsyncSession = Depends(get_db)):
    newsletter = await db.get(Newsletter, newsletter_id)
    if newsletter is None:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return newsletter


# ---------------------------------------------------------------------------
# Subscribers  (new in Task 5)
# ---------------------------------------------------------------------------


@router.post("/subscribers", response_model=SubscriberOut, status_code=201, tags=["subscribers"])
async def create_subscriber(payload: SubscriberCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(Subscriber).where(Subscriber.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already subscribed")
    subscriber = Subscriber(name=payload.name, email=payload.email, is_active=payload.is_active)
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)
    return subscriber


@router.get("/subscribers", response_model=list[SubscriberOut], tags=["subscribers"])
async def list_subscribers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subscriber).order_by(Subscriber.id.desc()))
    return result.scalars().all()


@router.get("/subscribers/{subscriber_id}", response_model=SubscriberOut, tags=["subscribers"])
async def get_subscriber(subscriber_id: int, db: AsyncSession = Depends(get_db)):
    subscriber = await db.get(Subscriber, subscriber_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return subscriber


@router.put("/subscribers/{subscriber_id}", response_model=SubscriberOut, tags=["subscribers"])
async def update_subscriber(
    subscriber_id: int, payload: SubscriberUpdate, db: AsyncSession = Depends(get_db)
):
    subscriber = await db.get(Subscriber, subscriber_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(subscriber, field, value)
    await db.commit()
    await db.refresh(subscriber)
    return subscriber


@router.delete("/subscribers/{subscriber_id}", status_code=204, tags=["subscribers"])
async def delete_subscriber(subscriber_id: int, db: AsyncSession = Depends(get_db)):
    subscriber = await db.get(Subscriber, subscriber_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    await db.delete(subscriber)
    await db.commit()


@router.post("/subscribers/import", response_model=CSVImportResult, tags=["subscribers"])
async def import_subscribers(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Accept a CSV with header: name,email
    Returns imported count, skipped (duplicate) count, and invalid rows.
    """
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    invalid_rows: list[str] = []

    for row in reader:
        name = (row.get("name") or "").strip()
        email = (row.get("email") or "").strip()

        if not name or not email or "@" not in email:
            invalid_rows.append(str(row))
            continue

        existing = await db.execute(select(Subscriber).where(Subscriber.email == email))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        db.add(Subscriber(name=name, email=email, is_active=True))
        imported += 1

    await db.commit()
    return CSVImportResult(imported=imported, skipped=skipped, invalid_rows=invalid_rows)


# ---------------------------------------------------------------------------
# Email logs + statistics  (new in Task 5)
# ---------------------------------------------------------------------------


@router.get("/email/logs", response_model=list[EmailLogOut], tags=["email"])
async def list_email_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailLog).order_by(EmailLog.id.desc()))
    return result.scalars().all()


@router.get("/email/logs/{newsletter_id}", response_model=list[EmailLogOut], tags=["email"])
async def get_email_logs_for_newsletter(
    newsletter_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(EmailLog)
        .where(EmailLog.newsletter_id == newsletter_id)
        .order_by(EmailLog.id.desc())
    )
    return result.scalars().all()


@router.get("/email/statistics", response_model=EmailStatistics, tags=["email"])
async def get_email_statistics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EmailLog))
    logs = result.scalars().all()

    total     = len(logs)
    delivered = sum(1 for l in logs if l.status == EmailStatus.SENT)
    failed    = sum(1 for l in logs if l.status == EmailStatus.FAILED)
    pending   = sum(1 for l in logs if l.status in (EmailStatus.PENDING, EmailStatus.RETRYING))
    success_pct = round((delivered / total * 100), 2) if total > 0 else 0.0

    return EmailStatistics(
        total_emails=total,
        successful_deliveries=delivered,
        failed_deliveries=failed,
        pending=pending,
        success_percentage=success_pct,
    )


@router.post("/email/retry/{newsletter_id}", tags=["email"])
async def retry_failed_emails(newsletter_id: int):
    from app.tasks.email_tasks import retry_failed_emails as retry_task
    result = retry_task.apply_async(args=[newsletter_id], queue="email_queue")
    return {"task_id": result.id, "status": "queued"}