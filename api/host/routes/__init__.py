#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotas da API REST para BuzzHeavier Sync
"""

from .sync import sync_bp
from .files import files_bp

__all__ = [
    'sync_bp',
    'files_bp'
]