import csv
import io

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


def _post(path, payload=None, files=None):
    try:
        if files:
            r = requests.post(f"{API_BASE}{path}", files=files, timeout=30)
        else:
            r = requests.post(f"{API_BASE}{path}", json=payload or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _put(path, payload):
    try:
        r = requests.put(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def _delete(path):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"API error: {e}")
        return False


def render():
    st.title("👥 Subscribers")

    tab1, tab2, tab3 = st.tabs(["All Subscribers", "Add Subscriber", "Import CSV"])

    # ------------------------------------------------------------------
    # Tab 1: List + edit + delete + toggle
    # ------------------------------------------------------------------
    with tab1:
        subscribers = _get("/subscribers") or []

        if not subscribers:
            st.info("No subscribers yet. Add one or import a CSV.")
        else:
            st.markdown(f"**{len(subscribers)} subscriber(s)**")
            st.markdown("---")

            for s in subscribers:
                status_icon = "🟢" if s["is_active"] else "🔴"
                with st.expander(f"{status_icon} #{s['id']} — {s['name']} ({s['email']})"):
                    col1, col2, col3, col4 = st.columns([3, 3, 2, 2])

                    with col1:
                        new_name = st.text_input("Name", value=s["name"], key=f"name_{s['id']}")
                    with col2:
                        new_email = st.text_input("Email", value=s["email"], key=f"email_{s['id']}")
                    with col3:
                        new_active = st.checkbox(
                            "Active", value=s["is_active"], key=f"active_{s['id']}"
                        )
                    with col4:
                        st.write("")
                        st.write("")
                        if st.button("💾 Save", key=f"save_{s['id']}"):
                            result = _put(
                                f"/subscribers/{s['id']}",
                                {"name": new_name, "email": new_email, "is_active": new_active},
                            )
                            if result:
                                st.success("Updated!")
                                st.rerun()

                        if st.button("🗑️ Delete", key=f"del_{s['id']}"):
                            if _delete(f"/subscribers/{s['id']}"):
                                st.success("Deleted.")
                                st.rerun()

        if st.button("🔄 Refresh"):
            st.rerun()

    # ------------------------------------------------------------------
    # Tab 2: Add single subscriber
    # ------------------------------------------------------------------
    with tab2:
        st.subheader("Add a subscriber")
        with st.form("add_subscriber_form"):
            name = st.text_input("Name", placeholder="Jane Doe")
            email = st.text_input("Email", placeholder="jane@example.com")
            is_active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Add Subscriber")

        if submitted:
            if not name.strip() or not email.strip():
                st.warning("Name and email are required.")
            else:
                result = _post("/subscribers", {"name": name, "email": email, "is_active": is_active})
                if result:
                    st.success(f"✅ Subscriber added — ID: {result['id']}")

    # ------------------------------------------------------------------
    # Tab 3: CSV import
    # ------------------------------------------------------------------
    with tab3:
        st.subheader("Import subscribers from CSV")
        st.markdown(
            "CSV must have a header row: `name,email`\n\n"
            "Example:\n```\nname,email\nJane Doe,jane@example.com\nJohn Smith,john@example.com\n```"
        )

        uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
        if uploaded and st.button("📥 Import"):
            files = {"file": (uploaded.name, uploaded.getvalue(), "text/csv")}
            result = _post("/subscribers/import", files=files)
            if result:
                st.success(
                    f"✅ Imported: **{result['imported']}** | "
                    f"Skipped: **{result['skipped']}**"
                )
                if result.get("invalid_rows"):
                    st.warning("Invalid rows:")
                    for row in result["invalid_rows"]:
                        st.code(row)