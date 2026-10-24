from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=254)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def has_change(self) -> "UserUpdate":
        if self.email is None and self.password is None:
            raise ValueError("email or password is required")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
