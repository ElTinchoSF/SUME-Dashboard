"""
Authentication module for SUME Dashboard.

Provides a simple password-based gate for internal access.
Password is configured via SUME_AUTH_PASSWORD environment variable.
Sessions are tracked via Streamlit session_state with configurable TTL.
"""

import hashlib
import hmac
from datetime import datetime, timedelta

import streamlit as st

from src.config import get_settings
from src.dashboard.logging_config import get_logger

logger = get_logger("auth")

SESSION_KEY = "sume_authenticated"
SESSION_TIME_KEY = "sume_auth_time"


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256 with a static salt."""
    salt = "sume-dashboard-salt-fbcb-unl"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _get_stored_password_hash() -> str:
    """Get the password hash from config (env var)."""
    settings = get_settings()
    password = settings.auth.password
    if not password:
        return ""
    return _hash_password(password)


def is_auth_enabled() -> bool:
    """Check if authentication is enabled."""
    settings = get_settings()
    return settings.auth.enabled and bool(settings.auth.password)


def is_authenticated() -> bool:
    """Check if the current session is authenticated."""
    if not is_auth_enabled():
        return True

    if SESSION_KEY not in st.session_state:
        return False

    if not st.session_state[SESSION_KEY]:
        return False

    # Check session expiry
    settings = get_settings()
    session_time = st.session_state.get(SESSION_TIME_KEY)
    if session_time:
        expiry = session_time + timedelta(hours=settings.auth.session_hours)
        if datetime.now() > expiry:
            logger.info("Session expired")
            st.session_state[SESSION_KEY] = False
            return False

    return True


def login(password: str) -> bool:
    """
    Attempt login with the given password.

    Returns True if authentication succeeds.
    """
    stored_hash = _get_stored_password_hash()
    if not stored_hash:
        logger.warning("No password configured — auth disabled")
        return True

    provided_hash = _hash_password(password)
    if hmac.compare_digest(provided_hash, stored_hash):
        st.session_state[SESSION_KEY] = True
        st.session_state[SESSION_TIME_KEY] = datetime.now()
        logger.info("Login successful")
        return True

    logger.warning("Login failed — invalid password")
    return False


def logout() -> None:
    """Clear the authentication session."""
    st.session_state[SESSION_KEY] = False
    st.session_state[SESSION_TIME_KEY] = None
    logger.info("Logged out")


def render_login_page() -> None:
    """Render the login form. Call this instead of the main app when not authenticated."""
    st.set_page_config(
        page_title="SUME Dashboard — Login",
        page_icon="🔒",
        layout="centered",
    )

    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0;">
            <h1 style="color: #244C5A; font-family: 'Montserrat', sans-serif;">
                📊 SUME Dashboard
            </h1>
            <p style="color: #666; font-size: 0.9rem;">
                Sistema de Análisis de Circuitos Administrativos<br>
                Facultad de Bioquímica y Ciencias Biológicas — UNL
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        password = st.text_input(
            "Contraseña",
            type="password",
            placeholder="Ingrese la contraseña de acceso",
        )
        submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if login(password):
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta. Intente nuevamente.")


def require_auth() -> None:
    """
    Gate function: if auth is enabled and user is not authenticated,
    show login page and stop execution. Otherwise, continue.
    """
    if is_authenticated():
        return

    render_login_page()
    st.stop()
