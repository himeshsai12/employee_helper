"""Translate provider failures into actionable messages without exposing secrets."""

from groq import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)


def helpdesk_error_message(error):
    if isinstance(error, RateLimitError):
        return (
            "The Groq request limit has been reached. Wait a moment and try again. "
            "You can still use Tickets, Employees, and Assets."
        )

    if isinstance(error, AuthenticationError):
        return "Groq rejected the API key. Check GROQ_API_KEY in .env."

    if isinstance(error, APITimeoutError):
        return "The AI service took too long to respond. Please try again."

    if isinstance(error, APIConnectionError):
        return "Could not reach the AI service. Check your internet connection."

    if isinstance(error, NotFoundError):
        return "The configured AI model is unavailable. Check MODEL_NAME in .env."

    if isinstance(error, BadRequestError):
        return "The AI service could not process this request. Try rephrasing it."

    if isinstance(error, ValueError) and str(error).startswith("GROQ_API_KEY is missing"):
        return "Add GROQ_API_KEY to .env to enable AI replies."

    return (
        "The request could not be completed. Please try again. "
        "You can also create a support request on the Tickets page."
    )
