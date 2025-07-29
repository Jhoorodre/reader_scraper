#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciador principal de sincronização
"""

import os
import logging
import threading
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from models.sync_models import SyncConfig, SyncStats, EstruturaHierarquica
from models.file_models import FileInfo, FileStatus
from utils.progress import ProgressBar, StatusDisplay
from utils.config import state_manager
from services.buzzheavier import BuzzHeavierClient, AuthManager, FileUploader, BatchUploader
from services.file import FileScanner, FileValidator, HierarchyAnalyzer
from services.conversion import ConversionService
from .state import SyncStateManager
from .stats import SyncStatsManager


class SyncManager:
    """Gerenciador principal de sincronização com BuzzHeavier"""
    
    def __init__(self, config: SyncConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Inicializa componentes
        self.auth_manager = AuthManager(config.buzzheavier_token)
        self.client = BuzzHeavierClient(config)
        self.uploader = FileUploader(self.client)
        self.batch_uploader = BatchUploader(self.uploader)
        
        self.file_scanner = FileScanner()
        self.file_validator = FileValidator()
        self.hierarchy_analyzer = HierarchyAnalyzer()
        
        self.state_manager = SyncStateManager()
        self.stats_manager = SyncStatsManager()
        
        # Serviço de conversão (apenas se não for modo original)
        self.conversion_service = None
        if config.conversion_mode != 'original':
            try:
                self.conversion_service = ConversionService(config)
                self.logger.info(f"Serviço de conversão inicializado: {config.conversion_mode}")
            except ImportError as e:
                self.logger.warning(f"Conversão desabilitada: {e}")
                self.config.conversion_mode = 'original'
        
        # Estado de execução
        self._is_running = False
        self._should_stop = False
        self._current_operation = None
        self._lock = threading.Lock()
    
    def start_sync(self, root_path: str, 
                   progress_callback: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, Any]:
        """
        Inicia sincronização completa
        
        Args:
            root_path: Caminho raiz para sincronização
            progress_callback: Callback para progresso (operação, atual, total)
            
        Returns:
            Resultado da sincronização
        """
        with self._lock:
            if self._is_running:
                return {'success': False, 'error': 'Sincronização já está em execução'}
            
            self._is_running = True
            self._should_stop = False
        
        try:
            self.logger.info(f"Iniciando sincronização: {root_path}")
            
            # Valida autenticação
            if not self.auth_manager.validate_token():
                return {'success': False, 'error': 'Token de autenticação inválido'}
            
            # Inicia estatísticas
            self.stats_manager.reset()
            self.stats_manager.start_timer()
            
            # Fase 1: Escaneamento
            self._current_operation = "Escaneando arquivos"
            if progress_callback:
                progress_callback(self._current_operation, 0, 5)
            
            estruturas = self._scan_files(root_path)
            if not estruturas:
                return {'success': False, 'error': 'Nenhum arquivo válido encontrado'}
            
            # Fase 2: Validação
            self._current_operation = "Validando arquivos"
            if progress_callback:
                progress_callback(self._current_operation, 1, 5)
            
            validation_result = self._validate_files(estruturas)
            if not validation_result['valid']:
                return {'success': False, 'error': 'Validação de arquivos falhou', 'details': validation_result}
            
            # Fase 3: Verificação de espaço
            self._current_operation = "Verificando espaço de armazenamento"
            if progress_callback:
                progress_callback(self._current_operation, 2, 5)
            
            space_check = self._check_storage_space(validation_result['total_size'])
            if not space_check['sufficient']:
                return {'success': False, 'error': 'Espaço insuficiente', 'details': space_check}
            
            # Fase 4: Conversão (se habilitada)
            if self.conversion_service:
                self._current_operation = f"Convertendo arquivos ({self.config.conversion_mode})"
                if progress_callback:
                    progress_callback(self._current_operation, 3, 6)
                
                estruturas = self.conversion_service.prepare_for_upload(estruturas)
                self.logger.info(f"Conversão {self.config.conversion_mode} aplicada a {len(estruturas)} arquivos")
            
            # Fase 5: Agrupamento e preparação
            self._current_operation = "Preparando upload"
            if progress_callback:
                progress_callback(self._current_operation, 4, 6)
            
            upload_groups = self._prepare_upload_groups(estruturas)
            
            # Fase 6: Upload
            self._current_operation = "Realizando upload"
            if progress_callback:
                progress_callback(self._current_operation, 5, 6)
            
            upload_result = self._execute_uploads(upload_groups, progress_callback)
            
            # Finaliza estatísticas
            final_stats = self.stats_manager.get_final_stats()
            
            return {
                'success': True,
                'stats': final_stats,
                'upload_result': upload_result
            }
        
        except Exception as e:
            self.logger.error(f"Erro na sincronização: {e}", exc_info=True)
            return {'success': False, 'error': f'Erro inesperado: {e}'}
        
        finally:
            # Limpa arquivos temporários de conversão
            if self.conversion_service:
                try:
                    self.conversion_service.cleanup_temp_files()
                except Exception as e:
                    self.logger.warning(f"Erro na limpeza de arquivos temporários: {e}")
            
            with self._lock:
                self._is_running = False
                self._current_operation = None
    
    def stop_sync(self):
        """Para sincronização em execução"""
        with self._lock:
            if self._is_running:
                self._should_stop = True
                self.logger.info("Solicitação de parada da sincronização")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual da sincronização"""
        with self._lock:
            return {
                'is_running': self._is_running,
                'current_operation': self._current_operation,
                'should_stop': self._should_stop,
                'stats': self.stats_manager.get_current_stats(),
                'auth_status': self.auth_manager.is_authenticated()
            }
    
    def retry_failed_files(self) -> Dict[str, Any]:
        """Reprocessa arquivos que falharam"""
        failed_files = self.state_manager.get_failed_files()
        
        if not failed_files:
            return {'success': True, 'message': 'Nenhum arquivo para reprocessar'}
        
        self.logger.info(f"Reprocessando {len(failed_files)} arquivos")
        
        # Converte para estruturas hierárquicas
        estruturas = []
        for file_path in failed_files:
            if os.path.exists(file_path):
                # Assume que o arquivo está na mesma estrutura
                root_path = self.state_manager.get_last_root_path()
                estrutura = self.hierarchy_analyzer.analyze_file_path(file_path, root_path)
                if estrutura:
                    estruturas.append(estrutura)
        
        if not estruturas:
            return {'success': False, 'error': 'Nenhum arquivo válido para reprocessar'}
        
        # Executa upload dos arquivos falhados
        upload_groups = self._prepare_upload_groups(estruturas)
        result = self._execute_uploads(upload_groups)
        
        return {'success': True, 'result': result}
    
    def _scan_files(self, root_path: str) -> List[EstruturaHierarquica]:
        """Escaneia arquivos no diretório"""
        status_display = StatusDisplay("Escaneando diretório")
        
        try:
            # Escaneia estrutura
            directory_structure = self.file_scanner.scan_directory(root_path)
            status_display.update(f"Encontrados {directory_structure.total_files} arquivos")
            
            # Encontra arquivos válidos
            estruturas = self.file_scanner.find_valid_files(root_path)
            
            # Salva no estado
            self.state_manager.set_last_root_path(root_path)
            
            status_display.finish(f"Scan completo: {len(estruturas)} arquivos válidos")
            return estruturas
        
        except Exception as e:
            status_display.finish(f"Erro no scan: {e}")
            raise
    
    def _validate_files(self, estruturas: List[EstruturaHierarquica]) -> Dict[str, Any]:
        """Valida arquivos encontrados"""
        file_paths = [e.caminho_local for e in estruturas]
        
        # Validação básica de arquivos
        validation_result = self.file_validator.validate_file_list(file_paths)
        
        # Validação de estrutura hierárquica
        hierarchy_result = self.file_validator.validate_hierarchy_structure(estruturas)
        
        return {
            'valid': validation_result.is_valid and hierarchy_result['valid'],
            'file_validation': validation_result,
            'hierarchy_validation': hierarchy_result,
            'total_size': validation_result.total_size
        }
    
    def _check_storage_space(self, required_size: int) -> Dict[str, Any]:
        """Verifica espaço de armazenamento disponível"""
        storage_info = self.client.get_storage_info()
        
        if not storage_info:
            return {'sufficient': True, 'warning': 'Não foi possível verificar espaço'}
        
        available = storage_info.get('available', 0)
        sufficient = available >= required_size
        
        return {
            'sufficient': sufficient,
            'available': available,
            'required': required_size,
            'deficit': max(0, required_size - available)
        }
    
    def _prepare_upload_groups(self, estruturas: List[EstruturaHierarquica]) -> Dict[str, List[EstruturaHierarquica]]:
        """Prepara grupos de upload organizados por hierarquia"""
        return self.hierarchy_analyzer.group_by_hierarchy(estruturas)
    
    def _execute_uploads(self, upload_groups: Dict[str, List[EstruturaHierarquica]], 
                        progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Executa uploads em paralelo"""
        total_files = sum(len(files) for files in upload_groups.values())
        
        if total_files == 0:
            return {'uploaded': 0, 'skipped': 0, 'failed': 0}
        
        progress = ProgressBar(total_files, "Upload de arquivos")
        uploaded = 0
        skipped = 0
        failed = 0
        
        # Upload paralelo por grupo
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_uploads) as executor:
            futures = []
            
            # Submete uploads
            for group_name, estruturas in upload_groups.items():
                for estrutura in estruturas:
                    if self._should_stop:
                        break
                    
                    future = executor.submit(self._upload_single_file, estrutura)
                    futures.append(future)
            
            # Coleta resultados
            for future in as_completed(futures):
                if self._should_stop:
                    break
                
                try:
                    result = future.result()
                    
                    if result['status'] == 'uploaded':
                        uploaded += 1
                        self.stats_manager.add_uploaded(result.get('size', 0))
                    elif result['status'] == 'skipped':
                        skipped += 1
                        self.stats_manager.add_skipped()
                    else:
                        failed += 1
                        self.stats_manager.add_failed()
                        self.state_manager.add_failed_file(result['file_path'])
                    
                    progress.update()
                    
                except Exception as e:
                    self.logger.error(f"Erro no upload: {e}")
                    failed += 1
                    self.stats_manager.add_failed()
                    progress.update()
        
        progress.finish()
        
        return {
            'uploaded': uploaded,
            'skipped': skipped,
            'failed': failed,
            'total': total_files,
            'stopped_early': self._should_stop
        }
    
    def _upload_single_file(self, estrutura: EstruturaHierarquica) -> Dict[str, Any]:
        """Upload de arquivo individual"""
        try:
            # Cria FileInfo
            file_info = FileInfo.from_path(estrutura.caminho_local)
            
            # Determina caminho remoto
            remote_path = estrutura.get_caminho_remoto()
            
            # Executa upload
            success = self.uploader.upload_with_retry(
                file_info, 
                remote_path, 
                max_attempts=self.config.retry_attempts
            )
            
            if success:
                return {
                    'status': 'uploaded' if file_info.status == FileStatus.UPLOADED else 'skipped',
                    'file_path': estrutura.caminho_local,
                    'size': file_info.size
                }
            else:
                return {
                    'status': 'failed',
                    'file_path': estrutura.caminho_local,
                    'error': file_info.error_message
                }
        
        except Exception as e:
            return {
                'status': 'failed',
                'file_path': estrutura.caminho_local,
                'error': str(e)
            }
    
    def cleanup(self):
        """Limpeza de recursos"""
        try:
            self.client.close()
        except Exception as e:
            self.logger.error(f"Erro na limpeza: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()