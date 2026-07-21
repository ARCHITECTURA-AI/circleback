import json
from datetime import datetime, timezone
import pytest
import http.cookies
from fastapi import Response, HTTPException
from circleback.api.session import (
    create_session,
    validate_session,
    clear_session,
    get_current_user,
    SESSION_COOKIE,
    _get_signer,
)
from itsdangerous import BadSignature

@pytest.fixture
def mock_settings(monkeypatch):
    class MockSettings:
        session_secret_key = "super_secret_test_key"
        base_url = "http://localhost:8000"
        frontend_url = "http://localhost:3000"
        debug = False
    
    monkeypatch.setattr("circleback.config.get_settings", lambda: MockSettings())
    return MockSettings()

def test_create_session(mock_settings):
    response = Response()
    user_data = {"provider": "google", "email": "test@example.com"}
    create_session(response, user_data)
    
    cookie = response.headers.get("set-cookie")
    assert cookie is not None
    assert SESSION_COOKIE in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie

def test_validate_session(mock_settings):
    response = Response()
    user_data = {"provider": "google", "email": "test@example.com"}
    create_session(response, user_data)
    
    # Extract the cookie value using SimpleCookie to handle escaping
    cookie_header = response.headers.get("set-cookie")
    cookie = http.cookies.SimpleCookie(cookie_header)
    cookie_value = cookie["circleback_session"].value
    
    validated = validate_session(cookie_value)
    assert validated["provider"] == "google"
    assert validated["email"] == "test@example.com"
    assert "authenticated_at" in validated

def test_validate_session_invalid_signature(mock_settings):
    with pytest.raises(HTTPException) as exc:
        validate_session("invalid.cookie.value")
    assert exc.value.status_code == 401

def test_clear_session(mock_settings):
    response = Response()
    clear_session(response)
    
    cookie = response.headers.get("set-cookie")
    assert cookie is not None
    assert f"{SESSION_COOKIE}=" in cookie
    assert "Max-Age=0" in cookie

@pytest.mark.asyncio
async def test_get_current_user(mock_settings):
    response = Response()
    user_data = {"provider": "slack"}
    create_session(response, user_data)
    
    cookie_header = response.headers.get("set-cookie")
    cookie = http.cookies.SimpleCookie(cookie_header)
    cookie_value = cookie["circleback_session"].value
    
    user = await get_current_user(circleback_session=cookie_value)
    assert user["provider"] == "slack"

@pytest.mark.asyncio
async def test_get_current_user_no_cookie(mock_settings):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(circleback_session=None)
    assert exc.value.status_code == 401
