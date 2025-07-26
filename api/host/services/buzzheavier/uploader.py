#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serviço de upload de arquivos para BuzzHeavier
"""

import os
import requests
import hashlib
import logging
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from .client import BuzzHeavierClient
from models.file_models import FileInfo, FileStatus
from utils.progress import StatusDisplay


class FileUploadWrapper:
    """Wrapper para arquivo que monitora progresso"""
    
    def __init__(self, file_obj, progress_callback: Optional[Callable[[bytes], None]] = None):
        self.file_obj = file_obj
        self.progress_callback = progress_callback
    
    def read(self, size=-1):
        """Lê dados e notifica callback"""
        chunk = self.file_obj.read(size)
        if chunk and self.progress_callback:
            self.progress_callback(chunk)
        return chunk
    
    def __getattr__(self, name):
        """Delega outros atributos para o arquivo original"""
        return getattr(self.file_obj, name)


class UploadProgressMonitor:
    """Monitor de progresso para upload de arquivo"""
    
    def __init__(self, filename: str, total_size: int):
        self.filename = filename
        self.total_size = total_size
        self.uploaded = 0
        self.status_display = StatusDisplay(f"Uploading {filename}")
    
    def __call__(self, chunk: bytes):
        """Callback chamado para cada chunk enviado"""
        self.uploaded += len(chunk)
        
        if self.total_size > 0:
            percent = (self.uploaded / self.total_size) * 100
            uploaded_mb = self.uploaded / (1024 * 1024)
            total_mb = self.total_size / (1024 * 1024)
            
            message = f"Uploading {self.filename} - {percent:.1f}% ({uploaded_mb:.1f}/{total_mb:.1f} MB)"
            self.status_display.update(message)
    
    def finish(self, success: bool = True):
        """Finaliza o monitor de progresso"""
        if success:
            self.status_display.finish(f"Upload completo: {self.filename}")
        else:
            self.status_display.finish(f"Upload falhou: {self.filename}")


class FileUploader:
    """Serviço de upload de arquivos para BuzzHeavier"""
    
    def __init__(self, client: BuzzHeavierClient):
        self.client = client
        self.logger = logging.getLogger(__name__)
    
    def upload_file(self, file_info: FileInfo, remote_path: str, 
                   progress_callback: Optional[Callable[[bytes], None]] = None) -> bool:
        """
        Upload de arquivo individual
        
        Args:
            file_info: Informações do arquivo
            remote_path: Caminho remoto de destino
            progress_callback: Callback para progresso
            
        Returns:
            True se upload foi bem-sucedido
        """
        try:
            filename = os.path.basename(file_info.path)
            
            # Verifica se arquivo já existe
            if self.client.check_file_exists(remote_path, filename):
                self.logger.info(f"Arquivo já existe: {filename}")
                file_info.status = FileStatus.SKIPPED
                return True
            
            # Cria diretório se não existe
            if not self.client.create_directory(remote_path):
                self.logger.error(f"Falha ao criar diretório: {remote_path}")
                file_info.status = FileStatus.FAILED
                file_info.error_message = "Falha ao criar diretório remoto"
                return False
            
            # Obtém URL de upload
            upload_url = self.client.get_upload_url(remote_path, filename)
            if not upload_url:
                self.logger.error(f"Falha ao obter URL de upload para: {filename}")
                file_info.status = FileStatus.FAILED
                file_info.error_message = "Falha ao obter URL de upload"
                return False
            
            # Configura monitor de progresso
            progress_monitor = UploadProgressMonitor(filename, file_info.size)
            
            # Combina callbacks
            def combined_callback(chunk: bytes):
                progress_monitor(chunk)
                if progress_callback:
                    progress_callback(chunk)
            
            # Realiza upload
            file_info.status = FileStatus.UPLOADING
            
            with open(file_info.path, 'rb') as f:
                wrapped_file = FileUploadWrapper(f, combined_callback)
                
                response = requests.put(
                    upload_url,
                    data=wrapped_file,
                    timeout=self.client.config.timeout_seconds,
                    headers={'Content-Type': 'application/octet-stream'}
                )
                
                response.raise_for_status()
            
            # Confirma upload
            if self.client.confirm_upload(remote_path, filename, file_info.hash):
                file_info.status = FileStatus.UPLOADED
                progress_monitor.finish(True)
                self.logger.info(f"Upload concluído: {filename}")
                return True
            else:
                file_info.status = FileStatus.FAILED
                file_info.error_message = "Falha na confirmação do upload"
                progress_monitor.finish(False)
                return False
        
        except requests.RequestException as e:
            file_info.status = FileStatus.FAILED
            file_info.error_message = f"Erro de rede: {str(e)}"
            self.logger.error(f"Erro no upload de {filename}: {e}")
            return False
        
        except Exception as e:
            file_info.status = FileStatus.FAILED
            file_info.error_message = f"Erro inesperado: {str(e)}"
            self.logger.error(f"Erro inesperado no upload de {filename}: {e}")
            return False
    
    def upload_with_retry(self, file_info: FileInfo, remote_path: str,
                         max_attempts: int = 3,
                         progress_callback: Optional[Callable[[bytes], None]] = None) -> bool:
        """
        Upload com retry automático
        
        Args:
            file_info: Informações do arquivo
            remote_path: Caminho remoto
            max_attempts: Número máximo de tentativas
            progress_callback: Callback para progresso
            
        Returns:
            True se upload foi bem-sucedido
        """
        for attempt in range(max_attempts):
            file_info.upload_attempts = attempt + 1
            
            if self.upload_file(file_info, remote_path, progress_callback):
                return True
            
            if attempt < max_attempts - 1:
                self.logger.warning(f"Tentativa {attempt + 1} falhou para {file_info.path}, tentando novamente...")
        
        self.logger.error(f"Upload falhou após {max_attempts} tentativas: {file_info.path}")
        return False
    
    def validate_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """Valida integridade do arquivo"""
        try:
            actual_hash = self._calculate_file_hash(file_path)
            return actual_hash == expected_hash
        except Exception as e:
            self.logger.error(f"Erro na validação de integridade: {e}")
            return False
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calcula hash MD5 do arquivo"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class BatchUploader:
    """Uploader para múltiplos arquivos em lote"""
    
    def __init__(self, uploader: FileUploader):
        self.uploader = uploader
        self.logger = logging.getLogger(__name__)
    
    def upload_batch(self, files: list[FileInfo], remote_base_path: str,
                    progress_callback: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, int]:
        """
        Upload de múltiplos arquivos
        
        Args:
            files: Lista de arquivos para upload
            remote_base_path: Caminho base remoto
            progress_callback: Callback para progresso (filename, current, total)
            
        Returns:
            Dicionário com estatísticas: {'uploaded': N, 'skipped': N, 'failed': N}
        """
        stats = {'uploaded': 0, 'skipped': 0, 'failed': 0}
        
        for i, file_info in enumerate(files):
            if progress_callback:
                progress_callback(os.path.basename(file_info.path), i + 1, len(files))
            
            # Determina caminho remoto baseado na estrutura do arquivo
            remote_path = self._determine_remote_path(file_info.path, remote_base_path)
            
            # Realiza upload
            success = self.uploader.upload_with_retry(file_info, remote_path)
            
            # Atualiza estatísticas
            if file_info.status == FileStatus.UPLOADED:
                stats['uploaded'] += 1
            elif file_info.status == FileStatus.SKIPPED:
                stats['skipped'] += 1
            else:
                stats['failed'] += 1
        
        return stats
    
    def _determine_remote_path(self, file_path: str, base_path: str) -> str:
        """Determina caminho remoto baseado na estrutura local"""
        # Por enquanto usa o caminho base - pode ser customizado conforme necessário
        return base_path