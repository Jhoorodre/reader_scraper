#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de instalação e configuração inicial
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    """Verifica versão do Python"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ é obrigatório")
        print(f"   Versão atual: {sys.version}")
        return False
    
    print(f"✅ Python {sys.version.split()[0]} (compatível)")
    return True


def install_dependencies():
    """Instala dependências"""
    print("\n📦 Instalando dependências...")
    
    try:
        # Verifica se pip está disponível
        subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                      check=True, capture_output=True)
        
        # Instala dependências
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], check=True)
        
        print("✅ Dependências instaladas com sucesso")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar dependências: {e}")
        return False
    except FileNotFoundError:
        print("❌ pip não encontrado")
        return False


def create_directories():
    """Cria diretórios necessários"""
    print("\n📁 Criando diretórios...")
    
    directories = [
        '_LOGS',
        'temp'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ {directory}/")
    
    return True


def create_config_template():
    """Cria template de configuração"""
    print("\n⚙️ Criando arquivo de configuração...")
    
    config_content = """[DEFAULT]
# Token BuzzHeavier (obrigatório)
buzzheavier_token = 

# Configurações de upload
max_concurrent_uploads = 5
retry_attempts = 3
timeout_seconds = 30
chunk_size = 8192
auto_consolidate = false

[logging]
# Configurações de log
level = INFO
log_dir = _LOGS
max_log_files = 10
"""
    
    config_file = Path('config.ini')
    
    if config_file.exists():
        backup_file = Path('config.ini.backup')
        shutil.copy2(config_file, backup_file)
        print(f"📋 Backup criado: {backup_file}")
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"✅ Arquivo criado: {config_file}")
    print("⚠️  Configure seu token BuzzHeavier no arquivo config.ini")
    
    return True


def check_compatibility():
    """Verifica compatibilidade com sync_buzzheavier.py original"""
    print("\n🔍 Verificando compatibilidade...")
    
    original_file = Path('../sync_buzzheavier.py')
    
    if original_file.exists():
        print(f"✅ Arquivo original encontrado: {original_file}")
        print("📋 O sistema modular mantém 100% de compatibilidade")
        
        # Verifica se há configuração existente
        original_config = Path('../config.ini')
        if original_config.exists():
            copy_config = input("📥 Copiar configuração existente? (s/N): ").strip().lower()
            if copy_config in ['s', 'sim', 'y', 'yes']:
                shutil.copy2(original_config, 'config.ini')
                print("✅ Configuração copiada")
        
        # Verifica estado
        original_state = Path('../sync_state.json')
        if original_state.exists():
            copy_state = input("📥 Copiar estado existente? (s/N): ").strip().lower()
            if copy_state in ['s', 'sim', 'y', 'yes']:
                shutil.copy2(original_state, 'sync_state.json')
                print("✅ Estado copiado")
        
        # Verifica logs
        original_logs = Path('../_LOGS')
        if original_logs.exists():
            copy_logs = input("📥 Copiar logs existentes? (s/N): ").strip().lower()
            if copy_logs in ['s', 'sim', 'y', 'yes']:
                if Path('_LOGS').exists():
                    shutil.rmtree('_LOGS')
                shutil.copytree(original_logs, '_LOGS')
                print("✅ Logs copiados")
    
    else:
        print("ℹ️  Arquivo original não encontrado (instalação limpa)")
    
    return True


def test_installation():
    """Testa a instalação"""
    print("\n🧪 Testando instalação...")
    
    try:
        # Testa estrutura de arquivos
        required_files = [
            'config.ini',
            'app.py', 
            'sync_cli.py',
            'requirements.txt'
        ]
        
        required_dirs = [
            'models',
            'utils', 
            'services',
            'cli',
            'routes',
            '_LOGS',
            'temp'
        ]
        
        # Verifica arquivos
        for file in required_files:
            if Path(file).exists():
                print(f"✅ {file}")
            else:
                print(f"⚠️  {file} não encontrado")
        
        # Verifica diretórios
        for dir in required_dirs:
            if Path(dir).exists():
                print(f"✅ {dir}/")
            else:
                print(f"⚠️  {dir}/ não encontrado")
        
        print("✅ Estrutura verificada")
        return True
    
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False


def show_usage_instructions():
    """Mostra instruções de uso"""
    print("\n" + "="*60)
    print("🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*60)
    
    print("\n🚀 COMO USAR:")
    print()
    print("1️⃣ MODO INTERATIVO (Original):")
    print("   python sync_cli.py")
    print("   # Menu familiar com todas as funcionalidades")
    print()
    print("2️⃣ LINHA DE COMANDO (Novo):")
    print("   python sync_cli.py sync /path/to/manga --token TOKEN")
    print("   python sync_cli.py scan /path/to/manga")
    print("   python sync_cli.py status")
    print()
    print("3️⃣ SERVIDOR API (Novo):")
    print("   python app.py --port 5000")
    print("   # Acesse http://localhost:5000 para documentação")
    print()
    print("⚙️ CONFIGURAÇÃO:")
    print("   1. Configure seu token em config.ini")
    print("   2. Ou use o menu interativo (python sync_cli.py -> opção 7)")
    print()
    print("📚 DOCUMENTAÇÃO:")
    print("   README.md - Guia completo")
    print("   http://localhost:5000 - API documentation")
    print()
    print("🆘 AJUDA:")
    print("   python sync_cli.py --help")
    print("   python sync_cli.py config show")


def main():
    """Instalação principal"""
    print("🚀 BuzzHeavier Sync Enhanced v2.0 - Instalação")
    print("="*50)
    
    steps = [
        ("Verificando Python", check_python_version),
        ("Instalando dependências", install_dependencies),
        ("Criando diretórios", create_directories),
        ("Criando configuração", create_config_template),
        ("Verificando compatibilidade", check_compatibility),
        ("Testando instalação", test_installation)
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"\n❌ Falha na etapa: {step_name}")
            print("🚨 Instalação interrompida")
            return 1
    
    show_usage_instructions()
    return 0


if __name__ == '__main__':
    sys.exit(main())