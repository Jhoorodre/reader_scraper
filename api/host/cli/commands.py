#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comandos CLI para uso em linha de comando
"""

import sys
import argparse
import logging
import json
from typing import Optional, Dict, Any

from services.sync.manager import SyncManager
from services.file.scanner import FileScanner
from models.sync_models import SyncConfig
from utils.config import config_manager


class CLICommands:
    """Comandos CLI para automação e scripts"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sync(self, path: str, token: Optional[str] = None, 
             max_uploads: int = 5, retry_attempts: int = 3, 
             timeout: int = 30, quiet: bool = False) -> int:
        """
        Comando de sincronização
        
        Args:
            path: Caminho do diretório
            token: Token BuzzHeavier (opcional se já configurado)
            max_uploads: Upload simultâneos
            retry_attempts: Tentativas de retry
            timeout: Timeout em segundos
            quiet: Modo silencioso
            
        Returns:
            0 para sucesso, 1 para erro
        """
        try:
            # Configura logging
            if quiet:
                logging.basicConfig(level=logging.ERROR)
            else:
                logging.basicConfig(level=logging.INFO, 
                                  format='%(asctime)s - %(levelname)s - %(message)s')
            
            # Obtém configuração
            config = config_manager.get_sync_config()
            
            # Atualiza com parâmetros fornecidos
            if token:
                config.buzzheavier_token = token
            config.max_concurrent_uploads = max_uploads
            config.retry_attempts = retry_attempts
            config.timeout_seconds = timeout
            
            if not config.buzzheavier_token:
                print("❌ Token BuzzHeavier obrigatório", file=sys.stderr)
                return 1
            
            if not quiet:
                print(f"🚀 Iniciando sincronização: {path}")
                print(f"⚙️ Configuração: {max_uploads} uploads, {retry_attempts} tentativas")
            
            # Executa sincronização
            with SyncManager(config) as sync_manager:
                result = sync_manager.start_sync(path)
                
                if result['success']:
                    stats = result['stats']
                    if not quiet:
                        print(f"✅ Sincronização concluída!")
                        print(f"📊 Uploaded: {stats['uploaded_files']}, "
                              f"Pulados: {stats['skipped_files']}, "
                              f"Falhas: {stats['failed_files']}")
                    return 0
                else:
                    print(f"❌ Erro: {result['error']}", file=sys.stderr)
                    return 1
        
        except Exception as e:
            print(f"❌ Erro inesperado: {e}", file=sys.stderr)
            self.logger.error(f"Erro no comando sync: {e}", exc_info=True)
            return 1
    
    def scan(self, path: str, format_output: str = 'text', 
             show_sample: bool = False) -> int:
        """
        Comando de escaneamento
        
        Args:
            path: Caminho do diretório
            format_output: Formato de saída (text, json)
            show_sample: Mostrar amostra de arquivos
            
        Returns:
            0 para sucesso, 1 para erro
        """
        try:
            scanner = FileScanner()
            
            # Escaneia diretório
            directory_structure = scanner.scan_directory(path)
            valid_structures = scanner.find_valid_files(path)
            
            if format_output == 'json':
                result = {
                    'path': directory_structure.root_path,
                    'total_files': directory_structure.total_files,
                    'valid_files': len(valid_structures),
                    'total_size': directory_structure.total_size,
                    'files_by_extension': directory_structure.files_by_extension,
                    'hierarchy_levels': directory_structure.hierarchy_levels
                }
                
                if show_sample and valid_structures:
                    result['sample_files'] = [
                        {
                            'agregador': s.agregador,
                            'scan': s.scan,
                            'serie': s.serie,
                            'capitulo': s.capitulo,
                            'arquivo': s.arquivo,
                            'caminho_remoto': s.get_caminho_remoto()
                        }
                        for s in valid_structures[:10]
                    ]
                
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            else:  # text format
                print(f"📁 Diretório: {directory_structure.root_path}")
                print(f"📄 Total de arquivos: {directory_structure.total_files}")
                print(f"✅ Arquivos válidos: {len(valid_structures)}")
                print(f"💾 Tamanho total: {self._format_size(directory_structure.total_size)}")
                print(f"📂 Diretórios: {len(directory_structure.directories)}")
                
                if directory_structure.files_by_extension:
                    print("\n📋 Extensões:")
                    for ext, count in directory_structure.files_by_extension.items():
                        print(f"   {ext}: {count}")
                
                print(f"\n🗂️ Hierarquia: {' > '.join(directory_structure.hierarchy_levels)}")
                
                if show_sample and valid_structures:
                    print(f"\n📋 Amostra (primeiros 10):")
                    for i, s in enumerate(valid_structures[:10], 1):
                        print(f"  {i:2d}. {s.get_caminho_remoto()}/{s.arquivo}")
            
            return 0
        
        except Exception as e:
            print(f"❌ Erro no scan: {e}", file=sys.stderr)
            return 1
    
    def status(self, format_output: str = 'text') -> int:
        """
        Comando de status
        
        Args:
            format_output: Formato de saída (text, json)
            
        Returns:
            0 para sucesso, 1 para erro
        """
        try:
            config = config_manager.get_sync_config()
            
            with SyncManager(config) as sync_manager:
                status = sync_manager.get_status()
                stats = sync_manager.stats_manager.get_current_stats()
                failed_files = sync_manager.state_manager.get_failed_files()
                
                if format_output == 'json':
                    result = {
                        'status': status,
                        'stats': stats,
                        'failed_files_count': len(failed_files),
                        'has_token': bool(config.buzzheavier_token)
                    }
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                
                else:  # text format
                    print("📊 STATUS DO SISTEMA")
                    print("=" * 30)
                    
                    # Status de execução
                    if status['is_running']:
                        print("🔄 Status: EM EXECUÇÃO")
                        if status['current_operation']:
                            print(f"⚙️ Operação: {status['current_operation']}")
                    else:
                        print("⏸️ Status: PARADO")
                    
                    # Configuração
                    print(f"\n⚙️ CONFIGURAÇÃO")
                    print(f"🔑 Token: {'✅ Configurado' if config.buzzheavier_token else '❌ Não configurado'}")
                    print(f"🔄 Uploads simultâneos: {config.max_concurrent_uploads}")
                    print(f"🔁 Tentativas: {config.retry_attempts}")
                    print(f"⏱️ Timeout: {config.timeout_seconds}s")
                    
                    # Estatísticas
                    print(f"\n📊 ESTATÍSTICAS")
                    print(f"📄 Total: {stats['total_files']}")
                    print(f"✅ Uploaded: {stats['uploaded_files']}")
                    print(f"⏭️ Pulados: {stats['skipped_files']}")
                    print(f"❌ Falhas: {stats['failed_files']}")
                    
                    if stats['progress_percent'] > 0:
                        print(f"📈 Progresso: {stats['progress_percent']:.1f}%")
                    
                    if stats['elapsed_seconds'] > 0:
                        print(f"⏱️ Tempo: {self._format_duration(stats['elapsed_seconds'])}")
                    
                    # Arquivos com falha
                    if failed_files:
                        print(f"\n❌ FALHAS PENDENTES: {len(failed_files)}")
            
            return 0
        
        except Exception as e:
            print(f"❌ Erro ao obter status: {e}", file=sys.stderr)
            return 1
    
    def retry_failed(self, quiet: bool = False) -> int:
        """
        Comando para reprocessar falhas
        
        Args:
            quiet: Modo silencioso
            
        Returns:
            0 para sucesso, 1 para erro
        """
        try:
            config = config_manager.get_sync_config()
            
            if not config.buzzheavier_token:
                print("❌ Token BuzzHeavier obrigatório", file=sys.stderr)
                return 1
            
            with SyncManager(config) as sync_manager:
                failed_files = sync_manager.state_manager.get_failed_files()
                
                if not failed_files:
                    if not quiet:
                        print("✅ Nenhum arquivo para reprocessar")
                    return 0
                
                if not quiet:
                    print(f"🔄 Reprocessando {len(failed_files)} arquivos...")
                
                result = sync_manager.retry_failed_files()
                
                if result['success']:
                    upload_result = result.get('result', {})
                    if not quiet:
                        print(f"✅ Reprocessamento concluído!")
                        print(f"📊 Uploaded: {upload_result.get('uploaded', 0)}, "
                              f"Pulados: {upload_result.get('skipped', 0)}, "
                              f"Falhas: {upload_result.get('failed', 0)}")
                    return 0
                else:
                    print(f"❌ Erro: {result['error']}", file=sys.stderr)
                    return 1
        
        except Exception as e:
            print(f"❌ Erro no reprocessamento: {e}", file=sys.stderr)
            return 1
    
    def config(self, action: str, key: Optional[str] = None, 
               value: Optional[str] = None) -> int:
        """
        Comando de configuração
        
        Args:
            action: show, set, get
            key: Chave da configuração
            value: Valor (para set)
            
        Returns:
            0 para sucesso, 1 para erro
        """
        try:
            config = config_manager.get_sync_config()
            
            if action == 'show':
                print("⚙️ CONFIGURAÇÃO ATUAL")
                print("=" * 25)
                print(f"🔑 Token: {'✅ Configurado' if config.buzzheavier_token else '❌ Não configurado'}")
                print(f"🔄 max_concurrent_uploads: {config.max_concurrent_uploads}")
                print(f"🔁 retry_attempts: {config.retry_attempts}")
                print(f"⏱️ timeout_seconds: {config.timeout_seconds}")
                print(f"📦 chunk_size: {config.chunk_size}")
                print(f"🔗 auto_consolidate: {config.auto_consolidate}")
                
            elif action == 'get':
                if not key:
                    print("❌ Chave obrigatória para 'get'", file=sys.stderr)
                    return 1
                
                if hasattr(config, key):
                    value = getattr(config, key)
                    if key == 'buzzheavier_token' and value:
                        print("✅ Configurado")
                    else:
                        print(value)
                else:
                    print(f"❌ Chave desconhecida: {key}", file=sys.stderr)
                    return 1
                
            elif action == 'set':
                if not key or value is None:
                    print("❌ Chave e valor obrigatórios para 'set'", file=sys.stderr)
                    return 1
                
                if key == 'buzzheavier_token':
                    config.buzzheavier_token = value
                    print("✅ Token configurado")
                elif key == 'max_concurrent_uploads':
                    config.max_concurrent_uploads = int(value)
                    print(f"✅ max_concurrent_uploads = {value}")
                elif key == 'retry_attempts':
                    config.retry_attempts = int(value)
                    print(f"✅ retry_attempts = {value}")
                elif key == 'timeout_seconds':
                    config.timeout_seconds = int(value)
                    print(f"✅ timeout_seconds = {value}")
                elif key == 'chunk_size':
                    config.chunk_size = int(value)
                    print(f"✅ chunk_size = {value}")
                elif key == 'auto_consolidate':
                    config.auto_consolidate = value.lower() in ['true', '1', 'yes', 'on']
                    print(f"✅ auto_consolidate = {config.auto_consolidate}")
                else:
                    print(f"❌ Chave desconhecida: {key}", file=sys.stderr)
                    return 1
                
                # Salva configuração
                config_manager.update_sync_config(config)
                
            else:
                print(f"❌ Ação desconhecida: {action}", file=sys.stderr)
                return 1
            
            return 0
        
        except ValueError as e:
            print(f"❌ Valor inválido: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"❌ Erro na configuração: {e}", file=sys.stderr)
            return 1
    
    def _format_size(self, bytes_size: int) -> str:
        """Formata tamanho em texto legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
    
    def _format_duration(self, seconds: float) -> str:
        """Formata duração em texto legível"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


def main():
    """Função principal para comandos CLI"""
    parser = argparse.ArgumentParser(
        description='BuzzHeavier Sync CLI Commands',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s sync /path/to/manga --token YOUR_TOKEN
  %(prog)s scan /path/to/manga --json
  %(prog)s status
  %(prog)s retry-failed
  %(prog)s config show
  %(prog)s config set max_concurrent_uploads 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # Comando sync
    sync_parser = subparsers.add_parser('sync', help='Sincronizar diretório')
    sync_parser.add_argument('path', help='Caminho do diretório')
    sync_parser.add_argument('--token', help='Token BuzzHeavier')
    sync_parser.add_argument('--max-uploads', type=int, default=5, help='Uploads simultâneos (padrão: 5)')
    sync_parser.add_argument('--retry-attempts', type=int, default=3, help='Tentativas de retry (padrão: 3)')
    sync_parser.add_argument('--timeout', type=int, default=30, help='Timeout em segundos (padrão: 30)')
    sync_parser.add_argument('--quiet', action='store_true', help='Modo silencioso')
    
    # Comando scan
    scan_parser = subparsers.add_parser('scan', help='Escanear diretório')
    scan_parser.add_argument('path', help='Caminho do diretório')
    scan_parser.add_argument('--json', action='store_true', help='Saída em JSON')
    scan_parser.add_argument('--sample', action='store_true', help='Mostrar amostra de arquivos')
    
    # Comando status
    status_parser = subparsers.add_parser('status', help='Status do sistema')
    status_parser.add_argument('--json', action='store_true', help='Saída em JSON')
    
    # Comando retry-failed
    retry_parser = subparsers.add_parser('retry-failed', help='Reprocessar falhas')
    retry_parser.add_argument('--quiet', action='store_true', help='Modo silencioso')
    
    # Comando config
    config_parser = subparsers.add_parser('config', help='Configuração')
    config_parser.add_argument('action', choices=['show', 'get', 'set'], help='Ação')
    config_parser.add_argument('key', nargs='?', help='Chave da configuração')
    config_parser.add_argument('value', nargs='?', help='Valor (para set)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = CLICommands()
    
    try:
        if args.command == 'sync':
            return cli.sync(
                path=args.path,
                token=args.token,
                max_uploads=args.max_uploads,
                retry_attempts=args.retry_attempts,
                timeout=args.timeout,
                quiet=args.quiet
            )
        
        elif args.command == 'scan':
            return cli.scan(
                path=args.path,
                format_output='json' if args.json else 'text',
                show_sample=args.sample
            )
        
        elif args.command == 'status':
            return cli.status(
                format_output='json' if args.json else 'text'
            )
        
        elif args.command == 'retry-failed':
            return cli.retry_failed(quiet=args.quiet)
        
        elif args.command == 'config':
            return cli.config(
                action=args.action,
                key=args.key,
                value=args.value
            )
        
        else:
            print(f"❌ Comando desconhecido: {args.command}", file=sys.stderr)
            return 1
    
    except KeyboardInterrupt:
        print("\n🚫 Interrompido pelo usuário", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"❌ Erro inesperado: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())