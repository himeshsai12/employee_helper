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
.\.venv\Scripts\python.exe -m pip install -r Requirements.txt
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
