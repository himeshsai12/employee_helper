import os
import uuid

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "tcs"),
        connection_timeout=5
    )


def _open_cursor(dictionary=False):
    db = get_connection()
    try:
        return db, db.cursor(dictionary=dictionary)
    except Exception:
        db.close()
        raise


def _close_cursor(db, cursor):
    try:
        cursor.close()
    finally:
        db.close()


def fetch_all(query, params=()):
    db, cursor = _open_cursor(dictionary=True)

    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        _close_cursor(db, cursor)


def get_ticket_status(ticket_id):
    rows = fetch_all(
        """
        SELECT ticket_id, employee_id, issue, status, created_at
        FROM tickets
        WHERE ticket_id = %s
        """,
        (ticket_id.strip().upper(),)
    )

    return rows[0] if rows else None


def get_leave_balance(employee_id):
    rows = fetch_all(
        """
        SELECT employee_id, name, department, leave_balance
        FROM employees
        WHERE employee_id = %s
        """,
        (employee_id.strip().upper(),)
    )

    return rows[0] if rows else None


def get_asset_details(employee_id):
    return fetch_all(
        """
        SELECT asset_id, employee_id, asset_type,
               asset_name, status
        FROM assets
        WHERE employee_id = %s
        """,
        (employee_id.strip().upper(),)
    )


def create_it_ticket(employee_id, issue):
    if not isinstance(employee_id, str) or not employee_id.strip():
        raise ValueError("Employee ID is required.")
    if len(employee_id.strip()) > 20:
        raise ValueError("Employee ID must contain at most 20 characters.")
    if not isinstance(issue, str) or not 1 <= len(issue.strip()) <= 240:
        raise ValueError("Issue description must contain 1 to 240 characters.")

    employee_id = employee_id.strip().upper()
    issue = issue.strip()
    db, cursor = _open_cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT employee_id FROM employees WHERE employee_id = %s",
            (employee_id,)
        )

        if not cursor.fetchone():
            return None

        # A UUID-based ID avoids collisions from COUNT(*) numbering.
        ticket_id = "T" + uuid.uuid4().hex[:10].upper()

        cursor.execute(
            """
            INSERT INTO tickets
            (ticket_id, employee_id, issue, status)
            VALUES (%s, %s, %s, %s)
            """,
            (ticket_id, employee_id, issue, "Open")
        )

        db.commit()

        return {
            "ticket_id": ticket_id,
            "employee_id": employee_id,
            "issue": issue,
            "status": "Open"
        }

    except Exception:
        db.rollback()
        raise

    finally:
        _close_cursor(db, cursor)


def save_conversation(session_id, user_message, assistant_message):
    db, cursor = _open_cursor()

    try:
        cursor.execute(
            """
            INSERT INTO conversations
            (session_id, user_message, assistant_message)
            VALUES (%s, %s, %s)
            """,
            (session_id, user_message, assistant_message)
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        _close_cursor(db, cursor)


def get_conversation(session_id):
    return fetch_all(
        """
        SELECT user_message, assistant_message, created_at
        FROM conversations
        WHERE session_id = %s
        ORDER BY id
        """,
        (session_id,)
    )


def list_tickets():
    return fetch_all(
        """
        SELECT t.ticket_id, t.employee_id,
               e.name AS employee_name,
               t.issue, t.status, t.created_at
        FROM tickets t
        LEFT JOIN employees e
            ON e.employee_id = t.employee_id
        ORDER BY t.created_at DESC
        """
    )


def list_employees():
    return fetch_all(
        """
        SELECT employee_id, name, email,
               department, leave_balance
        FROM employees
        ORDER BY employee_id
        """
    )


def list_assets():
    return fetch_all(
        """
        SELECT a.asset_id, a.employee_id,
               e.name AS employee_name,
               a.asset_type, a.asset_name, a.status
        FROM assets a
        LEFT JOIN employees e
            ON e.employee_id = a.employee_id
        ORDER BY a.asset_id
        """
    )


def get_dashboard_stats():
    db, cursor = _open_cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) AS total FROM tickets")
        total_tickets = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM tickets
            WHERE status IN ('Open', 'In Progress')
            """
        )
        open_tickets = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM employees")
        employees = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM assets")
        assets = cursor.fetchone()["total"]

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "employees": employees,
            "assets": assets
        }

    finally:
        _close_cursor(db, cursor)
