from fastapi import HTTPException, status

class AppException(HTTPException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "An internal server occured"

    def __init__(self, detail: str = None):
        if detail is None:
            detail = self.detail

        super().__init__(status_code = self.status_code, detail = detail)

class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"

class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad Request"

class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized"

class CredentialsException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Incorrect credentials"

class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You dont have permission to access this resource"