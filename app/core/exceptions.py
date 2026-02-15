from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Recurso nao encontrado"):
        super().__init__(message, status_code=404, code="NOT_FOUND")


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422, code="VALIDATION_ERROR")
