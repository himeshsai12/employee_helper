from langchain.tools import tool

from db import (
    get_ticket_status,
    get_leave_balance,
    get_asset_details,
    create_it_ticket
)


@tool
def get_ticket_status_tool(ticket_id: str) -> str:
    """Check an IT ticket using its ticket ID, such as T101."""

    result = get_ticket_status(ticket_id)

    if not result:
        return f"No ticket found with ID {ticket_id}."

    return (
        f"Ticket ID: {result['ticket_id']}\n"
        f"Employee ID: {result['employee_id']}\n"
        f"Issue: {result['issue']}\n"
        f"Status: {result['status']}"
    )


@tool
def get_leave_balance_tool(employee_id: str) -> str:
    """Get an employee's available leave balance using employee ID."""

    result = get_leave_balance(employee_id)

    if not result:
        return f"No employee found with ID {employee_id}."

    return (
        f"Employee: {result['name']}\n"
        f"Employee ID: {result['employee_id']}\n"
        f"Department: {result['department']}\n"
        f"Available leave: {result['leave_balance']} days"
    )


@tool
def asset_details_tool(employee_id: str) -> str:
    """Get all company assets assigned to an employee."""

    results = get_asset_details(employee_id)

    if not results:
        return f"No assets found for employee {employee_id}."

    details = []

    for asset in results:
        details.append(
            f"Asset ID: {asset['asset_id']}, "
            f"Type: {asset['asset_type']}, "
            f"Name: {asset['asset_name']}, "
            f"Status: {asset['status']}"
        )

    return "\n".join(details)


@tool
def create_it_ticket_tool(employee_id: str, issue: str) -> str:
    """Create a new IT support ticket for a valid employee ID."""

    try:
        result = create_it_ticket(employee_id, issue)
    except ValueError as error:
        return str(error)

    if not result:
        return (
            f"Employee {employee_id} was not found. "
            "No ticket was created."
        )

    return (
        f"Ticket created successfully.\n"
        f"Ticket ID: {result['ticket_id']}\n"
        f"Employee ID: {result['employee_id']}\n"
        f"Issue: {result['issue']}\n"
        f"Status: {result['status']}"
    )


helpdesk_tools = [
    get_ticket_status_tool,
    get_leave_balance_tool,
    asset_details_tool,
    create_it_ticket_tool
]
