#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente HTTP para BuzzHeavier API
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models.sync_models import SyncConfig
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

API_URL_BASE = "https://buzzheavier.com/api"
UPLOAD_URL_BASE = "https://w.buzzheavier.com"
API_URL_FS = f"{API_URL_BASE}/fs"
API_URL_ACCOUNT = f"{API_URL_BASE}/account"


class BuzzHeavierClient:
    """Cliente HTTP para comunicação com BuzzHeavier API"""
    
    def __init__(self, config: SyncConfig):
        self.config = config
        self.session = requests.Session()
        self._setup_session()
        self.logger = logging.getLogger(__name__)
    
    def _setup_session(self):
        """Configura sessão HTTP com retry e timeouts"""
        # Configuração de retry
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Headers padrão
        self.session.headers.update({
            'User-Agent': 'BuzzHeavier-Sync/2.0',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.config.buzzheavier_token}'
        })
        
        # Timeout padrão
        self.session.timeout = self.config.timeout_seconds
    
    def test_connection(self) -> bool:
        """Testa conexão com a API"""
        try:
            response = self.session.get(f"{API_URL_ACCOUNT}/me")
            return response.status_code == 200
        except requests.RequestException as e:
            self.logger.error(f"Erro ao testar conexão: {e}")
            return False
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Obtém informações da conta"""
        try:
            response = self.session.get(f"{API_URL_ACCOUNT}/me")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Erro ao obter informações da conta: {e}")
            return None
    
    def check_file_exists(self, remote_path: str, filename: str) -> bool:
        """Verifica se arquivo já existe no servidor"""
        try:
            url = f"{API_URL_FS}/files"
            params = {
                'path': remote_path,
                'filename': filename
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('exists', False)
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao verificar existência do arquivo: {e}")
            return False
    
    def create_directory(self, remote_path: str) -> bool:
        """Cria diretório no servidor"""
        try:
            url = f"{API_URL_FS}/mkdir"
            data = {'path': remote_path}
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao criar diretório {remote_path}: {e}")
            return False
    
    def list_directory(self, remote_path: str) -> Optional[List[Dict[str, Any]]]:
        """Lista conteúdo do diretório"""
        try:
            url = f"{API_URL_FS}/list"
            params = {'path': remote_path}
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            return response.json().get('files', [])
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao listar diretório {remote_path}: {e}")
            return None
    
    def get_upload_url(self, remote_path: str, filename: str) -> Optional[str]:
        """Obtém URL para upload do arquivo"""
        try:
            url = f"{API_URL_FS}/upload-url"
            data = {
                'path': remote_path,
                'filename': filename
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            return response.json().get('upload_url')
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao obter URL de upload: {e}")
            return None
    
    def confirm_upload(self, remote_path: str, filename: str, file_hash: str) -> bool:
        """Confirma que o upload foi concluído"""
        try:
            url = f"{API_URL_FS}/upload-confirm"
            data = {
                'path': remote_path,
                'filename': filename,
                'hash': file_hash
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao confirmar upload: {e}")
            return False
    
    def delete_file(self, remote_path: str, filename: str) -> bool:
        """Remove arquivo do servidor"""
        try:
            url = f"{API_URL_FS}/delete"
            data = {
                'path': remote_path,
                'filename': filename
            }
            
            response = self.session.delete(url, json=data)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Erro ao deletar arquivo: {e}")
            return False
    
    def get_storage_info(self) -> Optional[Dict[str, Any]]:
        """Obtém informações de armazenamento"""
        try:
            response = self.session.get(f"{API_URL_ACCOUNT}/storage")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Erro ao obter informações de armazenamento: {e}")
            return None
    
    def close(self):
        """Fecha a sessão HTTP"""
        self.session.close()