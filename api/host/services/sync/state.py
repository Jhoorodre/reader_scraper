#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciamento de estado de sincronização
"""

import json
import logging
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from pathlib import Path

from utils.config import state_manager


class SyncStateManager:
    """Gerenciador de estado persistente da sincronização"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def save_sync_session(self, session_data: Dict[str, Any]):
        """Salva dados da sessão de sincronização"""
        session_data['timestamp'] = datetime.now().isoformat()
        state_manager.set('last_sync_session', session_data)
        self.logger.debug("Sessão de sincronização salva")
    
    def get_last_sync_session(self) -> Optional[Dict[str, Any]]:
        """Recupera dados da última sessão"""
        return state_manager.get('last_sync_session')
    
    def add_failed_file(self, file_path: str):
        """Adiciona arquivo à lista de falhas"""
        failed_files = set(self.get_failed_files())
        failed_files.add(file_path)
        state_manager.set('failed_files', list(failed_files))
        self.logger.debug(f"Arquivo adicionado às falhas: {file_path}")
    
    def remove_failed_file(self, file_path: str):
        """Remove arquivo da lista de falhas"""
        failed_files = set(self.get_failed_files())
        failed_files.discard(file_path)
        state_manager.set('failed_files', list(failed_files))
        self.logger.debug(f"Arquivo removido das falhas: {file_path}")
    
    def get_failed_files(self) -> List[str]:
        """Retorna lista de arquivos com falha"""
        failed_files = state_manager.get('failed_files', [])
        
        # Remove arquivos que não existem mais
        existing_files = []
        for file_path in failed_files:
            if Path(file_path).exists():
                existing_files.append(file_path)
        
        # Atualiza lista se houve mudanças
        if len(existing_files) != len(failed_files):
            state_manager.set('failed_files', existing_files)
            self.logger.info(f"Removidos {len(failed_files) - len(existing_files)} arquivos inexistentes das falhas")
        
        return existing_files
    
    def clear_failed_files(self):
        """Limpa lista de arquivos com falha"""
        state_manager.set('failed_files', [])
        self.logger.info("Lista de falhas limpa")
    
    def set_last_root_path(self, root_path: str):
        """Define último caminho raiz usado"""
        state_manager.set('last_root_path', root_path)
    
    def get_last_root_path(self) -> Optional[str]:
        """Retorna último caminho raiz usado"""
        return state_manager.get('last_root_path')
    
    def save_upload_progress(self, progress_data: Dict[str, Any]):
        """Salva progresso do upload"""
        progress_data['timestamp'] = datetime.now().isoformat()
        state_manager.set('upload_progress', progress_data)
    
    def get_upload_progress(self) -> Optional[Dict[str, Any]]:
        """Recupera progresso do upload"""
        return state_manager.get('upload_progress')
    
    def clear_upload_progress(self):
        """Limpa progresso do upload"""
        state_manager.set('upload_progress', None)
    
    def add_successful_file(self, file_path: str, remote_path: str):
        """Adiciona arquivo à lista de sucessos"""
        successful_files = state_manager.get('successful_files', {})
        successful_files[file_path] = {
            'remote_path': remote_path,
            'timestamp': datetime.now().isoformat()
        }
        state_manager.set('successful_files', successful_files)
    
    def get_successful_files(self) -> Dict[str, Dict[str, str]]:
        """Retorna arquivos uploadados com sucesso"""
        return state_manager.get('successful_files', {})
    
    def is_file_uploaded(self, file_path: str) -> bool:
        """Verifica se arquivo já foi uploadado"""
        successful_files = self.get_successful_files()
        return file_path in successful_files
    
    def save_scan_cache(self, root_path: str, scan_data: Dict[str, Any]):
        """Salva cache de scan de diretório"""
        cache = state_manager.get('scan_cache', {})
        cache[root_path] = {
            **scan_data,
            'timestamp': datetime.now().isoformat()
        }
        state_manager.set('scan_cache', cache)
    
    def get_scan_cache(self, root_path: str) -> Optional[Dict[str, Any]]:
        """Recupera cache de scan"""
        cache = state_manager.get('scan_cache', {})
        return cache.get(root_path)
    
    def clear_scan_cache(self):
        """Limpa cache de scans"""
        state_manager.set('scan_cache', {})
        self.logger.info("Cache de scans limpo")
    
    def save_sync_statistics(self, stats: Dict[str, Any]):
        """Salva estatísticas de sincronização"""
        stats['timestamp'] = datetime.now().isoformat()
        
        # Mantém histórico das últimas 10 sincronizações
        history = state_manager.get('sync_history', [])
        history.append(stats)
        
        # Limita a 10 entradas
        if len(history) > 10:
            history = history[-10:]
        
        state_manager.set('sync_history', history)
        state_manager.set('last_sync_stats', stats)
    
    def get_sync_history(self) -> List[Dict[str, Any]]:
        """Retorna histórico de sincronizações"""
        return state_manager.get('sync_history', [])
    
    def get_last_sync_stats(self) -> Optional[Dict[str, Any]]:
        """Retorna estatísticas da última sincronização"""
        return state_manager.get('last_sync_stats')
    
    def export_state(self) -> Dict[str, Any]:
        """Exporta todo o estado atual"""
        return {
            'failed_files': self.get_failed_files(),
            'successful_files': self.get_successful_files(),
            'last_root_path': self.get_last_root_path(),
            'sync_history': self.get_sync_history(),
            'last_sync_stats': self.get_last_sync_stats(),
            'export_timestamp': datetime.now().isoformat()
        }
    
    def import_state(self, state_data: Dict[str, Any]):
        """Importa estado de dados externos"""
        if 'failed_files' in state_data:
            state_manager.set('failed_files', state_data['failed_files'])
        
        if 'successful_files' in state_data:
            state_manager.set('successful_files', state_data['successful_files'])
        
        if 'last_root_path' in state_data:
            state_manager.set('last_root_path', state_data['last_root_path'])
        
        if 'sync_history' in state_data:
            state_manager.set('sync_history', state_data['sync_history'])
        
        self.logger.info("Estado importado com sucesso")
    
    def reset_state(self):
        """Reseta todo o estado"""
        keys_to_clear = [
            'failed_files',
            'successful_files',
            'last_root_path',
            'upload_progress',
            'scan_cache',
            'sync_history',
            'last_sync_stats',
            'last_sync_session'
        ]
        
        for key in keys_to_clear:
            state_manager.set(key, None)
        
        self.logger.info("Estado resetado")
    
    def cleanup_old_data(self, days: int = 30):
        """Remove dados antigos do estado"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Limpa histórico antigo
        history = self.get_sync_history()
        recent_history = []
        
        for entry in history:
            try:
                entry_date = datetime.fromisoformat(entry.get('timestamp', '2000-01-01'))
                if entry_date > cutoff_date:
                    recent_history.append(entry)
            except ValueError:
                # Mantém entradas com timestamp inválido
                recent_history.append(entry)
        
        if len(recent_history) != len(history):
            state_manager.set('sync_history', recent_history)
            self.logger.info(f"Removidas {len(history) - len(recent_history)} entradas antigas do histórico")
        
        # Limpa cache de scan antigo
        cache = state_manager.get('scan_cache', {})
        recent_cache = {}
        
        for path, data in cache.items():
            try:
                cache_date = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
                if cache_date > cutoff_date:
                    recent_cache[path] = data
            except ValueError:
                # Mantém cache com timestamp inválido
                recent_cache[path] = data
        
        if len(recent_cache) != len(cache):
            state_manager.set('scan_cache', recent_cache)
            self.logger.info(f"Removidas {len(cache) - len(recent_cache)} entradas antigas do cache")