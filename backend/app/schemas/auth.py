from typing import Annotated

from pydantic import Field, StringConstraints

from .common import Input

Password = Annotated[str, StringConstraints(strip_whitespace=False)]
Email = Annotated[str, StringConstraints(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]


class Login(Input):
    email: Email
    password: Password = Field(min_length=1, max_length=256, repr=False)


class Register(Login):
    password: Password = Field(min_length=12, max_length=256, repr=False)
    display_name: str = Field(min_length=1, max_length=150)
    department: str = Field(min_length=1, max_length=100)


class Refresh(Input):
    refresh_token: str = Field(min_length=20, max_length=3000, repr=False)
