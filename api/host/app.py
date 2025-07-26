#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicação Flask para BuzzHeavier Sync API
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

from .routes import sync_bp, files_bp
from .utils import config_manager
from . import __version__


def create_app(config_name: str = 'default') -> Flask:
    """Factory para criar aplicação Flask"""
    
    app = Flask(__name__)
    
    # Configuração básica
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # CORS para permitir acesso de outras origens
    CORS(app)
    
    # Configuração de logging
    setup_logging(app)
    
    # Registra blueprints
    app.register_blueprint(sync_bp)
    app.register_blueprint(files_bp)
    
    # Rotas base
    setup_base_routes(app)
    
    # Handlers de erro globais
    setup_error_handlers(app)
    
    return app


def setup_logging(app: Flask):
    """Configura logging da aplicação"""
    
    # Nível de log baseado no ambiente
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configura logger do Flask
    app.logger.setLevel(getattr(logging, log_level))
    
    # Reduz verbosidade de libs externas
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def setup_base_routes(app: Flask):
    """Configura rotas base da API"""
    
    @app.route('/')
    def index():
        """Rota raiz da API"""
        return jsonify({
            'name': 'BuzzHeavier Sync API',
            'version': __version__,
            'status': 'running',
            'endpoints': {
                'sync': {
                    'start': 'POST /sync/start',
                    'status': 'GET /sync/status',
                    'stats': 'GET /sync/stats',
                    'stop': 'POST /sync/stop',
                    'retry_failed': 'POST /sync/retry-failed',
                    'history': 'GET /sync/history',
                    'config': 'GET/PUT /sync/config',
                    'clear_state': 'POST /sync/clear-state'
                },
                'files': {
                    'scan': 'POST /files/scan',
                    'validate': 'POST /files/validate',
                    'hierarchy': 'POST /files/hierarchy',
                    'duplicates': 'POST /files/duplicates',
                    'storage_check': 'POST /files/storage-check',
                    'info': 'POST /files/info',
                    'clear_cache': 'POST /files/clear-cache'
                }
            }
        })
    
    @app.route('/health')
    def health():
        """Health check da API"""
        try:
            # Verifica configuração
            config = config_manager.get_sync_config()
            has_token = bool(config.buzzheavier_token)
            
            return jsonify({
                'status': 'healthy',
                'version': __version__,
                'config_loaded': True,
                'has_auth_token': has_token,
                'timestamp': app.config.get('START_TIME', 'unknown')
            })
        
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500
    
    @app.route('/version')
    def version():
        """Versão da API"""
        return jsonify({
            'version': __version__,
            'api_name': 'BuzzHeavier Sync API'
        })


def setup_error_handlers(app: Flask):
    """Configura handlers de erro globais"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Endpoint não encontrado',
            'message': 'Verifique a documentação da API',
            'status_code': 404
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'error': 'Método não permitido',
            'message': f'Método {request.method} não é válido para este endpoint',
            'status_code': 405
        }), 405
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Requisição inválida',
            'message': 'Verifique os parâmetros enviados',
            'status_code': 400
        }), 400
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Erro interno: {error}')
        return jsonify({
            'error': 'Erro interno do servidor',
            'message': 'Contacte o administrador se o problema persistir',
            'status_code': 500
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f'Erro não tratado: {error}', exc_info=True)
        return jsonify({
            'error': 'Erro inesperado',
            'message': 'Um erro inesperado ocorreu',
            'status_code': 500
        }), 500


def run_app(host: str = '127.0.0.1', port: int = 5000, debug: bool = False):
    """Executa a aplicação Flask"""
    
    app = create_app()
    
    # Salva timestamp de início
    from datetime import datetime
    app.config['START_TIME'] = datetime.now().isoformat()
    
    app.logger.info(f"Iniciando BuzzHeavier Sync API v{__version__}")
    app.logger.info(f"Servidor rodando em http://{host}:{port}")
    
    if debug:
        app.logger.warning("Modo DEBUG ativado - apenas para desenvolvimento!")
    
    try:
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        app.logger.info("Aplicação interrompida pelo usuário")
    except Exception as e:
        app.logger.error(f"Erro ao iniciar aplicação: {e}")


if __name__ == '__main__':
    # Configuração da linha de comando
    import argparse
    
    parser = argparse.ArgumentParser(description='BuzzHeavier Sync API')
    parser.add_argument('--host', default='127.0.0.1', help='Host para o servidor')
    parser.add_argument('--port', type=int, default=5000, help='Porta para o servidor')
    parser.add_argument('--debug', action='store_true', help='Ativa modo debug')
    
    args = parser.parse_args()
    
    run_app(host=args.host, port=args.port, debug=args.debug)