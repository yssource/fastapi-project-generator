#
# Copyright (C) {{cookiecutter.copyright}}
#
# Author: {{cookiecutter.author}} <{{cookiecutter.email}}>
#

from app.core.config import settings
from app.core.deps import get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.token import Token, TokenData
from app.schemas.user import UserInfo, UserRegister
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session
from . import Repository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=settings.jwt_token_prefix.lower(),
    scopes={
        "api": "Read information about the current API.",
        # "items": "Read items."
    },
)


async def get_current_user(
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db),
) -> UserInfo:
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = jwt.decode(token,
                             settings.secret_key,
                             algorithms=[settings.algorithm])
        username: str = payload.get("sub", None)
        if username is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, subject=username)
        user = UserRepository(db).get_by_username(username)
        if user is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception

    flag = False
    for scope in security_scopes.scopes:
        if scope in token_data.scopes:
            flag = True
            break

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )

    return user


async def get_current_active_user(current_user: UserInfo = Security(
    get_current_user, scopes=["api"])):

    return current_user


class UserRepository(Repository):
    def create(self, userinfo: UserRegister) -> Token:
        password = get_password_hash(userinfo.password)
        user = User()
        user.username = userinfo.username
        user.password = password
        user.email = userinfo.email
        self.db.add(user)
        self.db.commit()
        return user

    def authenticate(self, username: str, password: str) -> User:
        user = self.get_by_username(username)

        if not user:
            return False

        if not verify_password(password, user.password):
            return False

        return user

    def get_by_username(self, username: str) -> User:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email).first()
