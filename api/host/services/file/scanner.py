#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serviço de escaneamento de estrutura de arquivos
"""

import os
import logging
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from collections import defaultdict

from models.sync_models import EstruturaHierarquica
from models.file_models import FileInfo, DirectoryStructure, ValidationResult
from .hierarchy import HierarchyAnalyzer


class FileScanner:
    """Scanner de estrutura de arquivos"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.hierarchy_analyzer = HierarchyAnalyzer()
        
        # Extensões suportadas
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
        
        # Cache de scans
        self._scan_cache: Dict[str, DirectoryStructure] = {}
    
    def scan_directory(self, root_path: str, use_cache: bool = True) -> DirectoryStructure:
        """
        Escaneia diretório e retorna estrutura completa
        
        Args:
            root_path: Caminho raiz para escaneamento
            use_cache: Se deve usar cache de scans anteriores
            
        Returns:
            DirectoryStructure com informações completas
        """
        root_path = os.path.abspath(root_path)
        
        # Verifica cache
        if use_cache and root_path in self._scan_cache:
            self.logger.debug(f"Usando cache para: {root_path}")
            return self._scan_cache[root_path]
        
        if not os.path.exists(root_path):
            raise FileNotFoundError(f"Diretório não encontrado: {root_path}")
        
        if not os.path.isdir(root_path):
            raise NotADirectoryError(f"Caminho não é um diretório: {root_path}")
        
        self.logger.info(f"Escaneando diretório: {root_path}")
        
        # Inicializa contadores
        total_files = 0
        total_size = 0
        directories = []
        files_by_extension = defaultdict(int)
        hierarchy_levels = []
        
        # Escaneia recursivamente
        for root, dirs, files in os.walk(root_path):
            # Adiciona diretórios
            directories.extend([os.path.join(root, d) for d in dirs])
            
            # Processa arquivos
            for file in files:
                file_path = os.path.join(root, file)
                
                try:
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size
                    
                    # Verifica extensão
                    _, ext = os.path.splitext(file.lower())
                    if ext in self.supported_extensions:
                        total_files += 1
                        total_size += file_size
                        files_by_extension[ext] += 1
                
                except (OSError, IOError) as e:
                    self.logger.warning(f"Erro ao acessar arquivo {file_path}: {e}")
        
        # Analisa hierarquia
        hierarchy_levels = self._analyze_hierarchy_levels(root_path)
        
        # Cria estrutura
        structure = DirectoryStructure(
            root_path=root_path,
            total_files=total_files,
            total_size=total_size,
            directories=directories,
            files_by_extension=dict(files_by_extension),
            hierarchy_levels=hierarchy_levels
        )
        
        # Armazena no cache
        if use_cache:
            self._scan_cache[root_path] = structure
        
        self.logger.info(f"Scan completo: {total_files} arquivos, {total_size / (1024*1024):.1f} MB")
        
        return structure
    
    def find_valid_files(self, root_path: str) -> List[EstruturaHierarquica]:
        """
        Encontra todos os arquivos válidos e retorna estruturas hierárquicas
        
        Args:
            root_path: Caminho raiz
            
        Returns:
            Lista de estruturas hierárquicas válidas
        """
        estruturas = []
        
        for root, dirs, files in os.walk(root_path):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Verifica se é arquivo de imagem suportado
                _, ext = os.path.splitext(file.lower())
                if ext not in self.supported_extensions:
                    continue
                
                try:
                    # Analisa hierarquia do arquivo
                    estrutura = self.hierarchy_analyzer.analyze_file_path(file_path, root_path)
                    if estrutura:
                        estruturas.append(estrutura)
                
                except Exception as e:
                    self.logger.warning(f"Erro ao analisar {file_path}: {e}")
        
        self.logger.info(f"Encontrados {len(estruturas)} arquivos válidos")
        return estruturas
    
    def validate_files(self, file_paths: List[str]) -> ValidationResult:
        """
        Valida lista de arquivos
        
        Args:
            file_paths: Lista de caminhos de arquivos
            
        Returns:
            Resultado da validação
        """
        valid_files = []
        invalid_files = []
        validation_errors = []
        total_size = 0
        
        for file_path in file_paths:
            try:
                if not os.path.exists(file_path):
                    invalid_files.append(file_path)
                    validation_errors.append(f"Arquivo não encontrado: {file_path}")
                    continue
                
                if not os.path.isfile(file_path):
                    invalid_files.append(file_path)
                    validation_errors.append(f"Não é um arquivo: {file_path}")
                    continue
                
                # Verifica extensão
                _, ext = os.path.splitext(file_path.lower())
                if ext not in self.supported_extensions:
                    invalid_files.append(file_path)
                    validation_errors.append(f"Extensão não suportada: {file_path}")
                    continue
                
                # Verifica se pode ler o arquivo
                try:
                    file_info = FileInfo.from_path(file_path)
                    valid_files.append(file_info)
                    total_size += file_info.size
                
                except Exception as e:
                    invalid_files.append(file_path)
                    validation_errors.append(f"Erro ao processar {file_path}: {e}")
            
            except Exception as e:
                invalid_files.append(file_path)
                validation_errors.append(f"Erro inesperado com {file_path}: {e}")
        
        return ValidationResult(
            valid_files=valid_files,
            invalid_files=invalid_files,
            total_size=total_size,
            validation_errors=validation_errors
        )
    
    def get_files_by_status(self, estruturas: List[EstruturaHierarquica],
                           uploaded_files: Set[str]) -> Dict[str, List[EstruturaHierarquica]]:
        """
        Agrupa arquivos por status (novo, existente, modificado)
        
        Args:
            estruturas: Lista de estruturas hierárquicas
            uploaded_files: Set de arquivos já uploadados
            
        Returns:
            Dicionário agrupando arquivos por status
        """
        groups = {
            'novos': [],
            'existentes': [],
            'modificados': []
        }
        
        for estrutura in estruturas:
            file_key = f"{estrutura.get_caminho_remoto()}/{estrutura.arquivo}"
            
            if file_key in uploaded_files:
                # TODO: Implementar verificação de modificação (hash, data, etc.)
                groups['existentes'].append(estrutura)
            else:
                groups['novos'].append(estrutura)
        
        return groups
    
    def _analyze_hierarchy_levels(self, root_path: str) -> List[str]:
        """Analisa níveis de hierarquia no diretório"""
        levels = []
        
        # Analisa estrutura de subdiretórios
        for root, dirs, files in os.walk(root_path):
            if root == root_path:
                continue
            
            rel_path = os.path.relpath(root, root_path)
            path_parts = rel_path.split(os.sep)
            
            # Atualiza níveis conhecidos
            for i, part in enumerate(path_parts):
                if i >= len(levels):
                    levels.append(f"Nível {i+1}")
        
        # Se vazio, assume estrutura padrão
        if not levels:
            levels = ["Scan", "Serie", "Capitulo"]
        
        return levels
    
    def clear_cache(self):
        """Limpa cache de scans"""
        self._scan_cache.clear()
        self.logger.info("Cache de scans limpo")