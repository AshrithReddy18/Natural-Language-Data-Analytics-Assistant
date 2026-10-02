"""Domain errors. Each carries a stable `code` and a user-safe message; internals never leak."""


class AppError(Exception):
    code = "internal_error"
    status_code = 500
    public_message = "Something went wrong."

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.public_message
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    public_message = "The requested resource was not found."


class BadRequestError(AppError):
    code = "bad_request"
    status_code = 400
    public_message = "The request was invalid."


class DataSourceUnavailableError(AppError):
    code = "datasource_unavailable"
    status_code = 503
    public_message = "The database is unavailable. Check the connection and try again."


class LLMUnavailableError(AppError):
    code = "llm_unavailable"
    status_code = 503
    public_message = "The AI model is unavailable right now."


class LLMNotConfiguredError(LLMUnavailableError):
    code = "llm_not_configured"
    public_message = (
        "No AI provider is configured. For a free option, set LLM_PROVIDER=ollama (local model) "
        "or LLM_PROVIDER=gemini with a free GEMINI_API_KEY. See the README."
    )


class LLMOutputError(AppError):
    code = "llm_bad_output"
    status_code = 502
    public_message = "The AI model returned a response that could not be used."


class SQLValidationError(AppError):
    code = "sql_invalid"
    status_code = 422
    public_message = "The SQL query failed validation."


class QueryExecutionError(AppError):
    code = "query_failed"
    status_code = 422
    public_message = "The query could not be executed."


class QueryTimeoutError(QueryExecutionError):
    code = "query_timeout"
    status_code = 504
    public_message = "The query took too long and was cancelled."


class UnauthorizedError(AppError):
    code = "unauthorized"
    status_code = 401
    public_message = "Please sign in."


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403
    public_message = "You don't have permission to do that."


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    public_message = "That already exists."
