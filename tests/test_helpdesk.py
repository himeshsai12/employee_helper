"""Regression checks. All model calls and database writes use test doubles."""

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import httpx
from mysql.connector import Error as DatabaseError
from groq import AuthenticationError, RateLimitError
from streamlit.testing.v1 import AppTest

import db
import graph
import tools
from errors import database_error_message, helpdesk_error_message


APP = str(Path(__file__).resolve().parents[1] / "app.py")


def provider_error(error_type, status, code=None):
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return error_type(
        "Provider details containing gsk_test_secret",
        response=response,
        body={"code": code},
    )


class AgentTests(unittest.TestCase):
    def test_followup_receives_previous_issue(self):
        history = [
            {"role": "user", "content": "My VPN disconnects."},
            {"role": "assistant", "content": "What is your employee ID?"},
        ]
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [SimpleNamespace(content="Ticket created.")]}
        with patch.object(graph, "build_agent", return_value=agent):
            self.assertEqual(graph.ask_helpdesk(" E_TEST ", history), "Ticket created.")
        sent = agent.invoke.call_args.args[0]["messages"]
        self.assertEqual(sent, history + [{"role": "user", "content": "E_TEST"}])
        self.assertEqual(len(history), 2)

    def test_failed_turns_are_excluded_from_model_context(self):
        history = [
            {"role": "user", "content": "Failed question", "failed": True},
            {"role": "assistant", "content": "Billing error", "failed": True},
            {"role": "user", "content": "My VPN disconnects."},
            {"role": "assistant", "content": "What is your employee ID?"},
        ]
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [SimpleNamespace(content="OK")]}
        with patch.object(graph, "build_agent", return_value=agent):
            graph.ask_helpdesk("E_TEST", history)
        sent = agent.invoke.call_args.args[0]["messages"]
        self.assertEqual(len(sent), 3)
        self.assertNotIn("Billing error", str(sent))

    def test_empty_question_does_not_create_agent(self):
        with patch.object(graph, "build_agent") as build:
            self.assertEqual(graph.ask_helpdesk("  "), "Please enter your helpdesk question.")
        build.assert_not_called()

    def test_nontext_response_blocks_are_not_displayed(self):
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [SimpleNamespace(content=[
            {"type": "reasoning", "reasoning": "Internal data"},
            {"type": "text", "text": "Visible answer"},
        ])]}
        with patch.object(graph, "build_agent", return_value=agent):
            self.assertEqual(graph.ask_helpdesk("Hello"), "Visible answer")

    def test_missing_key_is_reported_before_client_construction(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}), patch.object(graph, "ChatGroq") as model:
            with self.assertRaisesRegex(ValueError, "GROQ_API_KEY is missing"):
                graph.build_agent()
        model.assert_not_called()


