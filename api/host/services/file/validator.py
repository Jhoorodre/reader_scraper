#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validação de arquivos e estruturas
"""

import os
import hashlib
import logging
from typing import List, Dict, Any, Set, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from models.file_models import FileInfo, FileStatus, ValidationResult
from models.sync_models import EstruturaHierarquica


@dataclass
class ValidationConfig:
    """Configuração para validação de arquivos"""
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    min_file_size: int = 1024  # 1KB
    supported_extensions: Set[str] = None
    check_duplicates: bool = True
    validate_images: bool = True
    
    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


class FileValidator:
    """Validador de arquivos e estruturas"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.logger = logging.getLogger(__name__)
        
        # Cache de hashes para detecção de duplicatas
        self._hash_cache: Dict[str, str] = {}
    
    def validate_single_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Valida arquivo individual
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            Tupla (é_válido, lista_de_erros)
        """
        errors = []
        
        try:
            if not os.path.exists(file_path):
                errors.append("Arquivo não encontrado")
                return False, errors
            
            if not os.path.isfile(file_path):
                errors.append("Caminho não é um arquivo")
                return False, errors
            
            # Verifica extensão
            _, ext = os.path.splitext(file_path.lower())
            if ext not in self.config.supported_extensions:
                errors.append(f"Extensão não suportada: {ext}")
            
            # Verifica tamanho
            file_size = os.path.getsize(file_path)
            if file_size < self.config.min_file_size:
                errors.append(f"Arquivo muito pequeno: {file_size} bytes")
            elif file_size > self.config.max_file_size:
                errors.append(f"Arquivo muito grande: {file_size} bytes")
            
            # Verifica se é legível
            try:
                with open(file_path, 'rb') as f:
                    f.read(1024)  # Tenta ler primeiros 1KB
            except (OSError, IOError, PermissionError) as e:
                errors.append(f"Arquivo não legível: {e}")
            
            # Validação específica para imagens (se habilitada)
            if self.config.validate_images and ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}:
                image_errors = self._validate_image_file(file_path)
                errors.extend(image_errors)
        
        except Exception as e:
            errors.append(f"Erro inesperado: {e}")
        
        return len(errors) == 0, errors
    
    def validate_file_list(self, file_paths: List[str]) -> ValidationResult:
        """
        Valida lista de arquivos
        
        Args:
            file_paths: Lista de caminhos
            
        Returns:
            Resultado da validação
        """
        valid_files = []
        invalid_files = []
        validation_errors = []
        total_size = 0
        
        # Cache para detecção de duplicatas
        seen_hashes = {}
        
        for file_path in file_paths:
            is_valid, errors = self.validate_single_file(file_path)
            
            if is_valid:
                try:
                    file_info = FileInfo.from_path(file_path)
                    
                    # Verifica duplicatas se habilitado
                    if self.config.check_duplicates:
                        if file_info.hash in seen_hashes:
                            duplicate_path = seen_hashes[file_info.hash]
                            validation_errors.append(f"Arquivo duplicado: {file_path} = {duplicate_path}")
                            invalid_files.append(file_path)
                            continue
                        else:
                            seen_hashes[file_info.hash] = file_path
                    
                    valid_files.append(file_info)
                    total_size += file_info.size
                
                except Exception as e:
                    invalid_files.append(file_path)
                    validation_errors.append(f"Erro ao processar {file_path}: {e}")
            else:
                invalid_files.append(file_path)
                validation_errors.extend([f"{file_path}: {error}" for error in errors])
        
        return ValidationResult(
            valid_files=valid_files,
            invalid_files=invalid_files,
            total_size=total_size,
            validation_errors=validation_errors
        )
    
    def validate_hierarchy_structure(self, estruturas: List[EstruturaHierarquica]) -> Dict[str, Any]:
        """
        Valida estrutura hierárquica de arquivos
        
        Args:
            estruturas: Lista de estruturas hierárquicas
            
        Returns:
            Resultado da validação
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {
                'total_estruturas': len(estruturas),
                'agregadores': set(),
                'scans': set(),
                'series': set(),
                'capitulos': set()
            }
        }
        
        for estrutura in estruturas:
            # Valida componentes obrigatórios
            if not estrutura.agregador:
                result['errors'].append(f"Agregador vazio: {estrutura.caminho_local}")
            if not estrutura.scan:
                result['errors'].append(f"Scan vazio: {estrutura.caminho_local}")
            if not estrutura.serie:
                result['errors'].append(f"Série vazia: {estrutura.caminho_local}")
            if not estrutura.arquivo:
                result['errors'].append(f"Arquivo vazio: {estrutura.caminho_local}")
            
            # Coleta estatísticas
            result['stats']['agregadores'].add(estrutura.agregador)
            result['stats']['scans'].add(estrutura.scan)
            result['stats']['series'].add(f"{estrutura.scan}/{estrutura.serie}")
            
            if estrutura.capitulo:
                result['stats']['capitulos'].add(
                    f"{estrutura.scan}/{estrutura.serie}/{estrutura.capitulo}"
                )
            
            # Verifica se arquivo existe
            if not os.path.exists(estrutura.caminho_local):
                result['errors'].append(f"Arquivo não encontrado: {estrutura.caminho_local}")
        
        # Converte sets para contagem
        result['stats']['total_agregadores'] = len(result['stats']['agregadores'])
        result['stats']['total_scans'] = len(result['stats']['scans'])
        result['stats']['total_series'] = len(result['stats']['series'])
        result['stats']['total_capitulos'] = len(result['stats']['capitulos'])
        
        # Remove sets (não serializáveis)
        result['stats']['agregadores'] = list(result['stats']['agregadores'])
        result['stats']['scans'] = list(result['stats']['scans'])
        result['stats']['series'] = list(result['stats']['series'])
        result['stats']['capitulos'] = list(result['stats']['capitulos'])
        
        if result['errors']:
            result['valid'] = False
        
        return result
    
    def find_duplicate_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Encontra arquivos duplicados por hash
        
        Args:
            file_paths: Lista de caminhos
            
        Returns:
            Dicionário {hash: [lista_de_arquivos_duplicados]}
        """
        hash_groups = {}
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    file_hash = self._get_file_hash(file_path)
                    
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(file_path)
            
            except Exception as e:
                self.logger.warning(f"Erro ao calcular hash de {file_path}: {e}")
        
        # Retorna apenas grupos com duplicatas
        return {hash_val: paths for hash_val, paths in hash_groups.items() if len(paths) > 1}
    
    def validate_storage_space(self, file_paths: List[str], available_space: int) -> Dict[str, Any]:
        """
        Valida se há espaço suficiente para upload
        
        Args:
            file_paths: Lista de arquivos
            available_space: Espaço disponível em bytes
            
        Returns:
            Resultado da validação de espaço
        """
        total_size = 0
        valid_files = 0
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    valid_files += 1
            except Exception:
                continue
        
        return {
            'sufficient_space': total_size <= available_space,
            'total_size': total_size,
            'available_space': available_space,
            'required_space': total_size,
            'space_deficit': max(0, total_size - available_space),
            'valid_files': valid_files
        }
    
    def _validate_image_file(self, file_path: str) -> List[str]:
        """Validação específica para arquivos de imagem"""
        errors = []
        
        try:
            # Tenta importar PIL para validação de imagem
            try:
                from PIL import Image
            except ImportError:
                # PIL não disponível, pula validação de imagem
                return errors
            
            with Image.open(file_path) as img:
                # Verifica se é uma imagem válida
                img.verify()
                
                # Reabre para verificar dimensões (verify() fecha o arquivo)
                with Image.open(file_path) as img2:
                    width, height = img2.size
                    
                    # Validações básicas
                    if width < 1 or height < 1:
                        errors.append("Dimensões de imagem inválidas")
                    
                    if width > 10000 or height > 10000:
                        errors.append("Imagem muito grande (>10000px)")
        
        except Exception as e:
            errors.append(f"Arquivo de imagem corrompido: {e}")
        
        return errors
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calcula hash MD5 do arquivo com cache"""
        if file_path in self._hash_cache:
            return self._hash_cache[file_path]
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        file_hash = hash_md5.hexdigest()
        self._hash_cache[file_path] = file_hash
        return file_hash
    
    def clear_cache(self):
        """Limpa cache de hashes"""
        self._hash_cache.clear()