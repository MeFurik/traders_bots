"""
Compatibility stub for removed stdlib module imghdr on Python 3.13+.
Only what python-telegram-bot 13.x реально использует.
"""

import os

def what(file, h=None):
    """Very minimal implementation: returns None (no type detection)."""
    return None
