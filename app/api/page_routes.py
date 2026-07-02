from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
page_router = APIRouter(include_in_schema=False)
_ENV = "development"


@page_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "page_title": "Dashboard",
            "page_icon": "bi bi-speedometer2",
            "page_subtitle": "System overview",
            "env": _ENV,
        },
    )


@page_router.get("/topics/page", response_class=HTMLResponse)
async def topics_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="topics.html",
        context={
            "active_page": "topics",
            "page_title": "Topics",
            "page_icon": "bi bi-tags",
            "page_subtitle": "Manage content topics",
            "env": _ENV,
        },
    )


@page_router.get("/generate/page", response_class=HTMLResponse)
async def generate_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="generate.html",
        context={
            "active_page": "generate",
            "page_title": "Generate Content",
            "page_icon": "bi bi-lightning-charge",
            "page_subtitle": "AI-powered article and newsletter generation",
            "env": _ENV,
        },
    )


@page_router.get("/articles/page", response_class=HTMLResponse)
async def articles_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="articles.html",
        context={
            "active_page": "articles",
            "page_title": "Articles",
            "page_icon": "bi bi-file-earmark-text",
            "page_subtitle": "Browse and read generated articles",
            "env": _ENV,
        },
    )


@page_router.get("/newsletters/page", response_class=HTMLResponse)
async def newsletters_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="newsletters.html",
        context={
            "active_page": "newsletters",
            "page_title": "Newsletters",
            "page_icon": "bi bi-envelope-paper",
            "page_subtitle": "Preview and download newsletters",
            "env": _ENV,
        },
    )


@page_router.get("/subscribers/page", response_class=HTMLResponse)
async def subscribers_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="subscribers.html",
        context={
            "active_page": "subscribers",
            "page_title": "Subscribers",
            "page_icon": "bi bi-people",
            "page_subtitle": "Manage newsletter subscribers",
            "env": _ENV,
        },
    )


@page_router.get("/tasks/page", response_class=HTMLResponse)
async def tasks_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="task_monitor.html",
        context={
            "active_page": "tasks",
            "page_title": "Task Monitor",
            "page_icon": "bi bi-activity",
            "page_subtitle": "Live Celery task and email delivery tracking",
            "env": _ENV,
        },
    )