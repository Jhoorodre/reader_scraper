#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelos de dados para arquivos e validação
"""

import os
import hashlib
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum


class FileStatus(Enum):
    """Status de arquivo para upload"""
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FileInfo:
    """Informações de arquivo para upload"""
    path: str
    size: int
    hash: str
    status: FileStatus = FileStatus.PENDING
    error_message: Optional[str] = None
    upload_attempts: int = 0
    last_attempt: Optional[str] = None
    
    @classmethod
    def from_path(cls, file_path: str) -> 'FileInfo':
        """Cria FileInfo a partir do caminho do arquivo"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        size = path.stat().st_size
        hash_value = cls._calculate_hash(file_path)
        
        return cls(
            path=str(path),
            size=size,
            hash=hash_value
        )
    
    @staticmethod
    def _calculate_hash(file_path: str) -> str:
        """Calcula hash MD5 do arquivo"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            'path': self.path,
            'size': self.size,
            'hash': self.hash,
            'status': self.status.value,
            'error_message': self.error_message,
            'upload_attempts': self.upload_attempts,
            'last_attempt': self.last_attempt
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileInfo':
        """Cria FileInfo a partir de dicionário"""
        return cls(
            path=data['path'],
            size=data['size'],
            hash=data['hash'],
            status=FileStatus(data.get('status', 'pending')),
            error_message=data.get('error_message'),
            upload_attempts=data.get('upload_attempts', 0),
            last_attempt=data.get('last_attempt')
        )


@dataclass
class ValidationResult:
    """Resultado da validação de arquivos"""
    valid_files: List[FileInfo]
    invalid_files: List[str]
    total_size: int
    validation_errors: List[str]
    
    @property
    def is_valid(self) -> bool:
        """Retorna True se todos os arquivos são válidos"""
        return len(self.invalid_files) == 0 and len(self.validation_errors) == 0
    
    @property
    def total_files(self) -> int:
        """Número total de arquivos"""
        return len(self.valid_files) + len(self.invalid_files)


@dataclass
class DirectoryStructure:
    """Estrutura de diretório escaneada"""
    root_path: str
    total_files: int
    total_size: int
    directories: List[str]
    files_by_extension: Dict[str, int]
    hierarchy_levels: List[str]
    
    def get_summary(self) -> str:
        """Retorna resumo da estrutura"""
        ext_summary = ", ".join([f"{ext}: {count}" for ext, count in self.files_by_extension.items()])
        size_mb = self.total_size / (1024 * 1024)
        
        return (f"📁 {self.root_path}\n"
                f"📊 {self.total_files} arquivos ({size_mb:.1f} MB)\n"
                f"📂 {len(self.directories)} diretórios\n"
                f"📋 Extensões: {ext_summary}\n"
                f"🗂️  Níveis: {' > '.join(self.hierarchy_levels)}")