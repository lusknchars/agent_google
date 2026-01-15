"""
Tests for security utilities.
"""
import pytest

from app.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
)


def test_password_hashing():
    """Test password hashing and verification."""
    password = "mysecretpassword"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_access_token():
    """Test JWT access token creation."""
    token = create_access_token(data={"sub": "user123"})
    
    assert token is not None
    assert isinstance(token, str)
    
    payload = verify_token(token, token_type="access")
    assert payload is not None
    assert payload["sub"] == "user123"
    assert payload["type"] == "access"


def test_create_refresh_token():
    """Test JWT refresh token creation."""
    token = create_refresh_token(data={"sub": "user123"})
    
    assert token is not None
    
    payload = verify_token(token, token_type="refresh")
    assert payload is not None
    assert payload["sub"] == "user123"
    assert payload["type"] == "refresh"


def test_token_type_mismatch():
    """Test that verifying with wrong token type fails."""
    access_token = create_access_token(data={"sub": "user123"})
    refresh_token = create_refresh_token(data={"sub": "user123"})
    
    # Access token should not verify as refresh
    assert verify_token(access_token, token_type="refresh") is None
    
    # Refresh token should not verify as access
    assert verify_token(refresh_token, token_type="access") is None


def test_invalid_token():
    """Test that invalid token returns None."""
    assert verify_token("invalid.token.here") is None
    assert verify_token("") is None
