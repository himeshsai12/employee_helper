import uuid

import pandas as pd
import streamlit as st

from db import (
    get_connection,
    get_dashboard_stats,
    list_tickets,
    list_employees,
    list_assets,
    get_conversation,
    save_conversation,
    create_it_ticket
)

from graph import ask_helpdesk
from errors import database_error_message, helpdesk_error_message


st.set_page_config(
    page_title="NexaDesk AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- CUSTOM DESIGN ----------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: linear-gradient(
        135deg, #f5f7ff 0%, #faf9ff 55%, #eef7ff 100%
    );
}

.block-container {
    padding-top: 1.5rem;
    max-width: 1450px;
}

.hero {
    padding: 30px;
    border-radius: 24px;
    background: linear-gradient(
        115deg, #111b3c, #253e78 62%, #6b5bd2
    );
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 16px 40px #1c2b551c;
}

.hero h1 {
    font-family: 'Manrope', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    margin: 0 0 8px 0;
    letter-spacing: -1px;
}

.hero p {
    color: #e2e8ff;
    margin: 0;
    font-size: 1rem;
}

.metric-card {
    background: rgba(255,255,255,.92);
    border: 1px solid #e7eaf4;
    border-radius: 18px;
    padding: 20px;
    box-shadow: 0 8px 25px #1a24500b;
    min-height: 120px;
}

.metric-label {
    font-size: .82rem;
    color: #68738c;
    font-weight: 600;
}

.metric-value {
    font-family: 'Manrope', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: #182448;
    margin-top: 8px;
}

.metric-hint {
    color: #7a86a0;
    font-size: .78rem;
    margin-top: 5px;
}

.section-title {
    font-family: 'Manrope', sans-serif;
    color: #182448;
    font-size: 1.25rem;
    font-weight: 800;
    margin: 8px 0 14px;
}

.stButton > button {
    border-radius: 11px;
    font-weight: 600;
    min-height: 2.6rem;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #5146d8, #7167e8);
    color: white;
    border: none;
}

div[data-testid="stChatMessage"] {
    border-radius: 16px;
    border: 1px solid #e8ebf5;
    background: white;
}

div[data-testid="stTabs"] button {
    font-weight: 700;
}

</style>
""", unsafe_allow_html=True)


# ---------------- SESSION STATE ----------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "show_ticket_form" not in st.session_state:
    st.session_state.show_ticket_form = False


# ---------------- HELPER FUNCTIONS ----------------

def show_header(title, subtitle):
    st.markdown(
        f"""
        <div class="hero">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_metric(label, value, hint):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def to_dataframe(rows):
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def filter_dataframe(df, search):
    if df.empty or not search:
        return df

    mask = df.astype(str).apply(
        lambda column: column.str.contains(
            search,
            case=False,
            na=False,
            regex=False
        )
    ).any(axis=1)

    return df[mask]


def open_ticket_form():
    st.session_state.show_ticket_form = True
    st.session_state.workspace = "Tickets"


def load_saved_chat():
    try:
        history = get_conversation(st.session_state.session_id)
        messages = []
        for row in history:
            messages.extend([
                {"role": "user", "content": row["user_message"]},
                {"role": "assistant", "content": row["assistant_message"]},
            ])
        if history:
            st.session_state.messages = messages
            st.session_state.workspace = "AI Helpdesk"
            st.session_state.notice = ("success", "Previous conversation loaded.")
        else:
            st.session_state.notice = ("info", "No saved conversation found.")
    except Exception as error:
        st.session_state.notice = (
            "error", "Could not load history. " + database_error_message(error)
        )


