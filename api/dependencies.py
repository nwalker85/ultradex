"""Dependency injection for FastAPI"""

from core import DexClient, ClaudeClient, ContactAnalyzer


# Will be populated by main.py during app startup
_app_state = {}


def set_app_state(app_state: dict):
    """Set the app state (called from main.py)"""
    global _app_state
    _app_state = app_state


def get_dex_client() -> DexClient:
    """Get Dex client from app state"""
    return _app_state["dex"]


def get_claude_client() -> ClaudeClient:
    """Get Claude client from app state"""
    return _app_state["claude"]


def get_analyzer() -> ContactAnalyzer:
    """Get contact analyzer from app state"""
    return _app_state["analyzer"]
