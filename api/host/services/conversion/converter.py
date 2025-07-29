#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serviço de conversão integrado ao upload BuzzHeavier
"""

import os
import tempfile
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import hashlib
import time

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.utils import ImageReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from models.sync_models import EstruturaHierarquica, SyncConfig
from models.file_models import FileInfo, FileStatus


class ConversionService:
    """Serviço de conversão integrado ao processo de upload"""
    
    def __init__(self, config: SyncConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Valida dependências
        if not PIL_AVAILABLE:
            raise ImportError("Pillow é necessário para conversão de imagens")
        
        if config.conversion_mode == 'pdf' and not PDF_AVAILABLE:
            raise ImportError("ReportLab é necessário para conversão PDF. Instale com: pip install reportlab")
        
        # Cache de arquivos temporários para limpeza
        self._temp_files: List[str] = []
        
        # Extensões suportadas
        self.supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        
        # Configurações PIL
        Image.MAX_IMAGE_PIXELS = None
    
    def prepare_for_upload(self, estruturas: List[EstruturaHierarquica]) -> List[EstruturaHierarquica]:
        """
        Prepara arquivos para upload baseado no modo de conversão
        
        Args:
            estruturas: Lista de estruturas hierárquicas
            
        Returns:
            Lista de estruturas modificadas (com conversões aplicadas)
        """
        if self.config.conversion_mode == 'original':
            return estruturas
        
        elif self.config.conversion_mode == 'webp':
            return self._convert_to_webp(estruturas)
        
        elif self.config.conversion_mode == 'pdf':
            return self._convert_to_pdf(estruturas)
        
        else:
            self.logger.warning(f"Modo de conversão desconhecido: {self.config.conversion_mode}")
            return estruturas
    
    def _convert_to_webp(self, estruturas: List[EstruturaHierarquica]) -> List[EstruturaHierarquica]:
        """Converte imagens para WebP mantendo estrutura individual"""
        converted_estruturas = []
        
        self.logger.info(f"Convertendo {len(estruturas)} arquivos para WebP (qualidade: {self.config.webp_quality}%)")
        
        for estrutura in estruturas:
            try:
                # Verifica se é imagem suportada
                _, ext = os.path.splitext(estrutura.arquivo.lower())
                if ext not in self.supported_extensions:
                    converted_estruturas.append(estrutura)
                    continue
                
                # Se já é WebP, mantém original
                if ext == '.webp':
                    converted_estruturas.append(estrutura)
                    continue
                
                # Converte para WebP
                webp_path = self._create_webp_temp(estrutura.caminho_local)
                if webp_path:
                    # Cria nova estrutura com arquivo WebP
                    webp_estrutura = EstruturaHierarquica(
                        agregador=estrutura.agregador,
                        scan=estrutura.scan,
                        serie=estrutura.serie,
                        capitulo=estrutura.capitulo,
                        arquivo=os.path.basename(webp_path),
                        caminho_local=webp_path,
                        caminho_relativo=estrutura.caminho_relativo
                    )
                    converted_estruturas.append(webp_estrutura)
                    self._temp_files.append(webp_path)
                else:
                    # Fallback para original em caso de erro
                    converted_estruturas.append(estrutura)
            
            except Exception as e:
                self.logger.error(f"Erro ao converter {estrutura.arquivo} para WebP: {e}")
                converted_estruturas.append(estrutura)  # Fallback
        
        self.logger.info(f"Conversão WebP concluída: {len(converted_estruturas)} arquivos preparados")
        return converted_estruturas
    
    def _convert_to_pdf(self, estruturas: List[EstruturaHierarquica]) -> List[EstruturaHierarquica]:
        """Converte capítulos completos para PDF"""
        # Agrupa por capítulo
        capitulos = self._group_by_chapter(estruturas)
        converted_estruturas = []
        
        self.logger.info(f"Convertendo {len(capitulos)} capítulos para PDF")
        
        for chapter_key, chapter_estruturas in capitulos.items():
            try:
                # Cria PDF do capítulo
                pdf_path = self._create_chapter_pdf(chapter_estruturas)
                if pdf_path:
                    # Cria estrutura única para o PDF do capítulo
                    pdf_estrutura = EstruturaHierarquica(
                        agregador=chapter_estruturas[0].agregador,
                        scan=chapter_estruturas[0].scan,
                        serie=chapter_estruturas[0].serie,
                        capitulo=chapter_estruturas[0].capitulo,
                        arquivo=os.path.basename(pdf_path),
                        caminho_local=pdf_path,
                        caminho_relativo=chapter_estruturas[0].caminho_relativo
                    )
                    converted_estruturas.append(pdf_estrutura)
                    self._temp_files.append(pdf_path)
                else:
                    # Fallback para imagens originais
                    converted_estruturas.extend(chapter_estruturas)
            
            except Exception as e:
                self.logger.error(f"Erro ao converter capítulo {chapter_key} para PDF: {e}")
                converted_estruturas.extend(chapter_estruturas)  # Fallback
        
        self.logger.info(f"Conversão PDF concluída: {len(converted_estruturas)} arquivos preparados")
        return converted_estruturas
    
    def _create_webp_temp(self, image_path: str) -> Optional[str]:
        """Cria arquivo WebP temporário"""
        try:
            with Image.open(image_path) as img:
                # Converte para RGB se necessário
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGBA')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Nome do arquivo temporário
                temp_name = f"webp_{int(time.time())}_{hashlib.md5(image_path.encode()).hexdigest()[:8]}.webp"
                temp_path = os.path.join(tempfile.gettempdir(), temp_name)
                
                # Salva como WebP
                img.save(temp_path, 'WebP', quality=self.config.webp_quality, optimize=True)
                
                # Log de estatísticas
                original_size = os.path.getsize(image_path)
                new_size = os.path.getsize(temp_path)
                compression_ratio = (1 - new_size / original_size) * 100
                
                self.logger.debug(f"WebP: {os.path.basename(image_path)} -> "
                                f"{self._format_size(original_size)} -> {self._format_size(new_size)} "
                                f"({compression_ratio:.1f}% economia)")
                
                return temp_path
        
        except Exception as e:
            self.logger.error(f"Erro ao criar WebP temporário para {image_path}: {e}")
            return None
    
    def _create_chapter_pdf(self, chapter_estruturas: List[EstruturaHierarquica]) -> Optional[str]:
        """Cria PDF temporário do capítulo"""
        try:
            # Ordena imagens por nome
            sorted_estruturas = sorted(chapter_estruturas, key=lambda x: x.arquivo)
            
            # Coleta caminhos das imagens
            image_paths = []
            for estrutura in sorted_estruturas:
                if os.path.exists(estrutura.caminho_local):
                    _, ext = os.path.splitext(estrutura.arquivo.lower())
                    if ext in self.supported_extensions:
                        image_paths.append(estrutura.caminho_local)
            
            if not image_paths:
                self.logger.warning(f"Nenhuma imagem válida encontrada para PDF do capítulo")
                return None
            
            # Nome do arquivo PDF temporário
            chapter_info = sorted_estruturas[0]
            safe_name = self._sanitize_filename(f"{chapter_info.serie}_{chapter_info.capitulo}")
            temp_name = f"pdf_{int(time.time())}_{safe_name}.pdf"
            temp_path = os.path.join(tempfile.gettempdir(), temp_name)
            
            # Configura tamanho da página
            page_sizes = {'A4': A4, 'Letter': letter}
            page_size = page_sizes.get(self.config.pdf_page_size, A4)
            
            # Cria PDF
            c = canvas.Canvas(temp_path, pagesize=page_size)
            page_width, page_height = page_size
            
            for i, img_path in enumerate(image_paths):
                try:
                    with Image.open(img_path) as img:
                        img_width, img_height = img.size
                        
                        # Calcula escala para caber na página
                        scale_w = page_width / img_width
                        scale_h = page_height / img_height
                        scale = min(scale_w, scale_h)
                        
                        new_width = img_width * scale
                        new_height = img_height * scale
                        
                        # Centraliza na página
                        x = (page_width - new_width) / 2
                        y = (page_height - new_height) / 2
                        
                        # Adiciona imagem ao PDF
                        c.drawImage(img_path, x, y, new_width, new_height)
                        
                        # Nova página (exceto na última)
                        if i < len(image_paths) - 1:
                            c.showPage()
                
                except Exception as e:
                    self.logger.warning(f"Erro ao processar imagem {img_path} no PDF: {e}")
                    continue
            
            c.save()
            
            # Log de estatísticas
            pdf_size = os.path.getsize(temp_path)
            self.logger.info(f"PDF criado: {chapter_info.capitulo} "
                           f"({len(image_paths)} páginas, {self._format_size(pdf_size)})")
            
            return temp_path
        
        except Exception as e:
            self.logger.error(f"Erro ao criar PDF do capítulo: {e}")
            return None
    
    def _group_by_chapter(self, estruturas: List[EstruturaHierarquica]) -> Dict[str, List[EstruturaHierarquica]]:
        """Agrupa estruturas por capítulo"""
        chapters = {}
        
        for estrutura in estruturas:
            chapter_key = f"{estrutura.scan}/{estrutura.serie}/{estrutura.capitulo}"
            if chapter_key not in chapters:
                chapters[chapter_key] = []
            chapters[chapter_key].append(estrutura)
        
        return chapters
    
    def cleanup_temp_files(self):
        """Remove arquivos temporários criados durante a conversão"""
        cleaned_count = 0
        total_size = 0
        
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    file_size = os.path.getsize(temp_file)
                    os.remove(temp_file)
                    cleaned_count += 1
                    total_size += file_size
                    self.logger.debug(f"Arquivo temporário removido: {temp_file}")
            
            except Exception as e:
                self.logger.warning(f"Erro ao remover arquivo temporário {temp_file}: {e}")
        
        if cleaned_count > 0:
            self.logger.info(f"Limpeza concluída: {cleaned_count} arquivos temporários removidos "
                           f"({self._format_size(total_size)} liberados)")
        
        self._temp_files.clear()
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove caracteres inválidos do nome do arquivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:50]  # Limita tamanho
    
    @staticmethod
    def _format_size(bytes_size: int) -> str:
        """Formata tamanho em bytes para string legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
    
    def __del__(self):
        """Cleanup automático quando o objeto é destruído"""
        if hasattr(self, '_temp_files') and self._temp_files:
            self.cleanup_temp_files()