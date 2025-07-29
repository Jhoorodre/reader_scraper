#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelos de dados para sincronização com BuzzHeavier
"""

import threading
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class EstruturaHierarquica:
    """Representa a estrutura hierárquica validada"""
    agregador: str      # Gikamura
    scan: str          # Sussy Toons
    serie: str         # Arquiteto de Dungeons  
    capitulo: str      # Capítulo 01
    arquivo: str       # 01.jpg
    caminho_local: str # Caminho completo local
    caminho_relativo: str # Caminho relativo da raiz
    
    def get_caminho_remoto(self) -> str:
        """Retorna o caminho remoto no formato BuzzHeavier"""
        return f"{self.agregador}/{self.scan}/{self.serie}/{self.capitulo}"


@dataclass
class SyncStats:
    """Estatísticas da sincronização thread-safe"""
    def __init__(self):
        self.total_files = 0
        self.uploaded_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.total_size = 0
        self.uploaded_size = 0
        self.start_time: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def add_uploaded(self, size: int = 0):
        with self._lock:
            self.uploaded_files += 1
            self.uploaded_size += size
    
    def add_skipped(self):
        with self._lock:
            self.skipped_files += 1
    
    def add_failed(self):
        with self._lock:
            self.failed_files += 1
    
    def get_progress_percent(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.uploaded_files + self.skipped_files + self.failed_files) / self.total_files * 100
    
    def reset(self):
        """Reset das estatísticas"""
        with self._lock:
            self.total_files = 0
            self.uploaded_files = 0
            self.skipped_files = 0
            self.failed_files = 0
            self.total_size = 0
            self.uploaded_size = 0
            self.start_time = None


@dataclass
class SyncConfig:
    """Configuração de sincronização"""
    buzzheavier_token: str
    max_concurrent_uploads: int = 5
    retry_attempts: int = 3
    timeout_seconds: int = 30
    chunk_size: int = 8192
    auto_consolidate: bool = False
    conversion_mode: str = 'original'  # 'original', 'webp', 'pdf'
    webp_quality: int = 85
    pdf_page_size: str = 'A4'  # 'A4', 'Letter'
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> 'SyncConfig':
        """Cria configuração a partir de dicionário"""
        return cls(
            buzzheavier_token=config_dict.get('buzzheavier_token', ''),
            max_concurrent_uploads=config_dict.get('max_concurrent_uploads', 5),
            retry_attempts=config_dict.get('retry_attempts', 3),
            timeout_seconds=config_dict.get('timeout_seconds', 30),
            chunk_size=config_dict.get('chunk_size', 8192),
            auto_consolidate=config_dict.get('auto_consolidate', False),
            conversion_mode=config_dict.get('conversion_mode', 'original'),
            webp_quality=config_dict.get('webp_quality', 85),
            pdf_page_size=config_dict.get('pdf_page_size', 'A4')
        )