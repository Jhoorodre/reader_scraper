#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise e validação de estrutura hierárquica
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from models.sync_models import EstruturaHierarquica


class HierarchyAnalyzer:
    """Analisador de estrutura hierárquica de arquivos"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_file_path(self, file_path: str, root_path: str) -> Optional[EstruturaHierarquica]:
        """
        Analisa caminho do arquivo e extrai estrutura hierárquica
        
        Args:
            file_path: Caminho completo do arquivo
            root_path: Caminho raiz da estrutura
            
        Returns:
            EstruturaHierarquica ou None se inválida
        """
        try:
            # Normaliza caminhos
            file_path = os.path.abspath(file_path)
            root_path = os.path.abspath(root_path)
            
            # Verifica se arquivo está dentro da raiz
            if not file_path.startswith(root_path):
                self.logger.warning(f"Arquivo fora da raiz: {file_path}")
                return None
            
            # Calcula caminho relativo
            rel_path = os.path.relpath(file_path, root_path)
            path_parts = rel_path.split(os.sep)
            
            # Valida estrutura mínima (pelo menos: scan/serie/arquivo ou scan/serie/capitulo/arquivo)
            if len(path_parts) < 3:
                self.logger.warning(f"Estrutura insuficiente: {rel_path}")
                return None
            
            # Extrai componentes
            arquivo = path_parts[-1]
            
            # Detecta agregador (nome do diretório raiz)
            agregador = os.path.basename(root_path)
            
            if len(path_parts) == 3:
                # Estrutura: scan/serie/arquivo
                scan = path_parts[0]
                serie = path_parts[1]
                capitulo = ""  # Arquivo solto na série
                
            elif len(path_parts) == 4:
                # Estrutura: scan/serie/capitulo/arquivo
                scan = path_parts[0]
                serie = path_parts[1]
                capitulo = path_parts[2]
                
            else:
                # Estrutura mais profunda - usa os 3 últimos níveis
                scan = path_parts[-4] if len(path_parts) >= 4 else path_parts[0]
                serie = path_parts[-3] if len(path_parts) >= 3 else path_parts[1]
                capitulo = path_parts[-2]
            
            # Valida componentes
            if not all([agregador, scan, serie, arquivo]):
                self.logger.warning(f"Componentes inválidos em: {rel_path}")
                return None
            
            return EstruturaHierarquica(
                agregador=agregador,
                scan=scan,
                serie=serie,
                capitulo=capitulo,
                arquivo=arquivo,
                caminho_local=file_path,
                caminho_relativo=rel_path
            )
        
        except Exception as e:
            self.logger.error(f"Erro ao analisar {file_path}: {e}")
            return None
    
    def validate_hierarchy_structure(self, root_path: str) -> Dict[str, Any]:
        """
        Valida estrutura hierárquica completa do diretório
        
        Args:
            root_path: Caminho raiz para validação
            
        Returns:
            Dicionário com resultado da validação
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {
                'total_files': 0,
                'valid_files': 0,
                'scans': set(),
                'series': set(),
                'capitulos': set()
            }
        }
        
        if not os.path.exists(root_path):
            result['valid'] = False
            result['errors'].append(f"Caminho não existe: {root_path}")
            return result
        
        if not os.path.isdir(root_path):
            result['valid'] = False
            result['errors'].append(f"Caminho não é um diretório: {root_path}")
            return result
        
        # Analisa estrutura
        for root, dirs, files in os.walk(root_path):
            for file in files:
                file_path = os.path.join(root, file)
                result['stats']['total_files'] += 1
                
                # Analisa arquivo
                estrutura = self.analyze_file_path(file_path, root_path)
                
                if estrutura:
                    result['stats']['valid_files'] += 1
                    result['stats']['scans'].add(estrutura.scan)
                    result['stats']['series'].add(f"{estrutura.scan}/{estrutura.serie}")
                    
                    if estrutura.capitulo:
                        result['stats']['capitulos'].add(
                            f"{estrutura.scan}/{estrutura.serie}/{estrutura.capitulo}"
                        )
                else:
                    result['warnings'].append(f"Arquivo com estrutura inválida: {file_path}")
        
        # Adiciona contagens
        result['stats']['total_scans'] = len(result['stats']['scans'])
        result['stats']['total_series'] = len(result['stats']['series'])
        result['stats']['total_capitulos'] = len(result['stats']['capitulos'])
        
        # Converte sets para listas para serialização
        result['stats']['scans'] = list(result['stats']['scans'])
        result['stats']['series'] = list(result['stats']['series'])
        result['stats']['capitulos'] = list(result['stats']['capitulos'])
        
        # Validações adicionais
        if result['stats']['valid_files'] == 0:
            result['errors'].append("Nenhum arquivo válido encontrado")
            result['valid'] = False
        
        if len(result['stats']['scans']) == 0:
            result['errors'].append("Nenhum scan detectado")
            result['valid'] = False
        
        return result
    
    def suggest_hierarchy_fix(self, file_path: str, root_path: str) -> Optional[str]:
        """
        Sugere correção para arquivo com hierarquia inválida
        
        Args:
            file_path: Caminho do arquivo problema
            root_path: Caminho raiz
            
        Returns:
            Sugestão de novo caminho ou None
        """
        try:
            rel_path = os.path.relpath(file_path, root_path)
            path_parts = rel_path.split(os.sep)
            arquivo = path_parts[-1]
            
            # Se tem apenas 1 ou 2 partes, sugere estrutura mínima
            if len(path_parts) < 3:
                scan_sugerido = path_parts[0] if len(path_parts) > 1 else "Unknown_Scan"
                serie_sugerida = "Unknown_Series"
                
                novo_caminho = os.path.join(root_path, scan_sugerido, serie_sugerida, arquivo)
                return novo_caminho
            
            return None
        
        except Exception as e:
            self.logger.error(f"Erro ao sugerir correção para {file_path}: {e}")
            return None
    
    def group_by_hierarchy(self, estruturas: List[EstruturaHierarquica]) -> Dict[str, List[EstruturaHierarquica]]:
        """
        Agrupa estruturas por diferentes níveis hierárquicos
        
        Args:
            estruturas: Lista de estruturas
            
        Returns:
            Dicionário com agrupamentos
        """
        groups = {
            'por_scan': {},
            'por_serie': {},
            'por_capitulo': {}
        }
        
        for estrutura in estruturas:
            # Por scan
            scan_key = estrutura.scan
            if scan_key not in groups['por_scan']:
                groups['por_scan'][scan_key] = []
            groups['por_scan'][scan_key].append(estrutura)
            
            # Por série
            serie_key = f"{estrutura.scan}/{estrutura.serie}"
            if serie_key not in groups['por_serie']:
                groups['por_serie'][serie_key] = []
            groups['por_serie'][serie_key].append(estrutura)
            
            # Por capítulo (se existe)
            if estrutura.capitulo:
                capitulo_key = f"{estrutura.scan}/{estrutura.serie}/{estrutura.capitulo}"
                if capitulo_key not in groups['por_capitulo']:
                    groups['por_capitulo'][capitulo_key] = []
                groups['por_capitulo'][capitulo_key].append(estrutura)
        
        return groups
    
    def detect_agregador(self, root_path: str) -> str:
        """Detecta nome do agregador baseado no caminho"""
        if not os.path.exists(root_path):
            raise FileNotFoundError(f"Caminho não encontrado: {root_path}")
        
        if not os.path.isdir(root_path):
            raise NotADirectoryError(f"Caminho não é um diretório: {root_path}")
        
        agregador = os.path.basename(root_path)
        
        if not agregador:
            raise ValueError(f"Não foi possível determinar nome do agregador: {root_path}")
        
        return agregador