class ConnectionSettingsTests(unittest.TestCase):
    def test_local_connection_uses_supplied_settings(self):
        settings = {
            "DB_HOST": "localhost", "DB_PORT": "3307", "DB_USER": "test-user",
            "DB_PASSWORD": "test-password", "DB_NAME": "test-db",
        }
        with patch.object(db.mysql.connector, "connect") as connect:
            result = db.get_connection(settings)
        self.assertIs(result, connect.return_value)
        self.assertEqual(connect.call_args.kwargs["port"], 3307)
        self.assertEqual(connect.call_args.kwargs["database"], "test-db")
        self.assertNotIn("ssl_ca", connect.call_args.kwargs)

    def test_provider_ca_enables_certificate_and_hostname_verification(self):
        certificate = "-----BEGIN CERTIFICATE-----\nTEST-CA\n-----END CERTIFICATE-----"
        settings = {"DB_HOST": "db.example.invalid", "DB_SSL_CA_PEM": certificate}
        ca_paths = []

        def connect(**options):
            ca_path = Path(options["ssl_ca"])
            ca_paths.append(ca_path)
            self.assertEqual(ca_path.read_text(encoding="utf-8"), certificate)
            self.assertTrue(options["ssl_verify_cert"])
            self.assertTrue(options["ssl_verify_identity"])
            return "test-connection"

        with patch.object(db.mysql.connector, "connect", side_effect=connect):
            self.assertEqual(db.get_connection(settings), "test-connection")
        self.assertFalse(ca_paths[0].exists())

    def test_failed_tls_connection_removes_temporary_certificate(self):
        ca_paths = []

        def connect(**options):
            ca_paths.append(Path(options["ssl_ca"]))
            raise DatabaseError("Synthetic TLS failure")

        with patch.object(db.mysql.connector, "connect", side_effect=connect):
            with self.assertRaises(DatabaseError):
                db.get_connection({"DB_SSL_CA_PEM": "Synthetic CA"})
        self.assertFalse(ca_paths[0].exists())


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.cursor.fetchone.return_value = {"employee_id": "E_TEST"}
        self.patch = patch.object(db, "get_connection", return_value=self.connection)
        self.connect = self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_create_ticket_normalizes_inputs_and_commits(self):
        ticket = db.create_it_ticket(" e_test ", " VPN disconnects ")
        self.assertEqual(ticket["employee_id"], "E_TEST")
        self.assertEqual(ticket["issue"], "VPN disconnects")
        self.assertEqual(ticket["status"], "Open")
        self.assertLessEqual(len(ticket["ticket_id"]), 30)
        inserted = self.cursor.execute.call_args.args[1]
        self.assertEqual(inserted, (ticket["ticket_id"], "E_TEST", "VPN disconnects", "Open"))
        self.connection.commit.assert_called_once()
        self.connection.close.assert_called_once()

    def test_invalid_inputs_are_rejected_before_opening_database(self):
        for employee, issue in [("", "VPN"), (" " * 2, "VPN"), ("X" * 21, "VPN"), ("E_TEST", " "), ("E_TEST", "X" * 241)]:
            with self.subTest(employee_length=len(employee), issue_length=len(issue)):
                with self.assertRaises(ValueError):
                    db.create_it_ticket(employee, issue)
        self.connect.assert_not_called()

    def test_unknown_employee_does_not_insert(self):
        self.cursor.fetchone.return_value = None
        self.assertIsNone(db.create_it_ticket("MISSING", "VPN disconnects"))
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_insert_failure_rolls_back_and_closes_resources(self):
        self.cursor.execute.side_effect = [None, DatabaseError("Synthetic insert failure")]
        with self.assertRaises(DatabaseError):
            db.create_it_ticket("E_TEST", "VPN disconnects")
        self.connection.rollback.assert_called_once()
        self.cursor.close.assert_called_once()
        self.connection.close.assert_called_once()

    def test_failed_cursor_creation_does_not_leak_connection(self):
        self.connection.cursor.side_effect = DatabaseError("Synthetic cursor failure")
        with self.assertRaises(DatabaseError):
            db.list_tickets()
        self.connection.close.assert_called_once()

    def test_failed_cursor_close_still_closes_connection(self):
        self.cursor.close.side_effect = DatabaseError("Synthetic cursor close failure")
        with self.assertRaises(DatabaseError):
            db.list_tickets()
        self.connection.close.assert_called_once()

    def test_failed_history_save_rolls_back(self):
        self.cursor.execute.side_effect = DatabaseError("Synthetic history save failure")
        with self.assertRaises(DatabaseError):
            db.save_conversation("test-session", "Hello", "Hi")
        self.connection.rollback.assert_called_once()
        self.connection.close.assert_called_once()

    def test_tool_returns_input_validation_message(self):
        answer = tools.create_it_ticket_tool.invoke({"employee_id": "", "issue": "VPN disconnects"})
        self.assertIn("Employee ID is required", answer)
        self.connect.assert_not_called()


