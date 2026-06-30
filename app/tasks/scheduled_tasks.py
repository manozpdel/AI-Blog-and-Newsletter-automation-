import asyncio
from datetime import date

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.graphs.content_graph import run_content_pipeline
from app.models.models import Article, ArticleStatus, Topic
from app.models.newsletter import Newsletter
from app.services.cache_service import is_already_generated_today, mark_generated_today
from app.workers.celery_app import celery_app


def _run_async(coro):
    return asyncio.run(coro)


async def _fetch_all_topics() -> list[Topic]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Topic))
        return list(result.scalars().all())


async def _store_article_and_newsletter(topic_id: int, pipeline_result: dict) -> int:
    async with AsyncSessionLocal() as db:
        article = Article(
            topic_id=topic_id,
            title=pipeline_result["title"],
            content=pipeline_result["article"],
            status=ArticleStatus.COMPLETED.value,
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)

        newsletter = Newsletter(article_id=article.id, content=pipeline_result["newsletter"])
        db.add(newsletter)
        await db.commit()
        await db.refresh(newsletter)

        return newsletter.id  # Return newsletter_id so we can dispatch emails


async def _process_topic(topic: Topic) -> dict:
    if await is_already_generated_today(topic.name):
        return {"topic_id": topic.id, "skipped": True, "reason": "already generated today"}

    pipeline_result = await run_content_pipeline(topic=topic.name, tone=topic.tone)
    newsletter_id = await _store_article_and_newsletter(topic.id, pipeline_result)
    await mark_generated_today(topic.name)

    return {"topic_id": topic.id, "newsletter_id": newsletter_id, "skipped": False}


@celery_app.task(name="content.daily_content_generation", bind=True)
def daily_content_generation(self) -> dict:
    """
    Celery Beat scheduled job.
    Generates article + newsletter per topic, then dispatches email delivery.
    """
    from app.tasks.email_tasks import dispatch_newsletter_emails  # avoid circular import

    topics = _run_async(_fetch_all_topics())

    results = []
    for topic in topics:
        try:
            result = _run_async(_process_topic(topic))
            results.append(result)

            # Trigger email dispatch for newly generated newsletters
            if not result.get("skipped") and result.get("newsletter_id"):
                dispatch_newsletter_emails.apply_async(
                    args=[result["newsletter_id"]],
                    queue="email_queue",
                )
        except Exception as exc:
            results.append({"topic_id": topic.id, "error": str(exc)})

    return {"date": date.today().isoformat(), "processed": results}