"""Page Object Models for E2E testing.

This package contains Page Object classes that encapsulate
interactions with each page in the application.
"""

from .base_page import BasePage
from .protection_page import ProtectionManagementPage
from .match_page import MatchPage
from .destroy_page import DestroyPage

__all__ = [
    "BasePage",
    "ProtectionManagementPage",
    "MatchPage",
    "DestroyPage",
]
