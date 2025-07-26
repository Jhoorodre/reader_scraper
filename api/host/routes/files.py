#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API REST endpoints para gerenciamento de arquivos
"""

from flask import Flask, request, jsonify, Blueprint
import os
import logging
from typing import Dict, Any

from services import FileScanner, FileValidator, HierarchyAnalyzer
from models import ValidationConfig

# Blueprint para rotas de arquivos
files_bp = Blueprint('files', __name__, url_prefix='/files')

# Instâncias globais
_file_scanner = FileScanner()
_file_validator = FileValidator()
_hierarchy_analyzer = HierarchyAnalyzer()


@files_bp.route('/scan', methods=['POST'])
def scan_directory():
    """
    POST /files/scan
    Escaneia diretório e retorna estrutura
    
    Body:
    {
        "path": "/path/to/directory",
        "use_cache": true
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        path = data.get('path')
        if not path:
            return jsonify({'error': 'path obrigatório'}), 400
        
        use_cache = data.get('use_cache', True)
        
        # Verifica se caminho existe
        if not os.path.exists(path):
            return jsonify({'error': f'Caminho não encontrado: {path}'}), 404
        
        if not os.path.isdir(path):
            return jsonify({'error': f'Caminho não é um diretório: {path}'}), 400
        
        # Escaneia diretório
        directory_structure = _file_scanner.scan_directory(path, use_cache)
        
        # Encontra arquivos válidos
        valid_files = _file_scanner.find_valid_files(path)
        
        return jsonify({
            'status': 'success',
            'data': {
                'directory_structure': {
                    'root_path': directory_structure.root_path,
                    'total_files': directory_structure.total_files,
                    'total_size': directory_structure.total_size,
                    'total_directories': len(directory_structure.directories),
                    'files_by_extension': directory_structure.files_by_extension,
                    'hierarchy_levels': directory_structure.hierarchy_levels,
                    'summary': directory_structure.get_summary()
                },
                'valid_files': [
                    {
                        'agregador': f.agregador,
                        'scan': f.scan,
                        'serie': f.serie,
                        'capitulo': f.capitulo,
                        'arquivo': f.arquivo,
                        'caminho_local': f.caminho_local,
                        'caminho_relativo': f.caminho_relativo,
                        'caminho_remoto': f.get_caminho_remoto()
                    }
                    for f in valid_files[:100]  # Limita a 100 para evitar payload muito grande
                ],
                'valid_files_count': len(valid_files),
                'scan_timestamp': directory_structure.__dict__.get('timestamp')
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao escanear diretório: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/validate', methods=['POST'])
def validate_files():
    """
    POST /files/validate
    Valida lista de arquivos
    
    Body:
    {
        "files": ["/path/to/file1.jpg", "/path/to/file2.png"],
        "config": {
            "max_file_size": 52428800,
            "min_file_size": 1024,
            "check_duplicates": true,
            "validate_images": true
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        files = data.get('files', [])
        if not files:
            return jsonify({'error': 'Lista de arquivos obrigatória'}), 400
        
        # Configuração de validação
        config_data = data.get('config', {})
        validation_config = ValidationConfig(**config_data)
        
        # Cria validador com configuração
        validator = FileValidator(validation_config)
        
        # Executa validação
        result = validator.validate_file_list(files)
        
        return jsonify({
            'status': 'success',
            'data': {
                'is_valid': result.is_valid,
                'total_files': result.total_files,
                'valid_files_count': len(result.valid_files),
                'invalid_files_count': len(result.invalid_files),
                'total_size': result.total_size,
                'validation_errors': result.validation_errors,
                'invalid_files': result.invalid_files,
                'valid_files_sample': [
                    {
                        'path': f.path,
                        'size': f.size,
                        'hash': f.hash,
                        'status': f.status.value
                    }
                    for f in result.valid_files[:10]  # Amostra de 10
                ]
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro na validação: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/hierarchy', methods=['POST'])
def analyze_hierarchy():
    """
    POST /files/hierarchy
    Analisa estrutura hierárquica de um diretório
    
    Body:
    {
        "path": "/path/to/directory"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        path = data.get('path')
        if not path:
            return jsonify({'error': 'path obrigatório'}), 400
        
        # Valida estrutura hierárquica
        result = _hierarchy_analyzer.validate_hierarchy_structure(path)
        
        # Detecta agregador
        try:
            agregador = _hierarchy_analyzer.detect_agregador(path)
        except Exception as e:
            agregador = None
            result['warnings'].append(f"Não foi possível detectar agregador: {e}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'is_valid': result['valid'],
                'errors': result['errors'],
                'warnings': result['warnings'],
                'stats': result['stats'],
                'detected_agregador': agregador
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro na análise de hierarquia: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/duplicates', methods=['POST'])
def find_duplicates():
    """
    POST /files/duplicates
    Encontra arquivos duplicados por hash
    
    Body:
    {
        "files": ["/path/to/file1.jpg", "/path/to/file2.png"],
        "path": "/path/to/directory"  // alternativa a files
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        files = data.get('files')
        path = data.get('path')
        
        if not files and not path:
            return jsonify({'error': 'files ou path obrigatório'}), 400
        
        # Se path fornecido, escaneia arquivos
        if path and not files:
            if not os.path.exists(path):
                return jsonify({'error': f'Caminho não encontrado: {path}'}), 404
            
            valid_structures = _file_scanner.find_valid_files(path)
            files = [s.caminho_local for s in valid_structures]
        
        # Encontra duplicatas
        duplicates = _file_validator.find_duplicate_files(files)
        
        # Formata resultado
        duplicate_groups = []
        total_duplicates = 0
        
        for hash_value, file_paths in duplicates.items():
            duplicate_groups.append({
                'hash': hash_value,
                'files': file_paths,
                'count': len(file_paths),
                'total_size': sum(os.path.getsize(f) for f in file_paths if os.path.exists(f))
            })
            total_duplicates += len(file_paths) - 1  # -1 porque o original não conta
        
        return jsonify({
            'status': 'success',
            'data': {
                'has_duplicates': len(duplicate_groups) > 0,
                'duplicate_groups': duplicate_groups,
                'total_duplicate_files': total_duplicates,
                'total_groups': len(duplicate_groups),
                'scanned_files': len(files)
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao buscar duplicatas: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/storage-check', methods=['POST'])
def check_storage():
    """
    POST /files/storage-check
    Verifica se há espaço suficiente para upload
    
    Body:
    {
        "files": ["/path/to/file1.jpg"],
        "available_space": 1073741824  // bytes
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        files = data.get('files', [])
        available_space = data.get('available_space')
        
        if available_space is None:
            return jsonify({'error': 'available_space obrigatório'}), 400
        
        # Valida espaço de armazenamento
        result = _file_validator.validate_storage_space(files, available_space)
        
        return jsonify({
            'status': 'success',
            'data': result
        }), 200
    
    except Exception as e:
        logging.error(f"Erro na verificação de armazenamento: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/info', methods=['POST'])
def get_file_info():
    """
    POST /files/info
    Obtém informações detalhadas de um arquivo
    
    Body:
    {
        "path": "/path/to/file.jpg"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        file_path = data.get('path')
        if not file_path:
            return jsonify({'error': 'path obrigatório'}), 400
        
        if not os.path.exists(file_path):
            return jsonify({'error': f'Arquivo não encontrado: {file_path}'}), 404
        
        # Valida arquivo individual
        is_valid, errors = _file_validator.validate_single_file(file_path)
        
        # Informações básicas do arquivo
        stat = os.stat(file_path)
        
        file_info = {
            'path': file_path,
            'size': stat.st_size,
            'is_valid': is_valid,
            'validation_errors': errors,
            'modified_time': stat.st_mtime,
            'extension': os.path.splitext(file_path)[1].lower(),
            'basename': os.path.basename(file_path),
            'dirname': os.path.dirname(file_path)
        }
        
        # Tenta analisar hierarquia se válido
        if is_valid:
            try:
                # Assume que está em uma estrutura hierárquica padrão
                parent_dir = os.path.dirname(file_path)
                root_candidates = [
                    os.path.dirname(parent_dir),
                    os.path.dirname(os.path.dirname(parent_dir)),
                    os.path.dirname(os.path.dirname(os.path.dirname(parent_dir)))
                ]
                
                hierarchy_info = None
                for root_candidate in root_candidates:
                    try:
                        structure = _hierarchy_analyzer.analyze_file_path(file_path, root_candidate)
                        if structure:
                            hierarchy_info = {
                                'agregador': structure.agregador,
                                'scan': structure.scan,
                                'serie': structure.serie,
                                'capitulo': structure.capitulo,
                                'arquivo': structure.arquivo,
                                'caminho_remoto': structure.get_caminho_remoto()
                            }
                            break
                    except:
                        continue
                
                file_info['hierarchy'] = hierarchy_info
            
            except Exception as e:
                file_info['hierarchy_error'] = str(e)
        
        return jsonify({
            'status': 'success',
            'data': file_info
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao obter informações do arquivo: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@files_bp.route('/clear-cache', methods=['POST'])
def clear_file_cache():
    """
    POST /files/clear-cache
    Limpa cache de arquivos
    """
    try:
        _file_scanner.clear_cache()
        _file_validator.clear_cache()
        
        return jsonify({
            'status': 'success',
            'message': 'Cache de arquivos limpo'
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao limpar cache: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


# Handlers de erro para o blueprint
@files_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404


@files_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500