def clear_chat():
    st.session_state.messages = []
    st.session_state.pending_question = None


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## ✦ NexaDesk AI")
    st.caption("ENTERPRISE SUPPORT PLATFORM")
    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Overview",
            "AI Helpdesk",
            "Tickets",
            "Employees",
            "Assets"
        ],
        key="workspace"
    )

    st.divider()
    st.markdown("### Quick actions")

    st.button("＋ New IT ticket", width="stretch", on_click=open_ticket_form)

    st.button("↻ Load saved chat", width="stretch", on_click=load_saved_chat)

    st.button("Clear current chat", width="stretch", on_click=clear_chat)

    st.divider()

    if st.button("Test MySQL connection", width="stretch"):
        try:
            connection = get_connection()
            connection.close()
            st.success("MySQL connected successfully.")
        except Exception as error:
            st.error(database_error_message(error))

    st.divider()
    st.caption("Python · Streamlit · LangChain · Groq · MySQL")
    st.caption("Educational project using fictional demo records.")


notice = st.session_state.pop("notice", None)
if notice:
    kind, message = notice
    getattr(st, kind)(message)


# ---------------- OVERVIEW ----------------

if page == "Overview":

    show_header(
        "Your support command center",
        "A smarter workplace helpdesk for IT tickets, employee services, and company assets."
    )

    try:
        stats = get_dashboard_stats()

        columns = st.columns(4)

        with columns[0]:
            show_metric(
                "TOTAL TICKETS",
                stats["total_tickets"],
                "All recorded requests"
            )

        with columns[1]:
            show_metric(
                "OPEN TICKETS",
                stats["open_tickets"],
                "Open or in progress"
            )

        with columns[2]:
            show_metric(
                "EMPLOYEES",
                stats["employees"],
                "Registered employees"
            )

        with columns[3]:
            show_metric(
                "COMPANY ASSETS",
                stats["assets"],
                "Tracked equipment"
            )

        st.write("")

        left, right = st.columns([1.4, 1])

        tickets = list_tickets()

        with left:
            st.markdown(
                '<div class="section-title">Recent support tickets</div>',
                unsafe_allow_html=True
            )

            st.dataframe(
                to_dataframe(tickets).head(8),
                width="stretch",
                hide_index=True
            )

        with right:
            st.markdown(
                '<div class="section-title">Ticket status snapshot</div>',
                unsafe_allow_html=True
            )

            df = to_dataframe(tickets)

            if not df.empty:
                counts = (
                    df["status"]
                    .value_counts()
                    .rename_axis("Status")
                    .reset_index(name="Tickets")
                )

                st.bar_chart(
                    counts.set_index("Status")
                )

            st.info(
                "Open AI Helpdesk to check tickets, "
                "employee leave, assets, or create a request."
            )

    except Exception as error:
        st.error(
            "Unable to load dashboard. " + database_error_message(error)
        )


# ---------------- AI HELPDESK ----------------

elif page == "AI Helpdesk":

    show_header(
        "AI Helpdesk Assistant",
        "Ask questions in plain English and get answers from company database tools."
    )

    st.button(
        "Create an IT ticket", key="chat_create_ticket",
        on_click=open_ticket_form
    )

    st.markdown(
        '<div class="section-title">Try a quick question</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Check ticket T101", width="stretch"):
            st.session_state.pending_question = (
                "What is the status of ticket T101?"
            )

    with c2:
        if st.button("Check leave for E101", width="stretch"):
            st.session_state.pending_question = (
                "What is the leave balance for employee E101?"
            )

    with c3:
        if st.button("Assets for E102", width="stretch"):
            st.session_state.pending_question = (
                "Show the company assets assigned to employee E102."
            )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("failed") and message["role"] == "assistant":
                st.error(message["content"])
            else:
                st.markdown(message["content"])

    question = st.chat_input(
        "Ask about tickets, leave, assets, or IT support..."
    )

    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None

    if question:

        failed = False
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):

            with st.spinner("Checking helpdesk information..."):
                try:
                    answer = ask_helpdesk(
                        question,
                        history=st.session_state.messages[:-1]
                    )

                except Exception as error:
                    failed = True
                    st.session_state.messages[-1]["failed"] = True
                    answer = helpdesk_error_message(error)

            if failed:
                st.error(answer)
            else:
                st.markdown(answer)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "failed": failed
        })

        if not failed:
            try:
                save_conversation(
                    st.session_state.session_id,
                    question,
                    answer
                )

            except Exception as error:
                st.warning(
                    "Answer displayed, but history could not be saved. "
                    + database_error_message(error)
                )


