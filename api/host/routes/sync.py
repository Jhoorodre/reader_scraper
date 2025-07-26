#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API REST endpoints para sincronização
"""

from flask import Flask, request, jsonify, Blueprint
import logging
from typing import Dict, Any, Optional

from services import SyncManager
from models import SyncConfig
from utils import config_manager

# Blueprint para rotas de sincronização
sync_bp = Blueprint('sync', __name__, url_prefix='/sync')

# Instância global do sync manager
_sync_manager: Optional[SyncManager] = None


def get_sync_manager() -> SyncManager:
    """Obtém instância do sync manager"""
    global _sync_manager
    
    if _sync_manager is None:
        config = config_manager.get_sync_config()
        _sync_manager = SyncManager(config)
    
    return _sync_manager


@sync_bp.route('/start', methods=['POST'])
def start_sync():
    """
    POST /sync/start
    Inicia sincronização
    
    Body:
    {
        "root_path": "/path/to/sync",
        "config": {
            "max_concurrent_uploads": 5,
            "retry_attempts": 3,
            ...
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        root_path = data.get('root_path')
        if not root_path:
            return jsonify({'error': 'root_path obrigatório'}), 400
        
        # Atualiza configuração se fornecida
        if 'config' in data:
            current_config = config_manager.get_sync_config()
            
            # Atualiza campos fornecidos
            for key, value in data['config'].items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)
            
            config_manager.update_sync_config(current_config)
        
        # Obtém sync manager
        sync_manager = get_sync_manager()
        
        # Verifica se já está executando
        status = sync_manager.get_status()
        if status['is_running']:
            return jsonify({'error': 'Sincronização já está em execução'}), 409
        
        # Inicia sincronização em thread separada
        import threading
        
        def sync_worker():
            result = sync_manager.start_sync(root_path)
            logging.info(f"Sincronização concluída: {result}")
        
        thread = threading.Thread(target=sync_worker, daemon=True)
        thread.start()
        
        return jsonify({
            'message': 'Sincronização iniciada',
            'root_path': root_path,
            'status': 'started'
        }), 202
    
    except Exception as e:
        logging.error(f"Erro ao iniciar sincronização: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/status', methods=['GET'])
def get_sync_status():
    """
    GET /sync/status
    Retorna status atual da sincronização
    """
    try:
        sync_manager = get_sync_manager()
        status = sync_manager.get_status()
        
        return jsonify({
            'status': 'success',
            'data': status
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao obter status: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/stats', methods=['GET'])
def get_sync_stats():
    """
    GET /sync/stats
    Retorna estatísticas detalhadas
    """
    try:
        sync_manager = get_sync_manager()
        stats = sync_manager.stats_manager.get_current_stats()
        
        # Adiciona estatísticas de estado
        state_data = {
            'failed_files_count': len(sync_manager.state_manager.get_failed_files()),
            'successful_files_count': len(sync_manager.state_manager.get_successful_files()),
            'last_root_path': sync_manager.state_manager.get_last_root_path()
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'current_stats': stats,
                'state_info': state_data
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/stop', methods=['POST'])
def stop_sync():
    """
    POST /sync/stop
    Para sincronização em execução
    """
    try:
        sync_manager = get_sync_manager()
        
        status = sync_manager.get_status()
        if not status['is_running']:
            return jsonify({'message': 'Nenhuma sincronização em execução'}), 200
        
        sync_manager.stop_sync()
        
        return jsonify({
            'message': 'Solicitação de parada enviada',
            'status': 'stopping'
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao parar sincronização: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/retry-failed', methods=['POST'])
def retry_failed():
    """
    POST /sync/retry-failed
    Reprocessa arquivos que falharam
    """
    try:
        sync_manager = get_sync_manager()
        
        # Verifica se há arquivos para reprocessar
        failed_files = sync_manager.state_manager.get_failed_files()
        if not failed_files:
            return jsonify({'message': 'Nenhum arquivo para reprocessar'}), 200
        
        # Verifica se não está executando
        status = sync_manager.get_status()
        if status['is_running']:
            return jsonify({'error': 'Sincronização já está em execução'}), 409
        
        # Inicia reprocessamento em thread separada
        import threading
        
        def retry_worker():
            result = sync_manager.retry_failed_files()
            logging.info(f"Reprocessamento concluído: {result}")
        
        thread = threading.Thread(target=retry_worker, daemon=True)
        thread.start()
        
        return jsonify({
            'message': f'Reprocessamento iniciado para {len(failed_files)} arquivos',
            'failed_files_count': len(failed_files),
            'status': 'started'
        }), 202
    
    except Exception as e:
        logging.error(f"Erro ao reprocessar arquivos: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/history', methods=['GET'])
def get_sync_history():
    """
    GET /sync/history
    Retorna histórico de sincronizações
    """
    try:
        sync_manager = get_sync_manager()
        history = sync_manager.state_manager.get_sync_history()
        
        return jsonify({
            'status': 'success',
            'data': {
                'history': history,
                'count': len(history)
            }
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao obter histórico: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/config', methods=['GET'])
def get_sync_config():
    """
    GET /sync/config
    Retorna configuração atual
    """
    try:
        config = config_manager.get_sync_config()
        
        # Oculta token para segurança
        config_dict = {
            'max_concurrent_uploads': config.max_concurrent_uploads,
            'retry_attempts': config.retry_attempts,
            'timeout_seconds': config.timeout_seconds,
            'chunk_size': config.chunk_size,
            'auto_consolidate': config.auto_consolidate,
            'has_token': bool(config.buzzheavier_token)
        }
        
        return jsonify({
            'status': 'success',
            'data': config_dict
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao obter configuração: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/config', methods=['PUT'])
def update_sync_config():
    """
    PUT /sync/config
    Atualiza configuração
    
    Body:
    {
        "max_concurrent_uploads": 5,
        "retry_attempts": 3,
        "timeout_seconds": 30,
        "chunk_size": 8192,
        "auto_consolidate": false
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON body obrigatório'}), 400
        
        # Obtém configuração atual
        current_config = config_manager.get_sync_config()
        
        # Atualiza campos fornecidos
        updated_fields = []
        for key, value in data.items():
            if hasattr(current_config, key) and key != 'buzzheavier_token':
                old_value = getattr(current_config, key)
                setattr(current_config, key, value)
                updated_fields.append(f"{key}: {old_value} -> {value}")
        
        if not updated_fields:
            return jsonify({'message': 'Nenhum campo válido para atualizar'}), 400
        
        # Salva configuração
        config_manager.update_sync_config(current_config)
        
        return jsonify({
            'message': 'Configuração atualizada',
            'updated_fields': updated_fields
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao atualizar configuração: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


@sync_bp.route('/clear-state', methods=['POST'])
def clear_sync_state():
    """
    POST /sync/clear-state
    Limpa estado de sincronização (falhas, sucessos, cache)
    """
    try:
        data = request.get_json() or {}
        clear_type = data.get('type', 'all')  # all, failed, successful, cache
        
        sync_manager = get_sync_manager()
        state_manager = sync_manager.state_manager
        
        cleared_items = []
        
        if clear_type in ['all', 'failed']:
            failed_count = len(state_manager.get_failed_files())
            state_manager.clear_failed_files()
            cleared_items.append(f"{failed_count} arquivos com falha")
        
        if clear_type in ['all', 'cache']:
            state_manager.clear_scan_cache()
            sync_manager.file_scanner.clear_cache()
            cleared_items.append("cache de scans")
        
        if clear_type == 'all':
            state_manager.reset_state()
            cleared_items = ["todo o estado"]
        
        return jsonify({
            'message': 'Estado limpo com sucesso',
            'cleared': cleared_items
        }), 200
    
    except Exception as e:
        logging.error(f"Erro ao limpar estado: {e}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500


# Handlers de erro para o blueprint
@sync_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404


@sync_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500