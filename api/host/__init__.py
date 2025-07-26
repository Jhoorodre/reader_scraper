#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BuzzHeavier Sync API - Sistema modular de sincronização
"""

__version__ = "2.0.0"
__author__ = "BuzzHeavier Sync Team"

from .models import EstruturaHierarquica, SyncStats, SyncConfig
from .utils import config_manager, state_manager, ProgressBar, StatusDisplay

# Configurações da API
API_URL_BASE = "https://buzzheavier.com/api"
UPLOAD_URL_BASE = "https://w.buzzheavier.com"
API_URL_FS = f"{API_URL_BASE}/fs"
API_URL_ACCOUNT = f"{API_URL_BASE}/account"

# Arquivos de configuração
CONFIG_FILE = "config.ini"
SYNC_STATE_FILE = "sync_state.json" 
LOGS_DIR = "_LOGS"

__all__ = [
    'EstruturaHierarquica',
    'SyncStats',
    'SyncConfig',
    'config_manager',
    'state_manager',
    'ProgressBar',
    'StatusDisplay',
    'API_URL_BASE',
    'UPLOAD_URL_BASE',
    'API_URL_FS',
    'API_URL_ACCOUNT',
    'CONFIG_FILE',
    'SYNC_STATE_FILE',
    'LOGS_DIR'
]