# ---------------- TICKET MANAGEMENT ----------------

elif page == "Tickets":

    show_header(
        "Ticket management",
        "Create, search, and review company IT support requests."
    )

    if not st.session_state.show_ticket_form:
        st.button(
            "New IT ticket", key="tickets_create_ticket", type="primary",
            on_click=open_ticket_form
        )

    if st.session_state.show_ticket_form:

        st.markdown(
            '<div class="section-title">Create a new IT ticket</div>',
            unsafe_allow_html=True
        )

        try:
            employees = list_employees()
        except Exception as error:
            employees = []
            st.error("Could not load employees. " + database_error_message(error))

        employee_labels = {
            employee["employee_id"]: f"{employee['employee_id']} - {employee['name']}"
            for employee in employees
        }
        if not employees:
            st.warning("A registered employee is required before creating a ticket.")

        with st.form("create_ticket_form"):

            employee_id = st.selectbox(
                "Employee ID",
                options=list(employee_labels),
                format_func=employee_labels.get,
                key="ticket_employee"
            )

            issue = st.text_area(
                "Describe the issue",
                placeholder="VPN disconnects every few minutes",
                max_chars=240,
                key="ticket_issue"
            )

            submitted = st.form_submit_button(
                "Create ticket",
                type="primary",
                disabled=not employees
            )

        if submitted:

            if not employee_id or not issue.strip():
                st.warning(
                    "Describe the issue in the box above, then click Create ticket."
                )

            else:
                try:
                    result = create_it_ticket(
                        employee_id,
                        issue
                    )

                    if result:
                        st.session_state.notice = ("success",
                            f"Ticket created: {result['ticket_id']} "
                            f"· Status: {result['status']}"
                        )

                        st.session_state.show_ticket_form = False
                        st.session_state.ticket_search = ""
                        st.session_state.ticket_status_filter = "All"
                        st.rerun()

                    else:
                        st.error(
                            "Employee ID not found. Check the ID and retry."
                        )

                except Exception as error:
                    if isinstance(error, ValueError):
                        st.warning(str(error))
                    else:
                        st.error("Could not create ticket. " + database_error_message(error))

    st.divider()

    c1, c2 = st.columns([1.5, 1])

    with c1:
        search = st.text_input(
            "Search ticket or employee",
            placeholder="T101 or E101",
            key="ticket_search"
        )

    with c2:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Open", "In Progress", "Resolved"],
            key="ticket_status_filter"
        )

    try:
        df = to_dataframe(list_tickets())
        df = filter_dataframe(df, search)

        if not df.empty and status_filter != "All":
            df = df[
                df["status"].str.lower()
                == status_filter.lower()
            ]

        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )

    except Exception as error:
        st.error("Could not load tickets. " + database_error_message(error))


# ---------------- EMPLOYEE DIRECTORY ----------------

elif page == "Employees":

    show_header(
        "Employee directory",
        "Search employee records and review available leave balances."
    )

    search = st.text_input(
        "Search by employee ID, name, email, or department"
    )

    try:
        df = to_dataframe(list_employees())
        df = filter_dataframe(df, search)

        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )

    except Exception as error:
        st.error("Could not load employees. " + database_error_message(error))


# ---------------- ASSET INVENTORY ----------------

elif page == "Assets":

    show_header(
        "Asset inventory",
        "View assigned company equipment and its current status."
    )

    search = st.text_input(
        "Search by employee, asset name, type, or status"
    )

    try:
        df = to_dataframe(list_assets())
        df = filter_dataframe(df, search)

        st.dataframe(
            df,
            width="stretch",
            hide_index=True
        )

    except Exception as error:
        st.error("Could not load assets. " + database_error_message(error))
