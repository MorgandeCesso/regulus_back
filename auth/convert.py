from db.models import User
from auth.schemas import UserResponse

def user_to_response(user: User) -> UserResponse:
    """Конвертирует модель User в схему UserResponse"""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        email_verified=user.email_verified
    )
