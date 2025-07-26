#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciamento de autenticação e sessão BuzzHeavier
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from utils.config import state_manager
API_URL_BASE = "https://buzzheavier.com/api"
API_URL_ACCOUNT = f"{API_URL_BASE}/account"


class AuthManager:
    """Gerenciador de autenticação BuzzHeavier"""
    
    def __init__(self, token: str):
        self.token = token
        self.session_info: Optional[Dict[str, Any]] = None
        self.last_validation = None
        self.logger = logging.getLogger(__name__)
        
        # Carrega sessão salva se existe
        self._load_session()
    
    def _load_session(self):
        """Carrega informações de sessão salvas"""
        session_data = state_manager.get('auth_session')
        if session_data:
            self.session_info = session_data
            self.last_validation = datetime.fromisoformat(session_data.get('last_validation', '2000-01-01'))
    
    def _save_session(self):
        """Salva informações de sessão"""
        if self.session_info:
            session_data = {
                **self.session_info,
                'last_validation': datetime.now().isoformat()
            }
            state_manager.set('auth_session', session_data)
    
    def validate_token(self) -> bool:
        """Valida token de autenticação"""
        # Cache de validação por 5 minutos
        if (self.last_validation and 
            datetime.now() - self.last_validation < timedelta(minutes=5)):
            return self.session_info is not None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.token}',
                'User-Agent': 'BuzzHeavier-Sync/2.0'
            }
            
            response = requests.get(f"{API_URL_ACCOUNT}/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.session_info = response.json()
                self.last_validation = datetime.now()
                self._save_session()
                
                self.logger.info(f"Token validado para usuário: {self.session_info.get('username', 'N/A')}")
                return True
            
            elif response.status_code == 401:
                self.logger.error("Token inválido ou expirado")
                self.session_info = None
                self._clear_session()
                return False
            
            else:
                self.logger.error(f"Erro na validação: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            self.logger.error(f"Erro de rede na validação: {e}")
            return False
    
    def _clear_session(self):
        """Limpa informações de sessão"""
        self.session_info = None
        self.last_validation = None
        state_manager.set('auth_session', None)
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Retorna informações do usuário autenticado"""
        if not self.session_info:
            if not self.validate_token():
                return None
        
        return self.session_info
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Retorna headers de autenticação"""
        return {
            'Authorization': f'Bearer {self.token}',
            'User-Agent': 'BuzzHeavier-Sync/2.0'
        }
    
    def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        return self.session_info is not None
    
    def get_username(self) -> str:
        """Retorna nome do usuário ou 'Anônimo'"""
        if self.session_info:
            return self.session_info.get('username', 'Anônimo')
        return 'Anônimo'
    
    def get_storage_quota(self) -> Dict[str, int]:
        """Retorna informações de cota de armazenamento"""
        if not self.session_info:
            return {'used': 0, 'total': 0, 'available': 0}
        
        storage = self.session_info.get('storage', {})
        used = storage.get('used', 0)
        total = storage.get('total', 0)
        available = max(0, total - used)
        
        return {
            'used': used,
            'total': total,
            'available': available
        }
    
    def check_storage_space(self, required_bytes: int) -> bool:
        """Verifica se há espaço suficiente para upload"""
        quota = self.get_storage_quota()
        return quota['available'] >= required_bytes
    
    def refresh_session(self) -> bool:
        """Força atualização das informações de sessão"""
        self.last_validation = None
        return self.validate_token()