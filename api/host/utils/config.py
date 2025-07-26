#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciamento de configuração centralizada
"""

import os
import json
import configparser
from typing import Dict, Any, Optional
from pathlib import Path

from models.sync_models import SyncConfig


class ConfigManager:
    """Gerenciador de configuração centralizada"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self):
        """Carrega configuração do arquivo"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """Cria configuração padrão"""
        self.config['DEFAULT'] = {
            'buzzheavier_token': '',
            'max_concurrent_uploads': '5',
            'retry_attempts': '3',
            'timeout_seconds': '30',
            'chunk_size': '8192',
            'auto_consolidate': 'false'
        }
        
        self.config['logging'] = {
            'level': 'INFO',
            'log_dir': '_LOGS',
            'max_log_files': '10'
        }
        
        self.save_config()
    
    def save_config(self):
        """Salva configuração no arquivo"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get_sync_config(self) -> SyncConfig:
        """Retorna configuração de sincronização"""
        return SyncConfig.from_dict({
            'buzzheavier_token': self.config.get('DEFAULT', 'buzzheavier_token'),
            'max_concurrent_uploads': self.config.getint('DEFAULT', 'max_concurrent_uploads'),
            'retry_attempts': self.config.getint('DEFAULT', 'retry_attempts'),
            'timeout_seconds': self.config.getint('DEFAULT', 'timeout_seconds'),
            'chunk_size': self.config.getint('DEFAULT', 'chunk_size'),
            'auto_consolidate': self.config.getboolean('DEFAULT', 'auto_consolidate')
        })
    
    def update_sync_config(self, sync_config: SyncConfig):
        """Atualiza configuração de sincronização"""
        self.config.set('DEFAULT', 'buzzheavier_token', sync_config.buzzheavier_token)
        self.config.set('DEFAULT', 'max_concurrent_uploads', str(sync_config.max_concurrent_uploads))
        self.config.set('DEFAULT', 'retry_attempts', str(sync_config.retry_attempts))
        self.config.set('DEFAULT', 'timeout_seconds', str(sync_config.timeout_seconds))
        self.config.set('DEFAULT', 'chunk_size', str(sync_config.chunk_size))
        self.config.set('DEFAULT', 'auto_consolidate', str(sync_config.auto_consolidate).lower())
        self.save_config()
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Obtém valor da configuração"""
        return self.config.get(section, key, fallback=fallback)
    
    def set(self, section: str, key: str, value: str):
        """Define valor na configuração"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)


class StateManager:
    """Gerenciador de estado persistente"""
    
    def __init__(self, state_file: str = "sync_state.json"):
        self.state_file = state_file
        self._state: Dict[str, Any] = {}
        self._load_state()
    
    def _load_state(self):
        """Carrega estado do arquivo"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self._state = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._state = {}
    
    def save_state(self):
        """Salva estado no arquivo"""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor do estado"""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any):
        """Define valor no estado"""
        self._state[key] = value
        self.save_state()
    
    def update(self, data: Dict[str, Any]):
        """Atualiza múltiplos valores"""
        self._state.update(data)
        self.save_state()
    
    def clear(self):
        """Limpa todo o estado"""
        self._state.clear()
        self.save_state()


# Instâncias globais para facilitar acesso
config_manager = ConfigManager()
state_manager = StateManager()