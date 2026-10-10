"""Application exceptions.

``AppError`` is converted to a consistent JSON error body by the handlers in
``app.main``. ``ResumeParseError`` is raised for a *single* bad file and is
turned into a per-file error rather than failing the whole request.
"""


class AppError(Exception):
    """An error that should be returned to the client as an HTTP response."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class ModelUnavailableError(AppError):
    """The semantic model is not loaded and could not be loaded."""

    def __init__(self, message: str = "The semantic matching model is not available."):
        super().__init__(503, "model_unavailable", message)


class ResumeParseError(Exception):
    """A single uploaded file could not be validated or parsed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
