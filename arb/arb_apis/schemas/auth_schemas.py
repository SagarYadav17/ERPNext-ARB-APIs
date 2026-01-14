"""
Pydantic schemas for authentication API validation
"""

import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Login request validation"""

    username: str = Field(..., min_length=3, description="Email or phone number")
    password: str = Field(..., min_length=1, description="User password")


class SendSignupOTPRequest(BaseModel):
    """Send signup OTP request validation"""

    phone: str = Field(
        ..., min_length=10, max_length=10, description="10-digit phone number"
    )
    full_name: str = Field(
        ..., min_length=2, max_length=100, description="User's full name"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number is numeric and 10 digits"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(v) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Validate full name"""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v


class VerifyOTPRequest(BaseModel):
    """Verify OTP request validation"""

    phone: str = Field(
        ..., min_length=10, max_length=10, description="10-digit phone number"
    )
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(v) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return v

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        """Validate OTP"""
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        if len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


class CompleteSignupRequest(BaseModel):
    """Complete signup request validation"""

    phone: str = Field(
        ..., min_length=10, max_length=10, description="10-digit phone number"
    )
    password: str = Field(
        ..., min_length=8, max_length=100, description="User password"
    )
    email: Optional[EmailStr] = Field(None, description="User email (optional)")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(v) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class ResendOTPRequest(BaseModel):
    """Resend OTP request validation"""

    phone: str = Field(
        ..., min_length=10, max_length=10, description="10-digit phone number"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number"""
        if not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(v) != 10:
            raise ValueError("Phone number must be exactly 10 digits")
        return v


class ForgotPasswordRequest(BaseModel):
    """Forgot password request validation"""

    phone: Optional[str] = Field(
        None, min_length=10, max_length=10, description="10-digit phone number"
    )
    email: Optional[EmailStr] = Field(None, description="User email")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number if provided"""
        if v is not None:
            if not v.isdigit():
                raise ValueError("Phone number must contain only digits")
            if len(v) != 10:
                raise ValueError("Phone number must be exactly 10 digits")
        return v

    def model_post_init(self, __context) -> None:
        """Ensure at least one of phone or email is provided"""
        if not self.phone and not self.email:
            raise ValueError("Either phone or email must be provided")


class VerifyResetOTPRequest(BaseModel):
    """Verify reset OTP request validation"""

    identifier: str = Field(..., min_length=6, description="Phone number or email")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP")

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        """Validate OTP"""
        if not v.isdigit():
            raise ValueError("OTP must contain only digits")
        if len(v) != 6:
            raise ValueError("OTP must be exactly 6 digits")
        return v


class ResetPasswordRequest(BaseModel):
    """Reset password request validation"""

    reset_token: str = Field(..., min_length=10, description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=100, description="New password"
    )
    confirm_password: str = Field(
        ..., min_length=8, max_length=100, description="Confirm new password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    def model_post_init(self, __context) -> None:
        """Ensure passwords match"""
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")


class RefreshTokenRequest(BaseModel):
    """Refresh token request validation"""

    refresh_token: str = Field(..., min_length=10, description="JWT refresh token")


class ValidateTokenRequest(BaseModel):
    """Validate token request validation"""

    token: str = Field(..., min_length=10, description="JWT token")


class ResendIdentifierRequest(BaseModel):
    """Resend OTP with identifier validation"""

    identifier: str = Field(..., min_length=6, description="Phone number or email")


class CheckUserExistsRequest(BaseModel):
    """Check user exists request validation"""

    phone: Optional[str] = Field(
        None, min_length=10, max_length=10, description="10-digit phone number"
    )
    email: Optional[EmailStr] = Field(None, description="User email")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number if provided"""
        if v is not None:
            if not v.isdigit():
                raise ValueError("Phone number must contain only digits")
            if len(v) != 10:
                raise ValueError("Phone number must be exactly 10 digits")
        return v

    def model_post_init(self, __context) -> None:
        """Ensure at least one of phone or email is provided"""
        if not self.phone and not self.email:
            raise ValueError("Either phone or email must be provided")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)