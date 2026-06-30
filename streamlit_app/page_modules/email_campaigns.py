import requests
import streamlit as st

API_BASE = "http://api:8000"


def _get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _post(path):
    try:
        r = requests.post(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def render():
    st.title("📬 Email Campaigns")

    # ------------------------------------------------------------------
    # Stats overview
    # ------------------------------------------------------------------
    stats = _get("/email/statistics") or {}

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Sent",   stats.get("total_emails", 0))
    col2.metric("Delivered",    stats.get("successful_deliveries", 0))
    col3.metric("Failed",       stats.get("failed_deliveries", 0))
    col4.metric("Pending",      stats.get("pending", 0))
    col5.metric("Success Rate", f"{stats.get('success_percentage', 0):.1f}%")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Per-newsletter campaign breakdown
    # ------------------------------------------------------------------
    st.subheader("Campaigns by Newsletter")

    newsletters = _get("/newsletters") or []
    articles    = {a["id"]: a for a in (_get("/articles") or [])}

    if not newsletters:
        st.info("No newsletters generated yet.")
        return

    for n in newsletters:
        article_title = articles.get(n["article_id"], {}).get("title", "Untitled")
        logs = _get(f"/email/logs/{n['id']}") or []

        total     = len(logs)
        delivered = sum(1 for l in logs if l["status"] == "SENT")
        failed    = sum(1 for l in logs if l["status"] == "FAILED")
        pending   = sum(1 for l in logs if l["status"] in ("PENDING", "RETRYING"))

        label = f"📰 Newsletter #{n['id']} — {article_title}"
        with st.expander(label):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Recipients", total)
            m2.metric("Delivered",  delivered)
            m3.metric("Failed",     failed)
            m4.metric("Pending",    pending)

            if failed > 0:
                if st.button(f"🔁 Retry Failed ({failed})", key=f"retry_{n['id']}"):
                    result = _post(f"/email/retry/{n['id']}")
                    if result:
                        st.success(f"Re-queued {result.get('requeued', 0)} email(s).")
                        st.rerun()

            if logs:
                st.markdown("---")
                st.markdown("**Delivery log**")
                for log in logs:
                    icon = (
                        "✅" if log["status"] == "SENT"
                        else "❌" if log["status"] == "FAILED"
                        else "⏳"
                    )
                    st.markdown(
                        f"{icon} `{log['status']}` — "
                        f"subscriber #{log['subscriber_id']} "
                        f"{'· ' + log['error_message'] if log.get('error_message') else ''}"
                    )

    if st.button("🔄 Refresh"):
        st.rerun()