# employee_helper

NexaDesk AI is an employee helpdesk built with Streamlit, LangChain, Groq, and MySQL.

## Features

- View support statistics and search IT tickets.
- Create tickets for registered employees using a form.
- Look up employee leave balances and assigned assets.
- Ask the AI helpdesk to use database tools, with context from earlier chat messages.
- Save and reload conversations within the current browser session.

## Setup

Use Python 3.12, MySQL, and a Groq API key.

From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your Groq API key and MySQL connection details. The default AI model is `openai/gpt-oss-20b`, served through Groq using `GROQ_API_KEY`.

In MySQL Workbench, create and select your database:

```sql
CREATE DATABASE IF NOT EXISTS tcs CHARACTER SET utf8mb4;
USE tcs;
```

Run [schema.sql](schema.sql) in that database. If you use a different database name, set `DB_NAME` in `.env` to match. Add employee records before creating tickets; an employee must exist for the ticket to be saved. Existing database records and credentials are not included in this repository.

## Run

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit. On **Tickets**, choose **New IT ticket**, select an employee, describe the issue, and click **Create ticket**. The ticket form works independently of the AI service.

AI Helpdesk requires a valid Groq key and an available API request allowance. Chat questions and relevant tool results are sent to Groq to generate answers. Quick-question examples refer to demo IDs such as `E101` and `T101`; those examples need matching records in your database.

## Streamlit Community Cloud

Deploy `app.py` from the `main` branch. Python dependencies are installed from the lowercase `requirements.txt` file.

The cloud app needs a MySQL server reachable from Streamlit Cloud. `localhost` and `127.0.0.1` refer to the cloud app's own machine, so copying your computer's local database credentials will not connect it to your local MySQL server. Create or use a hosted MySQL database, run `schema.sql` there, and add the employee records you want to use.

In the app's **Settings > Secrets**, enter these top-level TOML settings, replacing the placeholders with the values from your database provider:

```toml
GROQ_API_KEY = "your_groq_api_key"
MODEL_NAME = "openai/gpt-oss-20b"
DB_HOST = "your_hosted_mysql_address"
DB_PORT = "3306"
DB_USER = "your_database_username"
DB_PASSWORD = "your_database_password"
DB_NAME = "your_database_name"
```

Use your provider's actual port and database name. Save the secrets and reboot the cloud app. An error mentioning `localhost:3306` means the app is still configured to use a local database address or `DB_HOST` has not been provided as a top-level secret.

For a provider such as Aiven that supplies its own CA certificate, also add the downloaded certificate as a top-level multiline secret:

```toml
DB_SSL_CA_PEM = """
-----BEGIN CERTIFICATE-----
paste_the_provider_certificate_here
-----END CERTIFICATE-----
"""
```

When this setting is present, the app verifies both the provider's certificate and its database hostname. Use the complete certificate supplied by your database service.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The regression tests use synthetic data and mock model calls and database writes. They do not need a live Groq key or MySQL server.

## Project files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit pages, ticket form, and chat UI |
| `graph.py` | Groq model and LangChain helpdesk agent |
| `tools.py` | Agent tools for ticket, leave, and asset operations |
| `db.py` | MySQL queries and transaction handling |
| `errors.py` | User-facing AI service error messages |
| `schema.sql` | Empty database tables for a new installation |
| `.streamlit/config.toml` | App theme and readable status colors |
| `tests/test_helpdesk.py` | Regression tests |

This is an educational demo. Add authentication and authorization before using it with real employee data or exposing it beyond a trusted local environment.
