import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_SECRET_KEY
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import JobApplication, JobMatch, Resume, User
from app.schemas import AuthSessionResponse, UserResponse


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DUMMY_PASSWORD_HASH = hash_password("constant-time-login-check")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class AccountDeletionRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return normalized


def issue_session(user: User):
    return {
        "access_token": create_access_token(
            user.id, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
    }


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthSessionResponse,
    summary="Create an account",
    description="Creates a local account and returns a bearer token for this browser session.",
)
def register(request: Credentials, database: Session = Depends(get_db)):
    email = normalize_email(request.email)
    existing = database.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    is_first_account = (database.scalar(select(func.count(User.id))) or 0) == 0
    user = User(email=email, password_hash=hash_password(request.password))
    database.add(user)
    database.flush()

    # Older local records were created before accounts existed. Give the first
    # account ownership of those records so a local upgrade does not lose them.
    if is_first_account:
        database.execute(update(Resume).where(Resume.user_id.is_(None)).values(user_id=user.id))
        database.execute(update(JobMatch).where(JobMatch.user_id.is_(None)).values(user_id=user.id))
        database.execute(
            update(JobApplication)
            .where(JobApplication.user_id.is_(None))
            .values(user_id=user.id)
        )

    database.commit()
    database.refresh(user)
    return issue_session(user)


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    summary="Sign in",
    description="Checks the account password and returns a bearer token.",
)
def login(request: Credentials, database: Session = Depends(get_db)):
    email = normalize_email(request.email)
    user = database.scalar(select(User).where(User.email == email))
    password_matches = (
        verify_password(request.password, user.password_hash)
        if user is not None
        else verify_password(request.password, DUMMY_PASSWORD_HASH)
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issue_session(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Read the signed-in account",
    description="Returns the account associated with the bearer token.",
)
def current_account(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Permanently delete the signed-in account",
    description=(
        "Requires the current password and permanently removes the account's resumes, "
        "job comparisons, career plans, and application tracker entries. Existing tokens "
        "stop working because the account no longer exists."
    ),
)
def delete_account(
    request: AccountDeletionRequest,
    database: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The current password is incorrect.",
        )

    # Delete in dependency order so tracker entries do not outlive their account,
    # and let the foreign keys remove analyses that belong to each match.
    database.execute(delete(JobApplication).where(JobApplication.user_id == user.id))
    database.execute(delete(JobMatch).where(JobMatch.user_id == user.id))
    database.execute(delete(Resume).where(Resume.user_id == user.id))
    database.execute(delete(User).where(User.id == user.id))
    database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
