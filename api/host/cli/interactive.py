#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Menu interativo CLI usando serviços modulares
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

from services.sync.manager import SyncManager
from services.file.scanner import FileScanner
from services.file.hierarchy import HierarchyAnalyzer
from models.sync_models import SyncConfig
from utils.config import config_manager
from utils.progress import ProgressBar, StatusDisplay


class InteractiveCLI:
    """Interface CLI interativa para BuzzHeavier Sync"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sync_manager: Optional[SyncManager] = None
        self.file_scanner = FileScanner()
        self.hierarchy_analyzer = HierarchyAnalyzer()
        
        # Estado da sessão
        self.current_path: Optional[str] = None
        self.last_scan_result = None
    
    def run(self):
        """Executa o menu interativo principal"""
        try:
            self._show_header()
            
            while True:
                try:
                    self._show_main_menu()
                    choice = input("\n🎯 Escolha uma opção: ").strip()
                    
                    if not choice:
                        continue
                    
                    if choice == '0':
                        self._show_goodbye()
                        break
                    
                    self._handle_main_menu_choice(choice)
                    
                except KeyboardInterrupt:
                    print("\n\n👋 Interrompido pelo usuário. Saindo...")
                    break
                except EOFError:
                    print("\n\n👋 Entrada finalizada. Saindo...")
                    break
                except Exception as e:
                    print(f"\n❌ Erro inesperado: {e}")
                    self.logger.error(f"Erro no menu principal: {e}", exc_info=True)
                    input("\nPressione Enter para continuar...")
        
        finally:
            self._cleanup()
    
    def _show_header(self):
        """Exibe cabeçalho da aplicação"""
        print("=" * 70)
        print("🚀 BuzzHeavier Sync Enhanced - Versão 2.0 (Modular)")
        print("📊 Sistema de Sincronização com BuzzHeavier")
        print("=" * 70)
        
        # Verifica configuração
        try:
            config = config_manager.get_sync_config()
            if config.buzzheavier_token:
                print("✅ Token configurado")
            else:
                print("⚠️  Token não configurado - configure antes de sincronizar")
        except Exception as e:
            print(f"⚠️  Erro na configuração: {e}")
        
        print()
    
    def _show_main_menu(self):
        """Exibe menu principal"""
        print("\n" + "─" * 50)
        print("📋 MENU PRINCIPAL")
        print("─" * 50)
        
        # Informações de contexto
        if self.current_path:
            print(f"📁 Diretório atual: {self.current_path}")
        
        if self.last_scan_result:
            files_count = self.last_scan_result.get('valid_files_count', 0)
            print(f"📊 Último scan: {files_count} arquivos válidos")
        
        print()
        print("1️⃣  📁 Selecionar diretório")
        print("2️⃣  🔍 Escanear estrutura de arquivos")
        print("3️⃣  ✅ Validar hierarquia")
        print("4️⃣  🚀 Iniciar sincronização")
        print("5️⃣  📊 Ver estatísticas")
        print("6️⃣  🔄 Reprocessar falhas")
        print("7️⃣  ⚙️  Configurações")
        print("8️⃣  🧹 Limpar cache/estado")
        print("9️⃣  ℹ️  Informações do sistema")
        print("0️⃣  🚪 Sair")
    
    def _handle_main_menu_choice(self, choice: str):
        """Processa escolha do menu principal"""
        handlers = {
            '1': self._select_directory,
            '2': self._scan_directory,
            '3': self._validate_hierarchy,
            '4': self._start_sync,
            '5': self._show_statistics,
            '6': self._retry_failed,
            '7': self._configuration_menu,
            '8': self._cleanup_menu,
            '9': self._system_info
        }
        
        handler = handlers.get(choice)
        if handler:
            try:
                handler()
            except Exception as e:
                print(f"\n❌ Erro ao executar opção: {e}")
                self.logger.error(f"Erro no handler {choice}: {e}", exc_info=True)
                input("\nPressione Enter para continuar...")
        else:
            print(f"\n❌ Opção inválida: {choice}")
    
    def _select_directory(self):
        """Seleciona diretório para sincronização"""
        print("\n📁 SELEÇÃO DE DIRETÓRIO")
        print("─" * 30)
        
        # Mostra sugestões baseadas no histórico
        last_path = config_manager.get('sync', 'last_root_path', fallback=None)
        if last_path and os.path.exists(last_path):
            print(f"💡 Último usado: {last_path}")
            use_last = input("Usar último diretório? (s/N): ").strip().lower()
            if use_last in ['s', 'sim', 'y', 'yes']:
                self.current_path = last_path
                print(f"✅ Diretório selecionado: {self.current_path}")
                return
        
        # Solicita novo caminho
        while True:
            path = input("📂 Digite o caminho do diretório: ").strip()
            
            if not path:
                print("❌ Caminho não pode estar vazio")
                continue
            
            # Expande ~ e variáveis de ambiente
            path = os.path.expanduser(path)
            path = os.path.expandvars(path)
            
            if not os.path.exists(path):
                print(f"❌ Caminho não encontrado: {path}")
                retry = input("Tentar outro caminho? (s/N): ").strip().lower()
                if retry not in ['s', 'sim', 'y', 'yes']:
                    return
                continue
            
            if not os.path.isdir(path):
                print(f"❌ Caminho não é um diretório: {path}")
                continue
            
            self.current_path = os.path.abspath(path)
            print(f"✅ Diretório selecionado: {self.current_path}")
            
            # Salva no histórico
            config_manager.set('sync', 'last_root_path', self.current_path)
            config_manager.save_config()
            break
    
    def _scan_directory(self):
        """Escaneia estrutura do diretório"""
        if not self.current_path:
            print("\n❌ Nenhum diretório selecionado. Use a opção 1 primeiro.")
            return
        
        print("\n🔍 ESCANEAMENTO DE ARQUIVOS")
        print("─" * 30)
        
        status_display = StatusDisplay("Escaneando diretório")
        
        try:
            # Escaneia diretório
            directory_structure = self.file_scanner.scan_directory(self.current_path)
            status_display.update("Analisando arquivos válidos")
            
            # Encontra arquivos válidos
            valid_structures = self.file_scanner.find_valid_files(self.current_path)
            
            status_display.finish("Scan completo")
            
            # Exibe resultados
            print(f"\n📊 RESULTADOS DO SCAN")
            print(f"📁 Diretório: {directory_structure.root_path}")
            print(f"📄 Total de arquivos: {directory_structure.total_files}")
            print(f"✅ Arquivos válidos: {len(valid_structures)}")
            print(f"💾 Tamanho total: {self._format_size(directory_structure.total_size)}")
            print(f"📂 Diretórios: {len(directory_structure.directories)}")
            
            # Extensões encontradas
            if directory_structure.files_by_extension:
                print(f"\n📋 Extensões encontradas:")
                for ext, count in directory_structure.files_by_extension.items():
                    print(f"   {ext}: {count} arquivos")
            
            # Níveis hierárquicos
            print(f"\n🗂️  Estrutura hierárquica: {' > '.join(directory_structure.hierarchy_levels)}")
            
            # Salva resultado
            self.last_scan_result = {
                'directory_structure': directory_structure,
                'valid_structures': valid_structures,
                'valid_files_count': len(valid_structures)
            }
            
            # Pergunta se quer ver detalhes
            if valid_structures and len(valid_structures) > 0:
                show_sample = input(f"\nVer amostra de arquivos válidos? (s/N): ").strip().lower()
                if show_sample in ['s', 'sim', 'y', 'yes']:
                    self._show_files_sample(valid_structures[:10])
        
        except Exception as e:
            status_display.finish(f"Erro no scan: {e}")
            print(f"❌ Erro durante o scan: {e}")
    
    def _validate_hierarchy(self):
        """Valida estrutura hierárquica"""
        if not self.current_path:
            print("\n❌ Nenhum diretório selecionado. Use a opção 1 primeiro.")
            return
        
        print("\n✅ VALIDAÇÃO DE HIERARQUIA")
        print("─" * 30)
        
        try:
            # Valida estrutura
            result = self.hierarchy_analyzer.validate_hierarchy_structure(self.current_path)
            
            print(f"🎯 Resultado: {'✅ VÁLIDA' if result['valid'] else '❌ INVÁLIDA'}")
            
            # Estatísticas
            stats = result['stats']
            print(f"\n📊 Estatísticas:")
            print(f"   📁 Total de arquivos: {stats['total_files']}")
            print(f"   ✅ Arquivos válidos: {stats['valid_files']}")
            print(f"   📂 Scans encontrados: {stats['total_scans']}")
            print(f"   📖 Séries encontradas: {stats['total_series']}")
            print(f"   📚 Capítulos encontrados: {stats['total_capitulos']}")
            
            # Scans detectados
            if stats['scans']:
                print(f"\n📂 Scans detectados:")
                for scan in stats['scans'][:5]:  # Mostra até 5
                    print(f"   • {scan}")
                if len(stats['scans']) > 5:
                    print(f"   ... e mais {len(stats['scans']) - 5}")
            
            # Erros
            if result['errors']:
                print(f"\n❌ Erros encontrados ({len(result['errors'])}):")
                for error in result['errors'][:5]:  # Mostra até 5
                    print(f"   • {error}")
                if len(result['errors']) > 5:
                    print(f"   ... e mais {len(result['errors']) - 5}")
            
            # Avisos
            if result['warnings']:
                print(f"\n⚠️  Avisos ({len(result['warnings'])}):")
                for warning in result['warnings'][:3]:  # Mostra até 3
                    print(f"   • {warning}")
                if len(result['warnings']) > 3:
                    print(f"   ... e mais {len(result['warnings']) - 3}")
        
        except Exception as e:
            print(f"❌ Erro na validação: {e}")
    
    def _start_sync(self):
        """Inicia sincronização"""
        if not self.current_path:
            print("\n❌ Nenhum diretório selecionado. Use a opção 1 primeiro.")
            return
        
        print("\n🚀 INICIAR SINCRONIZAÇÃO")
        print("─" * 30)
        
        try:
            # Verifica configuração
            config = config_manager.get_sync_config()
            if not config.buzzheavier_token:
                print("❌ Token BuzzHeavier não configurado. Configure primeiro (opção 7).")
                return
            
            # Confirma ação
            print(f"📁 Diretório: {self.current_path}")
            confirm = input("Confirmar início da sincronização? (s/N): ").strip().lower()
            if confirm not in ['s', 'sim', 'y', 'yes']:
                print("🚫 Sincronização cancelada.")
                return
            
            # Cria sync manager se necessário
            if not self.sync_manager:
                self.sync_manager = SyncManager(config)
            
            # Callback de progresso
            def progress_callback(operation: str, current: int, total: int):
                if total > 0:
                    percent = (current / total) * 100
                    print(f"\r🔄 {operation}: {percent:.1f}% ({current}/{total})", end='', flush=True)
            
            print("🚀 Iniciando sincronização...")
            
            # Executa sincronização
            result = self.sync_manager.start_sync(self.current_path, progress_callback)
            
            print()  # Nova linha
            
            # Mostra resultado
            if result['success']:
                stats = result['stats']
                print("\n✅ SINCRONIZAÇÃO CONCLUÍDA")
                print(f"📊 Arquivos processados: {stats['processed_files']}")
                print(f"⬆️  Uploads: {stats['uploaded_files']}")
                print(f"⏭️  Pulados: {stats['skipped_files']}")
                print(f"❌ Falhas: {stats['failed_files']}")
                print(f"⏱️  Tempo: {self._format_duration(stats['elapsed_seconds'])}")
                
                if stats['avg_upload_speed'] > 0:
                    print(f"🚀 Velocidade média: {self._format_speed(stats['avg_upload_speed'])}")
            else:
                print(f"\n❌ FALHA NA SINCRONIZAÇÃO")
                print(f"Erro: {result['error']}")
                if 'details' in result:
                    print(f"Detalhes: {result['details']}")
        
        except Exception as e:
            print(f"\n❌ Erro durante sincronização: {e}")
            self.logger.error(f"Erro na sincronização: {e}", exc_info=True)
    
    def _show_statistics(self):
        """Mostra estatísticas"""
        print("\n📊 ESTATÍSTICAS")
        print("─" * 20)
        
        if not self.sync_manager:
            config = config_manager.get_sync_config()
            self.sync_manager = SyncManager(config)
        
        # Estatísticas atuais
        current_stats = self.sync_manager.stats_manager.get_current_stats()
        print("📈 Sessão atual:")
        print(f"   Total: {current_stats['total_files']} arquivos")
        print(f"   ✅ Uploaded: {current_stats['uploaded_files']}")
        print(f"   ⏭️  Pulados: {current_stats['skipped_files']}")
        print(f"   ❌ Falhas: {current_stats['failed_files']}")
        
        if current_stats['elapsed_seconds'] > 0:
            print(f"   ⏱️  Tempo: {self._format_duration(current_stats['elapsed_seconds'])}")
        
        # Estado
        failed_files = self.sync_manager.state_manager.get_failed_files()
        successful_files = self.sync_manager.state_manager.get_successful_files()
        
        print(f"\n💾 Estado persistente:")
        print(f"   ❌ Arquivos com falha: {len(failed_files)}")
        print(f"   ✅ Arquivos enviados: {len(successful_files)}")
        
        # Histórico
        history = self.sync_manager.state_manager.get_sync_history()
        if history:
            print(f"\n📚 Histórico: {len(history)} sincronizações")
            
            # Mostra estatísticas da última
            last_sync = history[-1]
            print(f"   Última: {last_sync.get('uploaded_files', 0)} uploads, "
                  f"{last_sync.get('failed_files', 0)} falhas")
    
    def _retry_failed(self):
        """Reprocessa arquivos com falha"""
        print("\n🔄 REPROCESSAR FALHAS")
        print("─" * 25)
        
        if not self.sync_manager:
            config = config_manager.get_sync_config()
            self.sync_manager = SyncManager(config)
        
        failed_files = self.sync_manager.state_manager.get_failed_files()
        
        if not failed_files:
            print("✅ Nenhum arquivo com falha para reprocessar.")
            return
        
        print(f"❌ Encontrados {len(failed_files)} arquivos com falha")
        
        # Mostra amostra
        print("📋 Arquivos (amostra):")
        for file_path in failed_files[:5]:
            print(f"   • {os.path.basename(file_path)}")
        if len(failed_files) > 5:
            print(f"   ... e mais {len(failed_files) - 5}")
        
        # Confirma reprocessamento
        confirm = input(f"\nReprocessar {len(failed_files)} arquivos? (s/N): ").strip().lower()
        if confirm not in ['s', 'sim', 'y', 'yes']:
            print("🚫 Reprocessamento cancelado.")
            return
        
        try:
            print("🔄 Iniciando reprocessamento...")
            result = self.sync_manager.retry_failed_files()
            
            if result['success']:
                upload_result = result.get('result', {})
                print("\n✅ REPROCESSAMENTO CONCLUÍDO")
                print(f"⬆️  Uploads: {upload_result.get('uploaded', 0)}")
                print(f"⏭️  Pulados: {upload_result.get('skipped', 0)}")
                print(f"❌ Falhas: {upload_result.get('failed', 0)}")
            else:
                print(f"\n❌ Erro no reprocessamento: {result['error']}")
        
        except Exception as e:
            print(f"\n❌ Erro durante reprocessamento: {e}")
    
    def _configuration_menu(self):
        """Menu de configurações"""
        while True:
            print("\n⚙️ CONFIGURAÇÕES")
            print("─" * 20)
            
            config = config_manager.get_sync_config()
            
            print(f"1️⃣  Token BuzzHeavier: {'✅ Configurado' if config.buzzheavier_token else '❌ Não configurado'}")
            print(f"2️⃣  Uploads simultâneos: {config.max_concurrent_uploads}")
            print(f"3️⃣  Tentativas de retry: {config.retry_attempts}")
            print(f"4️⃣  Timeout (segundos): {config.timeout_seconds}")
            print(f"5️⃣  Tamanho do chunk: {config.chunk_size}")
            print(f"6️⃣  Auto consolidação: {'✅ Ativada' if config.auto_consolidate else '❌ Desativada'}")
            print("0️⃣  🔙 Voltar")
            
            choice = input("\n🎯 Escolha uma opção: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self._configure_token()
            elif choice == '2':
                self._configure_concurrent_uploads()
            elif choice == '3':
                self._configure_retry_attempts()
            elif choice == '4':
                self._configure_timeout()
            elif choice == '5':
                self._configure_chunk_size()
            elif choice == '6':
                self._configure_auto_consolidate()
            else:
                print(f"❌ Opção inválida: {choice}")
    
    def _configure_token(self):
        """Configura token BuzzHeavier"""
        print("\n🔑 Configuração do Token")
        current_config = config_manager.get_sync_config()
        
        if current_config.buzzheavier_token:
            print("✅ Token já configurado")
            update = input("Atualizar token? (s/N): ").strip().lower()
            if update not in ['s', 'sim', 'y', 'yes']:
                return
        
        token = input("Digite o token BuzzHeavier: ").strip()
        if token:
            current_config.buzzheavier_token = token
            config_manager.update_sync_config(current_config)
            print("✅ Token configurado com sucesso")
        else:
            print("❌ Token não pode estar vazio")
    
    def _configure_concurrent_uploads(self):
        """Configura uploads simultâneos"""
        current_config = config_manager.get_sync_config()
        
        try:
            value = int(input(f"Uploads simultâneos (atual: {current_config.max_concurrent_uploads}): "))
            if 1 <= value <= 20:
                current_config.max_concurrent_uploads = value
                config_manager.update_sync_config(current_config)
                print(f"✅ Configurado para {value} uploads simultâneos")
            else:
                print("❌ Valor deve estar entre 1 e 20")
        except ValueError:
            print("❌ Valor inválido")
    
    def _configure_retry_attempts(self):
        """Configura tentativas de retry"""
        current_config = config_manager.get_sync_config()
        
        try:
            value = int(input(f"Tentativas de retry (atual: {current_config.retry_attempts}): "))
            if 1 <= value <= 10:
                current_config.retry_attempts = value
                config_manager.update_sync_config(current_config)
                print(f"✅ Configurado para {value} tentativas")
            else:
                print("❌ Valor deve estar entre 1 e 10")
        except ValueError:
            print("❌ Valor inválido")
    
    def _configure_timeout(self):
        """Configura timeout"""
        current_config = config_manager.get_sync_config()
        
        try:
            value = int(input(f"Timeout em segundos (atual: {current_config.timeout_seconds}): "))
            if 10 <= value <= 300:
                current_config.timeout_seconds = value
                config_manager.update_sync_config(current_config)
                print(f"✅ Timeout configurado para {value} segundos")
            else:
                print("❌ Valor deve estar entre 10 e 300 segundos")
        except ValueError:
            print("❌ Valor inválido")
    
    def _configure_chunk_size(self):
        """Configura tamanho do chunk"""
        current_config = config_manager.get_sync_config()
        
        try:
            value = int(input(f"Tamanho do chunk (atual: {current_config.chunk_size}): "))
            if 1024 <= value <= 1048576:  # 1KB a 1MB
                current_config.chunk_size = value
                config_manager.update_sync_config(current_config)
                print(f"✅ Chunk configurado para {value} bytes")
            else:
                print("❌ Valor deve estar entre 1024 e 1048576 bytes")
        except ValueError:
            print("❌ Valor inválido")
    
    def _configure_auto_consolidate(self):
        """Configura auto consolidação"""
        current_config = config_manager.get_sync_config()
        
        toggle = input(f"Auto consolidação ({'ativada' if current_config.auto_consolidate else 'desativada'}). Alternar? (s/N): ").strip().lower()
        if toggle in ['s', 'sim', 'y', 'yes']:
            current_config.auto_consolidate = not current_config.auto_consolidate
            config_manager.update_sync_config(current_config)
            status = 'ativada' if current_config.auto_consolidate else 'desativada'
            print(f"✅ Auto consolidação {status}")
    
    def _cleanup_menu(self):
        """Menu de limpeza"""
        while True:
            print("\n🧹 LIMPEZA")
            print("─" * 15)
            
            if not self.sync_manager:
                config = config_manager.get_sync_config()
                self.sync_manager = SyncManager(config)
            
            failed_count = len(self.sync_manager.state_manager.get_failed_files())
            successful_count = len(self.sync_manager.state_manager.get_successful_files())
            
            print(f"1️⃣  Limpar arquivos com falha ({failed_count})")
            print(f"2️⃣  Limpar cache de scans")
            print(f"3️⃣  Limpar histórico de sincronizações")
            print(f"4️⃣  Limpar tudo (reset completo)")
            print("0️⃣  🔙 Voltar")
            
            choice = input("\n🎯 Escolha uma opção: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.sync_manager.state_manager.clear_failed_files()
                print("✅ Lista de falhas limpa")
            elif choice == '2':
                self.sync_manager.state_manager.clear_scan_cache()
                self.file_scanner.clear_cache()
                print("✅ Cache de scans limpo")
            elif choice == '3':
                confirm = input("Confirma limpeza do histórico? (s/N): ").strip().lower()
                if confirm in ['s', 'sim', 'y', 'yes']:
                    self.sync_manager.state_manager.get_sync_history().clear()
                    print("✅ Histórico limpo")
            elif choice == '4':
                confirm = input("⚠️ ATENÇÃO: Limpar TUDO? (s/N): ").strip().lower()
                if confirm in ['s', 'sim', 'y', 'yes']:
                    self.sync_manager.state_manager.reset_state()
                    print("✅ Estado completamente resetado")
            else:
                print(f"❌ Opção inválida: {choice}")
    
    def _system_info(self):
        """Mostra informações do sistema"""
        print("\nℹ️ INFORMAÇÕES DO SISTEMA")
        print("─" * 30)
        
        # Informações básicas
        print(f"🚀 BuzzHeavier Sync Enhanced v2.0")
        print(f"🐍 Python: {sys.version.split()[0]}")
        print(f"💻 Sistema: {os.name}")
        
        # Configuração atual
        try:
            config = config_manager.get_sync_config()
            print(f"\n⚙️ Configuração:")
            print(f"   🔑 Token: {'✅ Configurado' if config.buzzheavier_token else '❌ Não configurado'}")
            print(f"   🔄 Uploads simultâneos: {config.max_concurrent_uploads}")
            print(f"   🔁 Tentativas: {config.retry_attempts}")
            print(f"   ⏱️  Timeout: {config.timeout_seconds}s")
        except Exception as e:
            print(f"❌ Erro ao carregar configuração: {e}")
        
        # Estado do diretório atual
        if self.current_path:
            print(f"\n📁 Diretório atual:")
            print(f"   📂 Caminho: {self.current_path}")
            print(f"   ✅ Existe: {'Sim' if os.path.exists(self.current_path) else 'Não'}")
            
            if self.last_scan_result:
                files_count = self.last_scan_result.get('valid_files_count', 0)
                print(f"   📊 Arquivos válidos: {files_count}")
    
    def _show_files_sample(self, structures):
        """Mostra amostra de arquivos"""
        print(f"\n📋 Amostra de arquivos válidos:")
        for i, structure in enumerate(structures, 1):
            print(f"{i:2d}. {structure.scan}/{structure.serie}")
            if structure.capitulo:
                print(f"    📚 {structure.capitulo}/{structure.arquivo}")
            else:
                print(f"    📄 {structure.arquivo}")
    
    def _show_goodbye(self):
        """Mensagem de despedida"""
        print("\n👋 Obrigado por usar o BuzzHeavier Sync!")
        print("📊 Sessão finalizada.")
    
    def _cleanup(self):
        """Limpeza de recursos"""
        if self.sync_manager:
            try:
                self.sync_manager.cleanup()
            except Exception as e:
                self.logger.error(f"Erro na limpeza: {e}")
    
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
    
    def _format_speed(self, bytes_per_sec: float) -> str:
        """Formata velocidade em texto legível"""
        return f"{self._format_size(bytes_per_sec)}/s"


def main():
    """Função principal do CLI"""
    try:
        cli = InteractiveCLI()
        cli.run()
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        logging.error(f"Erro fatal no CLI: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()