class ErrorMessageTests(unittest.TestCase):
    def test_local_database_failure_explains_cloud_configuration(self):
        error = DatabaseError("Connection failed; private details", errno=2003)
        with patch.dict("os.environ", {"DB_HOST": "localhost"}):
            message = database_error_message(error)
        self.assertIn("Streamlit Cloud", message)
        self.assertIn("DB_HOST", message)
        self.assertIn("hosted MySQL", message)
        self.assertNotIn("private details", message)

    def test_remote_database_failure_has_network_guidance(self):
        with patch.dict("os.environ", {"DB_HOST": "db.example.invalid"}):
            message = database_error_message(DatabaseError("Connection refused", errno=2003))
        self.assertIn("DB_PORT", message)
        self.assertIn("network access", message)
        self.assertNotIn("db.example.invalid", message)

    def test_agent_database_failure_has_database_guidance(self):
        with patch.dict("os.environ", {"DB_HOST": "localhost"}):
            message = helpdesk_error_message(DatabaseError("Connection refused", errno=2003))
        self.assertIn("DB_HOST", message)

    def test_request_limit_has_actionable_message(self):
        message = helpdesk_error_message(provider_error(RateLimitError, 429, "rate_limit_exceeded"))
        self.assertIn("Groq request limit", message)
        self.assertIn("Tickets", message)
        self.assertNotIn("gsk_test_secret", message)

    def test_missing_groq_key_has_actionable_message(self):
        message = helpdesk_error_message(ValueError("GROQ_API_KEY is missing. Add your key to the .env file."))
        self.assertIn("GROQ_API_KEY", message)

    def test_authentication_failure_does_not_expose_provider_details(self):
        message = helpdesk_error_message(provider_error(AuthenticationError, 401, "invalid_api_key"))
        self.assertIn("GROQ_API_KEY", message)
        self.assertNotIn("gsk_test_secret", message)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tickets = [
            {"ticket_id": "T_TEST1", "employee_id": "E_TEST", "employee_name": "Test Employee", "issue": "VPN [urgent]", "status": "Open", "created_at": "2026-01-01"},
            {"ticket_id": "T_TEST2", "employee_id": "E_OTHER", "employee_name": "Other Employee", "issue": "Printer", "status": "Resolved", "created_at": "2026-01-02"},
        ]
        for name, result in {
            "get_dashboard_stats": {"total_tickets": 2, "open_tickets": 1, "employees": 1, "assets": 1},
            "list_tickets": self.tickets,
            "list_employees": [{"employee_id": "E_TEST", "name": "Test Employee", "leave_balance": 5}],
            "list_assets": [{"asset_id": "A_TEST", "employee_id": "E_TEST", "asset_name": "Test laptop", "status": "Assigned"}],
        }.items():
            self.stack.enter_context(patch.object(db, name, return_value=result))
        self.create = self.stack.enter_context(patch.object(db, "create_it_ticket", side_effect=self.create_ticket))
        self.save = self.stack.enter_context(patch.object(db, "save_conversation"))
        self.history = self.stack.enter_context(patch.object(db, "get_conversation", return_value=[]))
        self.ask = self.stack.enter_context(patch.object(graph, "ask_helpdesk", return_value="What is your employee ID?"))
        self.at = AppTest.from_file(APP, default_timeout=30).run()

    def create_ticket(self, employee_id, issue):
        ticket = {"ticket_id": "T_CREATED", "employee_id": employee_id.strip().upper(), "issue": issue.strip(), "status": "Open"}
        self.tickets.append({**ticket, "employee_name": "Test Employee", "created_at": "2026-01-03"})
        return ticket

    def click(self, label):
        next(button for button in self.at.button if button.label == label).click().run()

    def check_page(self):
        self.assertFalse(self.at.exception, [error.message for error in self.at.exception])

    def fill_ticket(self, employee="E_TEST", issue="Synthetic VPN issue"):
        self.at.selectbox(key="ticket_employee").set_value(employee)
        self.at.text_area(key="ticket_issue").set_value(issue)
        self.click("Create ticket")

    def test_all_pages_load(self):
        for page in ["Overview", "AI Helpdesk", "Tickets", "Employees", "Assets"]:
            self.at.sidebar.radio[0].set_value(page).run()
            self.check_page()
            self.assertFalse(self.at.error)

    def test_dashboard_database_failure_explains_required_cloud_host(self):
        with patch.object(db, "get_dashboard_stats", side_effect=DatabaseError("Connection refused", errno=2003)), patch.dict("os.environ", {"DB_HOST": "localhost"}):
            self.at.run()
        self.check_page()
        self.assertIn("Streamlit Cloud", self.at.error[0].value)
        self.assertIn("DB_HOST", self.at.error[0].value)

    def test_quick_action_creates_ticket_without_jumping_back(self):
        self.at.sidebar.button[0].click().run()
        self.assertEqual(self.at.sidebar.radio[0].value, "Tickets")
        self.fill_ticket()
        self.check_page()
        self.create.assert_called_once_with("E_TEST", "Synthetic VPN issue")
        self.assertEqual(self.at.sidebar.radio[0].value, "Tickets")
        self.assertTrue(any("T_CREATED" in notice.value for notice in self.at.success))
        self.assertIn("T_CREATED", self.at.dataframe[0].value["ticket_id"].tolist())

    def test_empty_ticket_form_preserves_page_and_shows_validation(self):
        self.at.sidebar.button[0].click().run()
        self.click("Create ticket")
        self.check_page()
        self.create.assert_not_called()
        self.assertEqual(self.at.sidebar.radio[0].value, "Tickets")
        self.assertTrue(self.at.warning)
        self.assertEqual(len(self.at.text_area), 1)

    def test_employee_deleted_during_submission_displays_error(self):
        self.create.side_effect = None
        self.create.return_value = None
        self.at.sidebar.button[0].click().run()
        self.fill_ticket()
        self.check_page()
        self.assertIn("Employee ID not found", self.at.error[0].value)

    def test_ticket_page_has_its_own_create_button(self):
        self.at.sidebar.radio[0].set_value("Tickets").run()
        self.click("New IT ticket")
        self.assertEqual(len(self.at.text_area), 1)
        self.check_page()

    def test_chat_can_open_ticket_form_without_model_call(self):
        self.at.sidebar.radio[0].set_value("AI Helpdesk").run()
        self.click("Create an IT ticket")
        self.assertEqual(self.at.sidebar.radio[0].value, "Tickets")
        self.assertEqual(len(self.at.text_area), 1)
        self.ask.assert_not_called()

    def test_ticket_creation_clears_filters_that_would_hide_new_ticket(self):
        self.at.sidebar.radio[0].set_value("Tickets").run()
        self.at.text_input(key="ticket_search").set_value("T_TEST2").run()
        self.at.selectbox(key="ticket_status_filter").set_value("Resolved").run()
        self.click("New IT ticket")
        self.fill_ticket()
        self.check_page()
        self.assertEqual(self.at.text_input(key="ticket_search").value, "")
        self.assertEqual(self.at.selectbox(key="ticket_status_filter").value, "All")
        self.assertIn("T_CREATED", self.at.dataframe[0].value["ticket_id"].tolist())

    def test_ticket_search_is_literal_and_status_filter_works(self):
        self.at.sidebar.radio[0].set_value("Tickets").run()
        self.at.text_input[0].set_value("[").run()
        self.assertEqual(self.at.dataframe[0].value["ticket_id"].tolist(), ["T_TEST1"])
        self.at.text_input[0].set_value("").run()
        self.at.selectbox[0].set_value("Resolved").run()
        self.assertEqual(self.at.dataframe[0].value["ticket_id"].tolist(), ["T_TEST2"])
        self.check_page()

    def test_chat_followup_passes_history_and_saves_success(self):
        self.at.sidebar.radio[0].set_value("AI Helpdesk").run()
        self.at.chat_input[0].set_value("My VPN disconnects.").run()
        self.at.chat_input[0].set_value("E_TEST").run()
        self.check_page()
        self.assertEqual(self.ask.call_args.kwargs["history"][0]["content"], "My VPN disconnects.")
        self.assertEqual(len(self.ask.call_args.kwargs["history"]), 2)
        self.assertEqual(self.save.call_count, 2)

    def test_rate_limit_error_is_safe_and_not_saved_as_success(self):
        self.ask.side_effect = provider_error(RateLimitError, 429, "rate_limit_exceeded")
        self.at.sidebar.radio[0].set_value("AI Helpdesk").run()
        self.at.chat_input[0].set_value("Hello").run()
        self.check_page()
        self.save.assert_not_called()
        self.assertIn("Groq request limit", self.at.error[0].value)
        self.assertNotIn("gsk_test_secret", self.at.error[0].value)
        self.assertTrue(all(message["failed"] for message in self.at.session_state.messages))
        self.at.run()
        self.assertIn("Groq request limit", self.at.error[0].value)

    def test_loading_saved_chat_navigates_to_helpdesk(self):
        self.history.return_value = [{"user_message": "Saved question", "assistant_message": "Saved answer"}]
        self.at.sidebar.button[1].click().run()
        self.check_page()
        self.assertEqual(self.at.sidebar.radio[0].value, "AI Helpdesk")
        self.assertEqual(len(self.at.chat_message), 2)
        self.assertTrue(self.at.success)

    def test_no_saved_chat_does_not_erase_current_messages(self):
        self.at.session_state.messages = [{"role": "user", "content": "Unsaved question"}]
        self.at.sidebar.button[1].click().run()
        self.assertEqual(self.at.session_state.messages[0]["content"], "Unsaved question")
        self.assertTrue(self.at.info)

    def test_clear_chat_removes_messages(self):
        self.at.session_state.messages = [{"role": "user", "content": "Test question"}]
        self.at.sidebar.button[2].click().run()
        self.check_page()
        self.assertEqual(self.at.session_state.messages, [])


if __name__ == "__main__":
    unittest.main()
