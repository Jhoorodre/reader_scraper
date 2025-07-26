#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ponto de entrada principal para BuzzHeavier Sync
Compatível com o sync_buzzheavier.py original
"""

import sys
import os
import argparse

# Adiciona o diretório atual ao path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import interactive_main, commands_main


def main():
    """Ponto de entrada principal"""
    
    # Se executado sem argumentos ou com --interactive, abre menu interativo
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['--interactive', '-i']):
        print("🚀 BuzzHeavier Sync Enhanced - Modo Interativo")
        return interactive_main()
    
    # Se o primeiro argumento é um comando válido, executa comandos CLI
    valid_commands = ['sync', 'scan', 'status', 'retry-failed', 'config']
    if len(sys.argv) > 1 and sys.argv[1] in valid_commands:
        return commands_main()
    
    # Caso contrário, mostra ajuda
    parser = argparse.ArgumentParser(
        description='BuzzHeavier Sync Enhanced v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🎯 Modos de Uso:

1️⃣ MODO INTERATIVO (Original):
   python sync_cli.py
   python sync_cli.py --interactive

2️⃣ MODO LINHA DE COMANDO (Novo):
   python sync_cli.py sync /path/to/manga --token TOKEN
   python sync_cli.py scan /path/to/manga --json
   python sync_cli.py status
   python sync_cli.py retry-failed
   python sync_cli.py config show

3️⃣ SERVIDOR API (Novo):
   python app.py --port 5000

📚 Documentação completa: README.md
        """
    )
    
    parser.add_argument('--interactive', '-i', action='store_true', 
                       help='Abrir menu interativo')
    parser.add_argument('--version', '-v', action='version', 
                       version='BuzzHeavier Sync Enhanced v2.0')
    
    # Se chegou até aqui, parse os argumentos e mostra help
    args = parser.parse_args()
    
    if args.interactive:
        return interactive_main()
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())