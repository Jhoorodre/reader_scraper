#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BuzzHeavier Sync Enhanced - Sincronização avançada com BuzzHeavier
Versão: 2.0
"""

import os
import requests
import configparser
import time
import sys
import json
import hashlib
import logging
import platform
import tempfile
from datetime import datetime
from urllib.parse import quote
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

# Imports opcionais para consolidação
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# --- Constantes da API ---
API_URL_BASE = "https://buzzheavier.com/api"
UPLOAD_URL_BASE = "https://w.buzzheavier.com"
API_URL_FS = f"{API_URL_BASE}/fs"
API_URL_ACCOUNT = f"{API_URL_BASE}/account"

# --- Configurações ---
CONFIG_FILE = "config.ini"
SYNC_STATE_FILE = "sync_state.json"
LOGS_DIR = "_LOGS"

# --- Classes Auxiliares ---

@dataclass
class EstruturaHierarquica:
    """Representa a estrutura hierárquica validada"""
    agregador: str      # Gikamura
    scan: str          # Sussy Toons
    serie: str         # Arquiteto de Dungeons  
    capitulo: str      # Capítulo 01
    arquivo: str       # 01.jpg
    caminho_local: str # Caminho completo local
    caminho_relativo: str # Caminho relativo da raiz
    
    def get_caminho_remoto(self) -> str:
        """Retorna o caminho remoto no formato BuzzHeavier"""
        return f"{self.agregador}/{self.scan}/{self.serie}/{self.capitulo}"

@dataclass
class SyncStats:
    """Estatísticas da sincronização thread-safe"""
    def __init__(self):
        self.total_files = 0
        self.uploaded_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.total_size = 0
        self.uploaded_size = 0
        self.start_time = None
        self._lock = threading.Lock()
    
    def add_uploaded(self, size: int = 0):
        with self._lock:
            self.uploaded_files += 1
            self.uploaded_size += size
    
    def add_skipped(self):
        with self._lock:
            self.skipped_files += 1
    
    def add_failed(self):
        with self._lock:
            self.failed_files += 1
    
    def get_progress_percent(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.uploaded_files + self.skipped_files + self.failed_files) / self.total_files * 100

class ProgressBar:
    """Barra de progresso com cores e interface melhorada"""
    
    def __init__(self, total: int, description: str = "Progresso"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
    
    def update(self, increment: int = 1):
        self.current += increment
        self._display()
    
    def _display(self):
        if self.total == 0:
            percent = 100.0
        else:
            percent = (self.current / self.total) * 100
        
        bar_length = 35
        filled = int(bar_length * self.current / max(self.total, 1))
        
        # Cores baseadas no progresso
        if percent < 30:
            bar_color = '\033[91m'  # Vermelho
            bar_char = '█'
        elif percent < 70:
            bar_color = '\033[93m'  # Amarelo
            bar_char = '█'
        else:
            bar_color = '\033[92m'  # Verde
            bar_char = '█'
        
        reset_color = '\033[0m'
        bar = bar_color + bar_char * filled + reset_color + '░' * (bar_length - filled)
        
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta_seconds = (elapsed / self.current) * (self.total - self.current)
            eta = f"{int(eta_seconds // 60):02d}:{int(eta_seconds % 60):02d}"
            
            # Velocidade de processamento
            speed = self.current / elapsed
            speed_text = f" • {speed:.1f} arq/s"
        else:
            eta = "--:--"
            speed_text = ""
        
        # Emoji baseado no progresso
        if percent == 100:
            emoji = "✅"
        elif percent > 50:
            emoji = "🚀"
        else:
            emoji = "⏳"
        
        print(f"\r{emoji} {self.description}: {bar} \033[1m{percent:.1f}%\033[0m ({self.current:,}/{self.total:,}) ETA: {eta}{speed_text}", 
              end='', flush=True)
        
        if self.current >= self.total:
            print()  # Nova linha quando completo

class UploadProgressMonitor:
    """Monitor de progresso para upload de arquivo"""
    
    def __init__(self, filename: str, total_size: int):
        self.filename = filename
        self.total_size = total_size
        self.uploaded = 0
        self.start_time = time.time()
        self.last_update = time.time()
        
    def __call__(self, chunk: bytes):
        """Callback chamado para cada chunk enviado"""
        self.uploaded += len(chunk)
        current_time = time.time()
        
        # Atualiza a cada 0.1 segundos para não sobrecarregar
        if current_time - self.last_update >= 0.1 or self.uploaded == self.total_size:
            self._display_progress()
            self.last_update = current_time
    
    def _display_progress(self):
        """Exibe progresso do upload atual com interface melhorada"""
        if self.total_size == 0:
            percent = 100.0
        else:
            percent = (self.uploaded / self.total_size) * 100
        
        bar_length = 30
        filled = int(bar_length * self.uploaded / max(self.total_size, 1))
        
        # Cores e animação baseadas no progresso
        if percent < 25:
            bar_color = '\033[94m'  # Azul
            emoji = "📤"
        elif percent < 50:
            bar_color = '\033[96m'  # Ciano
            emoji = "⬆️"
        elif percent < 75:
            bar_color = '\033[93m'  # Amarelo
            emoji = "🚀"
        else:
            bar_color = '\033[92m'  # Verde
            emoji = "⚡"
        
        reset_color = '\033[0m'
        bar = bar_color + '█' * filled + reset_color + '░' * (bar_length - filled)
        
        elapsed = time.time() - self.start_time
        if self.uploaded > 0 and elapsed > 0:
            speed = self.uploaded / elapsed
            if speed > 0:
                eta_seconds = (self.total_size - self.uploaded) / speed
                eta = f"{int(eta_seconds):02d}s"
            else:
                eta = "--s"
            speed_str = format_size(speed) + "/s"
            
            # Adiciona cor à velocidade baseada na performance
            if speed > 1024 * 1024:  # > 1MB/s
                speed_color = '\033[92m'  # Verde
            elif speed > 512 * 1024:  # > 512KB/s
                speed_color = '\033[93m'  # Amarelo
            else:
                speed_color = '\033[91m'  # Vermelho
            speed_str = speed_color + speed_str + reset_color
        else:
            eta = "--s"
            speed_str = "0 B/s"
        
        uploaded_str = format_size(self.uploaded)
        total_str = format_size(self.total_size)
        
        # Nome do arquivo truncado se muito longo
        display_name = self.filename
        if len(display_name) > 25:
            display_name = display_name[:22] + "..."
        
        print(f"\r      {emoji} \033[1m{display_name}\033[0m: {bar} \033[1m{percent:.1f}%\033[0m ({uploaded_str}/{total_str}) {speed_str} ETA: {eta}", 
              end='', flush=True)
        
        if self.uploaded >= self.total_size:
            print()  # Nova linha quando completo

class FileUploadWrapper:
    """Wrapper para arquivo que monitora progresso"""
    
    def __init__(self, file_obj, progress_callback):
        self.file_obj = file_obj
        self.progress_callback = progress_callback
        
    def read(self, size=-1):
        """Lê dados e notifica callback"""
        chunk = self.file_obj.read(size)
        if chunk and self.progress_callback:
            self.progress_callback(chunk)
        return chunk
    
    def __getattr__(self, name):
        """Delega outros métodos para o arquivo original"""
        return getattr(self.file_obj, name)

class SyncState:
    """Gerencia estado da sincronização para resume"""
    
    def __init__(self):
        self.uploaded_files: Set[str] = set()
        self.failed_files: Set[str] = set()
        self.file_hashes: Dict[str, str] = {}
    
    def load(self):
        """Carrega estado salvo"""
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.uploaded_files = set(data.get('uploaded_files', []))
                    self.failed_files = set(data.get('failed_files', []))
                    self.file_hashes = data.get('file_hashes', {})
                    logging.info(f"Estado carregado: {len(self.uploaded_files)} arquivos já enviados")
            except Exception as e:
                logging.warning(f"Erro ao carregar estado: {e}")
    
    def save(self):
        """Salva estado atual"""
        try:
            data = {
                'uploaded_files': list(self.uploaded_files),
                'failed_files': list(self.failed_files),
                'file_hashes': self.file_hashes,
                'last_sync': datetime.now().isoformat()
            }
            with open(SYNC_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Erro ao salvar estado: {e}")
    
    def mark_uploaded(self, file_path: str, file_hash: str):
        """Marca arquivo como enviado"""
        self.uploaded_files.add(file_path)
        self.file_hashes[file_path] = file_hash
        self.failed_files.discard(file_path)
    
    def mark_failed(self, file_path: str):
        """Marca arquivo como falhou"""
        self.failed_files.add(file_path)
        self.uploaded_files.discard(file_path)
    
    def is_uploaded(self, file_path: str, current_hash: str) -> bool:
        """Verifica se arquivo já foi enviado com mesmo hash"""
        return (file_path in self.uploaded_files and 
                self.file_hashes.get(file_path) == current_hash)
    
    def get_failed_files(self) -> List[str]:
        """Retorna lista de arquivos que falharam"""
        return list(self.failed_files)
    
    def clear_failed_files(self):
        """Limpa lista de arquivos que falharam"""
        self.failed_files.clear()
        logging.info("Lista de arquivos falhados foi limpa")
    
    def retry_failed_files(self) -> List[str]:
        """Retorna arquivos que falharam e ainda existem no sistema"""
        existing_failed = []
        to_remove = []
        
        for file_path in self.failed_files:
            if os.path.exists(file_path):
                existing_failed.append(file_path)
            else:
                # Marca para remoção arquivos que não existem mais
                to_remove.append(file_path)
        
        # Remove arquivos inexistentes
        for file_path in to_remove:
            self.failed_files.discard(file_path)
            logging.info(f"Arquivo removido da lista de falhas (não existe): {file_path}")
        
        # Salva estado se houve remoções
        if to_remove:
            self.save()
            
        return existing_failed

# --- Variáveis Globais ---
cache_diretorios = {}
sync_stats = SyncStats()
sync_state = SyncState()

# --- Funções Auxiliares ---

def verificar_consolidacao_disponivel() -> bool:
    """Verifica se a consolidação de capítulos está disponível"""
    if platform.system() != 'Linux':
        print("❌ CONSOLIDAÇÃO: Função disponível apenas no Linux")
        return False
    
    if not PIL_AVAILABLE:
        print("❌ CONSOLIDAÇÃO: Pillow não instalado")
        print("   Instale: pip install pillow")
        return False
    
    try:
        # Permite que o Pillow processe imagens com dimensões gigantescas
        Image.MAX_IMAGE_PIXELS = None
        
        # Testa se libimagequant está disponível
        test_img = Image.new('RGB', (1, 1))
        test_img.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT)
        return True
    except Exception as e:
        print("❌ CONSOLIDAÇÃO: libimagequant não disponível")
        print("   Instale: pip install pillow[imagequant]")
        return False

def normalizar_caminho(caminho: str) -> str:
    """Normaliza caminho para o sistema operacional atual"""
    if not caminho:
        return ""
    
    # Expandir ~ primeiro se presente
    caminho = os.path.expanduser(caminho)
    
    # Detectar se é caminho Windows absoluto (C:\ ou C:/ ou similar)
    is_windows_absolute = (len(caminho) >= 3 and 
                          caminho[1] == ':' and 
                          (caminho[2] == '\\' or caminho[2] == '/'))
    
    if is_windows_absolute:
        # É um caminho Windows absoluto - converter para WSL se estivermos no Linux
        if platform.system() == 'Linux' and os.path.exists('/mnt'):
            # Converter C:\path ou C:/path para /mnt/c/path
            drive_letter = caminho[0].lower()
            resto_caminho = caminho[3:].replace('\\', '/').replace('//', '/')
            caminho_wsl = f"/mnt/{drive_letter}/{resto_caminho}"
            return caminho_wsl
    
    # Converte separadores para o OS atual
    caminho_normalizado = caminho.replace('\\', os.sep).replace('/', os.sep)
    
    # Se já é absoluto, não usar abspath para evitar concatenação
    if os.path.isabs(caminho_normalizado):
        return caminho_normalizado
    else:
        return os.path.abspath(caminho_normalizado)

def detectar_agregador(root_path: str) -> str:
    """Detecta automaticamente o nome do agregador baseado no caminho"""
    if not os.path.exists(root_path):
        raise FileNotFoundError(f"Caminho não encontrado: {root_path}")
    
    if not os.path.isdir(root_path):
        raise NotADirectoryError(f"Caminho não é um diretório: {root_path}")
    
    # O nome do agregador é o último componente do caminho
    agregador = os.path.basename(root_path)
    
    if not agregador:
        raise ValueError(f"Não foi possível determinar nome do agregador: {root_path}")
    
    return agregador

def validar_estrutura_caminho(root_path: str) -> bool:
    """Valida se o caminho tem a estrutura esperada (Agregador/Scan/Serie/...)"""
    try:
        if not os.path.exists(root_path):
            print(f"❌ Caminho não existe: {root_path}")
            return False
        
        # Verifica se tem pelo menos uma estrutura de scan dentro
        items = os.listdir(root_path)
        diretorios = [item for item in items if os.path.isdir(os.path.join(root_path, item))]
        
        if not diretorios:
            print(f"❌ Nenhum diretório de scan encontrado em: {root_path}")
            return False
        
        # Verifica estrutura de pelo menos um scan
        primeiro_scan = os.path.join(root_path, diretorios[0])
        items_scan = os.listdir(primeiro_scan)
        series = [item for item in items_scan if os.path.isdir(os.path.join(primeiro_scan, item))]
        
        if not series:
            print(f"❌ Nenhuma série encontrada no scan: {primeiro_scan}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao validar estrutura: {e}")
        return False

def setup_logging():
    """Configura sistema de logs"""
    # Criar pasta de logs se não existir
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

def consolidar_capitulo(imagens_paths: List[str], estrutura_base: EstruturaHierarquica, config_data: dict) -> Optional[str]:
    """Consolida páginas de um capítulo em um PNG único otimizado"""
    if not verificar_consolidacao_disponivel():
        return None
    
    if not config_data.get('consolidation_enabled', False):
        return None
    
    try:
        # Carrega todas as imagens do capítulo
        imagens = []
        for img_path in sorted(imagens_paths):
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path)
                    imagens.append(img.convert('RGBA'))
                except Exception as e:
                    print(f"⚠️  Erro ao carregar {os.path.basename(img_path)}: {e}")
                    continue
        
        if not imagens:
            print("❌ Nenhuma imagem válida encontrada para consolidação")
            return None
        
        # Calcula dimensões da imagem final
        largura_maxima = max(img.width for img in imagens)
        altura_total = sum(img.height for img in imagens)
        
        print(f"📦 Consolidando {len(imagens)} páginas ({largura_maxima}x{altura_total}px)")
        
        # Cria a imagem final
        imagem_final = Image.new('RGBA', (largura_maxima, altura_total))
        pos_y = 0
        
        for img in imagens:
            imagem_final.paste(img, (0, pos_y))
            pos_y += img.height
            img.close()
        
        # Gera nome do arquivo consolidado usando o nome do capítulo
        numero_cap = extrair_numero_capitulo(estrutura_base.capitulo)
        pattern = config_data.get('consolidation_filename_pattern', 'Cap {numero:04d} - {serie}.png')
        nome_consolidado = pattern.format(numero=numero_cap, serie=estrutura_base.serie)
        
        # Adiciona timestamp e hash para garantir unicidade do arquivo temporário
        import hashlib
        import time as time_module
        unique_id = hashlib.md5(f"{estrutura_base.capitulo}{time_module.time()}".encode()).hexdigest()[:8]
        nome_temp = f"{unique_id}_{nome_consolidado}"
        
        # Salva arquivo temporário com nome único
        temp_path = os.path.join(tempfile.gettempdir(), nome_temp)
        
        print(f"🔧 Aplicando quantização libimagequant...")
        imagem_quantizada = imagem_final.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT)
        imagem_quantizada.save(temp_path, 'PNG', optimize=True)
        
        print(f"✅ Capítulo consolidado: {nome_consolidado} ({format_size(os.path.getsize(temp_path))})")
        
        return temp_path
        
    except Exception as e:
        print(f"❌ Erro na consolidação: {e}")
        return None

def processar_arquivo_individual(estrutura: EstruturaHierarquica, account_id: str, config_data: dict, progress: 'ProgressBar') -> bool:
    """Processa um arquivo individual em thread"""
    try:
        # Verifica se o arquivo já foi processado com sucesso no log
        if verificar_sucesso_no_log(estrutura):
            print(f"  ⏭️  PULANDO: '{estrutura.capitulo}' (já processado com sucesso)")
            return True
            
        # Garante estrutura hierárquica de diretórios
        id_diretorio_destino = garantir_caminho_remoto(account_id, estrutura)
        if id_diretorio_destino:
            # Sincroniza arquivo
            resultado = sincronizar_arquivo(account_id, estrutura, id_diretorio_destino, config_data)
            progress.update()
            return resultado
        else:
            print(f"  ❌ ERRO: Falha ao criar estrutura hierárquica para {estrutura.arquivo}")
            sync_stats.add_failed()
            sync_state.mark_failed(estrutura.caminho_local)
            progress.update()
            return False
    except Exception as e:
        print(f"  ❌ ERRO: {e}")
        sync_stats.add_failed()
        progress.update()
        return False

def processar_capitulo_thread(args) -> int:
    """Processa um capítulo em thread - retorna número de arquivos processados"""
    chave_capitulo, arquivos_capitulo, account_id, config_data, progress = args
    
    try:
        print(f"\n📖 Processando capítulo: {chave_capitulo}")
        
        # Se só tem 1 arquivo, não consolida
        if len(arquivos_capitulo) == 1 or not verificar_consolidacao_disponivel():
            # Processa arquivo individual
            for estrutura in arquivos_capitulo:
                id_diretorio_destino = garantir_caminho_remoto(account_id, estrutura)
                if id_diretorio_destino:
                    sincronizar_arquivo(account_id, estrutura, id_diretorio_destino, config_data)
                progress.update()
        else:
            # Consolida capítulo
            caminhos_imagens = [est.caminho_local for est in arquivos_capitulo]
            estrutura_base = arquivos_capitulo[0]  # Usa primeira como base
            
            # Gera PNG consolidado
            arquivo_consolidado = consolidar_capitulo(caminhos_imagens, estrutura_base, config_data)
            
            if arquivo_consolidado and config_data.get('consolidation_upload_consolidated', True):
                # Extrai o nome original do arquivo (remove o hash único do nome temporário)
                nome_temp = os.path.basename(arquivo_consolidado)
                # Remove o prefixo hash_timestamp_ do nome
                if '_' in nome_temp:
                    nome_original = '_'.join(nome_temp.split('_')[1:])  # Remove primeira parte (hash)
                else:
                    nome_original = nome_temp
                
                # Cria estrutura para o arquivo consolidado (sem subpasta de capítulo)
                estrutura_consolidada = EstruturaHierarquica(
                    agregador=estrutura_base.agregador,
                    scan=estrutura_base.scan,
                    serie=estrutura_base.serie,
                    capitulo="",  # Sem capítulo para ir direto na série
                    arquivo=nome_original,  # Usa nome original sem hash
                    caminho_local=arquivo_consolidado,
                    caminho_relativo=f"{estrutura_base.agregador}/{estrutura_base.scan}/{estrutura_base.serie}/{nome_original}"
                )
                
                # Upload do arquivo consolidado (direto na pasta da série)
                id_diretorio_serie = garantir_caminho_remoto(account_id, estrutura_consolidada)
                if id_diretorio_serie:
                    sincronizar_arquivo(account_id, estrutura_consolidada, id_diretorio_serie, config_data)
                
                # Remove arquivo temporário
                try:
                    os.remove(arquivo_consolidado)
                except:
                    pass
            
            # Se configurado, também faz upload das páginas individuais
            if config_data.get('consolidation_upload_individual', False):
                for estrutura in arquivos_capitulo:
                    id_diretorio_destino = garantir_caminho_remoto(account_id, estrutura)
                    if id_diretorio_destino:
                        sincronizar_arquivo(account_id, estrutura, id_diretorio_destino, config_data)
            
            # Atualiza progresso para todos os arquivos do capítulo
            for _ in arquivos_capitulo:
                progress.update()
        
        return len(arquivos_capitulo)
        
    except Exception as e:
        print(f"❌ Erro no capítulo {chave_capitulo}: {e}")
        for _ in arquivos_capitulo:
            sync_stats.add_failed()
            progress.update()
        return len(arquivos_capitulo)

def agrupar_por_capitulo(estruturas: List[EstruturaHierarquica]) -> Dict[str, List[EstruturaHierarquica]]:
    """Agrupa estruturas por capítulo (Agregador/Scan/Serie/Capitulo)"""
    capitulos = {}
    
    for estrutura in estruturas:
        # Cria chave única para o capítulo
        chave_capitulo = f"{estrutura.agregador}/{estrutura.scan}/{estrutura.serie}"
        
        # Se arquivo está em subpasta (capítulo), adiciona à chave
        pasta_pai = os.path.dirname(estrutura.caminho_local)
        nome_pasta_pai = os.path.basename(pasta_pai)
        
        # Se a pasta pai não é a série, é um capítulo
        if nome_pasta_pai != estrutura.serie:
            chave_capitulo += f"/{nome_pasta_pai}"
        
        if chave_capitulo not in capitulos:
            capitulos[chave_capitulo] = []
        
        capitulos[chave_capitulo].append(estrutura)
    
    return capitulos

def extrair_numero_capitulo(nome_arquivo: str) -> int:
    """Extrai número do capítulo do nome do arquivo"""
    import re
    # Busca por números no nome do arquivo
    numeros = re.findall(r'\d+', nome_arquivo)
    if numeros:
        return int(numeros[0])
    return 1

def carregar_logs_existentes() -> Dict[str, Dict]:
    """Carrega todos os logs JSON existentes para análise de cache"""
    logs_existentes = {}
    
    if not os.path.exists(LOGS_DIR):
        return logs_existentes
    
    for arquivo in os.listdir(LOGS_DIR):
        if arquivo.endswith('.json'):
            caminho_log = os.path.join(LOGS_DIR, arquivo)
            try:
                with open(caminho_log, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                    # Extrai informações da série
                    chave_serie = f"{log_data['agregador']}/{log_data['scan']}/{log_data['serie']}"
                    logs_existentes[chave_serie] = log_data
            except Exception as e:
                print(f"⚠️  Erro ao carregar log {arquivo}: {e}")
    
    return logs_existentes

def analisar_status_capitulos(logs_existentes: Dict[str, Dict]) -> Dict[str, str]:
    """Analisa status dos capítulos baseado nos logs"""
    status_capitulos = {}
    
    for chave_serie, log_data in logs_existentes.items():
        # Conta arquivos por status
        sucessos = log_data.get('estatisticas', {}).get('sucessos', 0)
        total = log_data.get('estatisticas', {}).get('total_arquivos', 0)
        
        # Verifica se tem arquivo consolidado E todos foram processados
        consolidado_existe = any(
            entry['arquivo'].endswith('.png') and entry['status'] == 'sucesso'
            for entry in log_data.get('historico', [])
        )
        
        if consolidado_existe and sucessos == total and total > 0:
            status_capitulos[chave_serie] = 'consolidado'
        elif sucessos == total and total > 0:
            status_capitulos[chave_serie] = 'completo'
        elif sucessos > 0:
            status_capitulos[chave_serie] = 'parcial'
        else:
            status_capitulos[chave_serie] = 'pendente'
    
    return status_capitulos

def verificar_sucesso_no_log(estrutura: EstruturaHierarquica) -> bool:
    """Verifica se o arquivo consolidado já foi processado com sucesso no log"""
    try:
        # Gera nome do arquivo consolidado baseado no padrão dos logs
        # Formato: "Cap 0010 - Arquiteto de Dungeons.png"
        capitulo_num = estrutura.capitulo.replace("Capítulo ", "").zfill(4)
        nome_consolidado = f"Cap {capitulo_num} - {estrutura.serie}.png"
        print(f"  🔍 DEBUG: Procurando '{nome_consolidado}' no log")
        
        # Carrega log da série
        nome_arquivo_log = f"{estrutura.agregador}_{estrutura.scan}_{estrutura.serie}.json"
        caminho_log = os.path.join(LOGS_DIR, nome_arquivo_log)
        
        if not os.path.exists(caminho_log):
            return False
            
        with open(caminho_log, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
            
        # Verifica histórico para arquivo consolidado com sucesso
        for entry in log_data.get('historico', []):
            if entry['arquivo'] == nome_consolidado and entry['status'] == 'sucesso':
                print(f"  ✅ ENCONTRADO NO LOG: {nome_consolidado} com sucesso")
                return True
                
        return False
        
    except Exception as e:
        print(f"⚠️  Erro ao verificar log para {estrutura.capitulo}: {e}")
        return False

def filtrar_arquivos_por_cache(estruturas_validas: List[EstruturaHierarquica], status_capitulos: Dict[str, str]) -> List[EstruturaHierarquica]:
    """Filtra arquivos baseado no cache de logs"""
    arquivos_filtrados = []
    capitulos_processados = set()
    
    print(f"\n🧠 ANÁLISE DE CACHE INTELIGENTE")
    print("="*50)
    
    for estrutura in estruturas_validas:
        chave_serie = f"{estrutura.agregador}/{estrutura.scan}/{estrutura.serie}"
        
        # Se a série já foi consolidada, pula todos os arquivos dela
        if chave_serie in status_capitulos:
            status = status_capitulos[chave_serie]
            
            if status == 'consolidado':
                if chave_serie not in capitulos_processados:
                    print(f"✅ {chave_serie}: Já consolidado (pulando)")
                    capitulos_processados.add(chave_serie)
                continue
            elif status == 'completo':
                if chave_serie not in capitulos_processados:
                    print(f"✅ {chave_serie}: Completo (pulando)")
                    capitulos_processados.add(chave_serie)
                continue
            elif status == 'parcial':
                if chave_serie not in capitulos_processados:
                    print(f"🔄 {chave_serie}: Parcial (reprocessando)")
                    capitulos_processados.add(chave_serie)
        else:
            if chave_serie not in capitulos_processados:
                print(f"🆕 {chave_serie}: Novo (processando)")
                capitulos_processados.add(chave_serie)
        
        # Adiciona arquivo para processamento
        arquivos_filtrados.append(estrutura)
    
    print("="*50)
    total_original = len(estruturas_validas)
    total_filtrado = len(arquivos_filtrados)
    economia = total_original - total_filtrado
    
    if economia > 0:
        print(f"🚀 CACHE OTIMIZADO: {economia:,} arquivos pulados ({economia/total_original*100:.1f}% economia)")
        print(f"📊 Processando apenas: {total_filtrado:,} arquivos pendentes")
    else:
        print(f"📊 Nenhum arquivo em cache - processando todos: {total_filtrado:,} arquivos")
    
    return arquivos_filtrados

def salvar_log_serie(estrutura: EstruturaHierarquica, status: str, detalhes: str = "", file_hash: str = None):
    """Salva log específico da série em JSON"""
    nome_arquivo = f"{estrutura.agregador}_{estrutura.scan}_{estrutura.serie}.json"
    caminho_log = os.path.join(LOGS_DIR, nome_arquivo)
    
    # Carregar log existente ou criar novo
    if os.path.exists(caminho_log):
        with open(caminho_log, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    else:
        log_data = {
            "agregador": estrutura.agregador,
            "scan": estrutura.scan,
            "serie": estrutura.serie,
            "historico": [],
            "estatisticas": {
                "total_arquivos": 0,
                "sucessos": 0,
                "falhas": 0,
                "pulados": 0
            }
        }
    
    # Adicionar nova entrada
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "arquivo": estrutura.arquivo,
        "status": status,
        "detalhes": detalhes
    }
    
    # Adiciona hash se fornecido
    if file_hash:
        entrada["hash"] = file_hash
    log_data["historico"].append(entrada)
    
    # Atualizar estatísticas
    log_data["estatisticas"]["total_arquivos"] = len(log_data["historico"])
    if status == "sucesso":
        log_data["estatisticas"]["sucessos"] += 1
    elif status == "falha":
        log_data["estatisticas"]["falhas"] += 1
    elif status == "pulado":
        log_data["estatisticas"]["pulados"] += 1
    
    # Salvar arquivo
    with open(caminho_log, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

def calculate_file_hash(file_path: str) -> Optional[str]:
    """Calcula hash MD5 de um arquivo"""
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"Erro ao calcular hash de {file_path}: {e}")
        return None

def format_size(size_bytes: int) -> str:
    """Formata tamanho em bytes para string legível"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def validar_e_mapear_estrutura(caminho_arquivo: str, pasta_raiz: str, agregador_esperado: str) -> Optional[EstruturaHierarquica]:
    """
    Valida e mapeia a estrutura hierárquica do arquivo
    Como pasta_raiz já aponta para o agregador, esperado: Scan/Serie/Capitulo/arquivo.ext
    """
    try:
        # Obter caminho relativo da pasta raiz (que já é o diretório do agregador)
        caminho_relativo = os.path.relpath(caminho_arquivo, pasta_raiz)
        # print(f"DEBUG: Processando arquivo: {caminho_arquivo} -> Relativo: {caminho_relativo}")
        
        # Normalizar separadores para o sistema atual
        caminho_relativo = caminho_relativo.replace('/', os.sep).replace('\\', os.sep)
        
        # Dividir em partes
        partes = caminho_relativo.split(os.sep)
        
        # Validar estrutura mínima: Scan/Serie/Capitulo/arquivo (4 partes mínimo)
        if len(partes) < 4:
            # print(f"DEBUG: Estrutura inválida (menos de 4 níveis): {caminho_relativo} - Partes: {len(partes)} - {partes}")
            return None
        
        # Extrair componentes (agregador vem do parâmetro, não do caminho)
        scan = partes[0]
        serie = partes[1] 
        capitulo = partes[2]
        arquivo = partes[-1]  # Último elemento (nome do arquivo)
        
        # O agregador vem da configuração, não do caminho relativo
        agregador = agregador_esperado
        
        # Verificar se é um arquivo de imagem
        extensoes_validas = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.cbz'}
        _, ext = os.path.splitext(arquivo.lower())
        if ext not in extensoes_validas:
            # print(f"DEBUG: Extensão inválida '{ext}': {caminho_relativo}")
            return None
        
        # Validar que não há subpastas extras entre Capítulo e arquivo
        if len(partes) > 5:
            # Se há mais de 5 partes, verificar se são subpastas válidas no capítulo
            subcaminhos = partes[4:-1]  # Partes entre capítulo e arquivo
            for sub in subcaminhos:
                if not sub.strip():  # Partes vazias são inválidas
                    logging.debug(f"Subcaminho vazio encontrado: {caminho_relativo}")
                    return None
        
        return EstruturaHierarquica(
            agregador=agregador,
            scan=scan,
            serie=serie, 
            capitulo=capitulo,
            arquivo=arquivo,
            caminho_local=caminho_arquivo,
            caminho_relativo=caminho_relativo
        )
        
    except Exception as e:
        logging.warning(f"Erro ao validar estrutura de {caminho_arquivo}: {e}")
        return None

def should_sync_file(file_path: str, allowed_ext: Set[str], blocked_ext: Set[str], max_size: int) -> bool:
    """Verifica se arquivo deve ser sincronizado"""
    file_ext = os.path.splitext(file_path)[1].lower()
    file_size = os.path.getsize(file_path)
    
    # Verifica extensões bloqueadas
    if blocked_ext and file_ext in blocked_ext:
        return False
    
    # Verifica extensões permitidas (se especificadas)
    if allowed_ext and file_ext not in allowed_ext:
        return False
    
    # Verifica tamanho máximo
    if max_size > 0 and file_size > max_size:
        return False
    
    return True

def carregar_config():
    """Carrega configurações do arquivo INI"""
    config = configparser.ConfigParser()
    
    if not os.path.exists(CONFIG_FILE):
        criar_config_padrao()
        print(f"❌ Arquivo '{CONFIG_FILE}' criado com configurações padrão.")
        print("   Por favor, configure seu ACCOUNT_ID antes de continuar.")
        return None
    
    config.read(CONFIG_FILE)
    
    try:
        # Configurações obrigatórias
        account_id = config['BUZZHEAVIER']['ACCOUNT_ID']
        if "SEU_ACCOUNT_ID_AQUI" in account_id or not account_id:
            print("❌ Erro: Você ainda não configurou seu ACCOUNT_ID.")
            return None
        
        # Configurações opcionais de filtros
        config_data = {
            'account_id': account_id,
            'allowed_extensions': set(),
            'blocked_extensions': set(),
            'max_file_size': 0,
            'verify_integrity': True,
            'resume_uploads': True,
            'root_path': '',
            'agregador': ''
        }
        
        if config.has_section('SYNC'):
            # Extensões permitidas
            allowed = config.get('SYNC', 'allowed_extensions', fallback='').strip()
            if allowed:
                config_data['allowed_extensions'] = set(ext.strip() for ext in allowed.split(',') if ext.strip())
            
            # Extensões bloqueadas
            blocked = config.get('SYNC', 'blocked_extensions', fallback='.tmp,.log,.cache').strip()
            if blocked:
                config_data['blocked_extensions'] = set(ext.strip() for ext in blocked.split(',') if ext.strip())
            
            # Outras configurações
            config_data['max_file_size'] = config.getint('SYNC', 'max_file_size_mb', fallback=0) * 1024 * 1024
            config_data['verify_integrity'] = config.getboolean('SYNC', 'verify_integrity', fallback=True)
            config_data['resume_uploads'] = config.getboolean('SYNC', 'resume_uploads', fallback=True)
            
            # Processa caminho root configurável
            root_path_config = config.get('SYNC', 'root_path', fallback='').strip()
            if root_path_config:
                # Normaliza caminho para o OS atual
                root_path_normalizado = normalizar_caminho(root_path_config)
                
                # Valida se o caminho existe e tem estrutura correta
                if not validar_estrutura_caminho(root_path_normalizado):
                    print(f"❌ Erro: Caminho inválido ou estrutura incorreta: {root_path_normalizado}")
                    return None
                
                # Detecta agregador automaticamente
                try:
                    agregador = detectar_agregador(root_path_normalizado)
                    config_data['root_path'] = root_path_normalizado
                    config_data['agregador'] = agregador
                    print(f"✅ Caminho configurado: {root_path_normalizado}")
                    print(f"✅ Agregador detectado: {agregador}")
                except Exception as e:
                    print(f"❌ Erro ao detectar agregador: {e}")
                    return None
            else:
                # Fallback para modo antigo (compatibilidade)
                config_data['root_path'] = 'Gikamura'
                config_data['agregador'] = 'Gikamura'
                print("⚠️  Usando modo de compatibilidade (root_path não configurado)")
        
        # Configurações de consolidação
        if config.has_section('CONSOLIDATION'):
            config_data['consolidation_enabled'] = config.getboolean('CONSOLIDATION', 'enabled', fallback=False)
            config_data['consolidation_upload_consolidated'] = config.getboolean('CONSOLIDATION', 'upload_consolidated', fallback=True)
            config_data['consolidation_upload_individual'] = config.getboolean('CONSOLIDATION', 'upload_individual_pages', fallback=False)
            config_data['consolidation_filename_pattern'] = config.get('CONSOLIDATION', 'filename_pattern', fallback='Cap {numero:04d} - {serie}.png')
        else:
            config_data['consolidation_enabled'] = False
            config_data['consolidation_upload_consolidated'] = False
            config_data['consolidation_upload_individual'] = True
            config_data['consolidation_filename_pattern'] = 'Cap {numero:04d} - {serie}.png'
        
        # Configurações de threading
        if config.has_section('THREADING'):
            config_data['max_workers'] = config.getint('THREADING', 'max_workers', fallback=3)
        else:
            config_data['max_workers'] = 3
        
        return config_data
        
    except KeyError as e:
        print(f"❌ Erro: Configuração '{e}' não encontrada.")
        return None

def criar_config_padrao():
    """Cria arquivo de configuração padrão"""
    config = configparser.ConfigParser()
    config['BUZZHEAVIER'] = {
        'ACCOUNT_ID': 'SEU_ACCOUNT_ID_AQUI'
    }
    config['SYNC'] = {
        'allowed_extensions': '',  # vazio = todos os tipos
        'blocked_extensions': '.tmp,.log,.cache',
        'max_file_size_mb': '0',  # 0 = sem limite
        'verify_integrity': 'true',
        'resume_uploads': 'true',
        'root_path': '/caminho/para/agregador'
    }
    
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

def mapear_arquivos_locais(pasta_raiz: str, config_data: dict) -> List[EstruturaHierarquica]:
    """Mapeia arquivos locais aplicando filtros"""
    print(f"📁 Mapeando arquivos em '{pasta_raiz}'...")
    
    if not os.path.isdir(pasta_raiz):
        print(f"❌ Erro: A pasta '{pasta_raiz}' não foi encontrada!")
        return []
    
    estruturas_validas = []
    total_size = 0
    filtered_count = 0
    invalid_structure_count = 0
    scanned_count = 0
    
    for pasta_atual, subpastas, arquivos in os.walk(pasta_raiz):
        # Exclui pasta _LOGS do processamento (mantém apenas local)
        if '_LOGS' in subpastas:
            subpastas.remove('_LOGS')
            logging.info("Pasta _LOGS excluída da sincronização (mantida apenas local)")
        for nome_arquivo in arquivos:
            scanned_count += 1
            caminho_completo = os.path.join(pasta_atual, nome_arquivo)
            
            # Indicador visual a cada 1000 arquivos
            if scanned_count % 1000 == 0:
                print(f"   \033[2mEscaneados: {scanned_count:,} arquivos...\033[0m", end='\r')
            
            # Pula arquivos que estão dentro de _LOGS
            if '_LOGS' in caminho_completo:
                filtered_count += 1
                continue
            
            try:
                # Valida estrutura hierárquica primeiro
                estrutura = validar_e_mapear_estrutura(caminho_completo, config_data['root_path'], config_data['agregador'])
                if not estrutura:
                    invalid_structure_count += 1
                    continue
                
                # Aplica filtros tradicionais
                if should_sync_file(caminho_completo, 
                                  config_data['allowed_extensions'],
                                  config_data['blocked_extensions'], 
                                  config_data['max_file_size']):
                    estruturas_validas.append(estrutura)
                    total_size += os.path.getsize(caminho_completo)
                else:
                    filtered_count += 1
                    
            except (OSError, IOError) as e:
                logging.warning(f"Erro ao acessar arquivo {caminho_completo}: {e}")
                continue
    
    print()  # Nova linha após o progresso
    
    # Atualiza estatísticas globais
    sync_stats.total_files = len(estruturas_validas)
    sync_stats.total_size = total_size
    
    # Resultado com cores
    print(f"\n\033[1;32m✅ MAPEAMENTO E VALIDAÇÃO CONCLUÍDA\033[0m")
    print(f"   📊 \033[1m{len(estruturas_validas):,}\033[0m arquivos com estrutura válida")
    print(f"   💾 \033[1m{format_size(total_size)}\033[0m de dados")
    print(f"   📁 \033[2m{scanned_count:,}\033[0m arquivos escaneados")
    if invalid_structure_count > 0:
        print(f"   ⚠️  \033[91m{invalid_structure_count:,}\033[0m arquivos com estrutura inválida (ignorados)")
    if filtered_count > 0:
        print(f"   🚫 \033[93m{filtered_count:,}\033[0m arquivos filtrados")
    
    return estruturas_validas

def obter_id_raiz(account_id: str) -> Optional[str]:
    """Obtém o ID do diretório raiz usando a API de File Manager"""
    if 'raiz' in cache_diretorios:
        return cache_diretorios['raiz']
    
    print("🔍 Buscando ID do diretório raiz...")
    headers = {"Authorization": f"Bearer {account_id}"}
    
    try:
        # Usa a API de File Manager para obter o diretório raiz
        response = requests.get(API_URL_FS, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"❌ Erro ao buscar diretório raiz! Status: {response.status_code}")
            logging.error(f"Erro na API do File Manager: {response.status_code} - {response.text}")
            return None
        
        dados_fs = response.json()
        # O ID do diretório raiz está dentro do objeto 'data'
        data = dados_fs.get('data', {})
        id_raiz = data.get('id')
        if not id_raiz:
            print("❌ Erro: ID do diretório raiz não encontrado.")
            logging.error(f"Resposta da API FS: {dados_fs}")
            return None
        
        print(f"✅ ID do diretório raiz: {id_raiz}")
        cache_diretorios['raiz'] = id_raiz
        
        # Verifica se Gikamura já existe e cacheia o ID
        children = data.get('children', [])
        for child in children:
            if child.get('name') == 'Gikamura' and child.get('isDirectory'):
                gikamura_id = child.get('id')
                cache_diretorios['Gikamura'] = gikamura_id
                print(f"✅ Diretório Gikamura já existe: {gikamura_id}")
                logging.info(f"Gikamura encontrado: {gikamura_id}")
                break
        
        logging.info(f"ID raiz obtido: {id_raiz}")
        return id_raiz
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")
        logging.error(f"Erro de conexão ao obter ID raiz: {e}")
        return None

def garantir_caminho_remoto(account_id: str, estrutura: EstruturaHierarquica) -> Optional[str]:
    """
    Garante que a estrutura hierárquica Gikamura/Scan/Serie/Capitulo exista no BuzzHeavier
    """
    headers = {"Authorization": f"Bearer {account_id}"}
    
    # Usar caminho remoto da estrutura validada
    caminho_remoto = estrutura.get_caminho_remoto()
    
    # Verificar se já está em cache
    if caminho_remoto in cache_diretorios:
        return cache_diretorios[caminho_remoto]
    
    # Se capítulo está vazio, vai direto para a série
    if estrutura.capitulo:
        print(f"Verificando estrutura hierárquica: '{estrutura.scan}/{estrutura.serie}/{estrutura.capitulo}'")
    else:
        print(f"Verificando estrutura hierárquica: '{estrutura.scan}/{estrutura.serie}/'")
        print(f"  📁 Upload direto na série (sem subpasta de capítulo)")
    
    # Começar do diretório Gikamura (já deve existir)
    if 'Gikamura' not in cache_diretorios:
        logging.error("Diretório Gikamura não encontrado no cache")
        return None
    
    id_diretorio_pai = cache_diretorios['Gikamura']
    
    # Hierarquia a ser criada: Scan -> Serie -> Capitulo (se não vazio)
    niveis = [
        ('Gikamura', estrutura.scan),      # Scan dentro de Gikamura
        (f'Gikamura/{estrutura.scan}', estrutura.serie),  # Serie dentro do Scan
    ]
    
    # Só adiciona capítulo se não estiver vazio
    if estrutura.capitulo:
        niveis.append((f'Gikamura/{estrutura.scan}/{estrutura.serie}', estrutura.capitulo))

    # Processar cada nível da hierarquia
    for caminho_cache, nome_diretorio in niveis:
        # Verificar se já está em cache
        if caminho_cache in cache_diretorios:
            id_diretorio_pai = cache_diretorios[caminho_cache]
            continue
        
        # Listar conteúdo do diretório pai
        url_get_dir = f"{API_URL_FS}/{id_diretorio_pai}"
        print(f"  - Verificando se '{nome_diretorio}' existe em {id_diretorio_pai}...")
        
        response = requests.get(url_get_dir, headers=headers)
        if response.status_code != 200:
            print(f"  ❌ Erro ao listar conteúdo! Status: {response.status_code}")
            logging.error(f"Erro ao listar diretório {id_diretorio_pai}: {response.status_code}")
            return None

        # Processar resposta da API
        response_data = response.json()
        if 'data' in response_data:
            conteudo_remoto = response_data['data'].get('children', [])
        else:
            conteudo_remoto = response_data.get('children', [])
        
        # Procurar diretório existente
        diretorio_encontrado = None
        for item in conteudo_remoto:
            is_directory = (item.get('type') == 'DIRECTORY' or 
                          item.get('type') == 'FOLDER' or 
                          item.get('isDirectory') == True)
            if item.get('name') == nome_diretorio and is_directory:
                diretorio_encontrado = item
                break
        
        if diretorio_encontrado:
            print(f"  ✅ {nome_diretorio} já existe")
            id_diretorio_pai = diretorio_encontrado['id']
        else:
            # Criar diretório
            print(f"  🔧 Criando {nome_diretorio}...")
            url_post_dir = f"{API_URL_FS}/{id_diretorio_pai}"
            payload = {"name": nome_diretorio}
            
            try:
                response_create = requests.post(url_post_dir, headers=headers, json=payload, timeout=30)
                
                if response_create.status_code == 200:
                    response_data = response_create.json()
                    novo_diretorio = response_data.get('data', response_data)
                    id_diretorio_pai = novo_diretorio['id']
                    print(f"  ✅ {nome_diretorio} criado (ID: {id_diretorio_pai})")
                elif response_create.status_code == 409:
                    # Diretório existe, recarregar para obter ID
                    print(f"  ℹ️  {nome_diretorio} já existe, obtendo ID...")
                    response_reload = requests.get(url_get_dir, headers=headers)
                    if response_reload.status_code == 200:
                        reload_data = response_reload.json()
                        if 'data' in reload_data:
                            conteudo_atualizado = reload_data['data'].get('children', [])
                        else:
                            conteudo_atualizado = reload_data.get('children', [])
                        
                        for item in conteudo_atualizado:
                            is_directory = (item.get('type') == 'DIRECTORY' or 
                                          item.get('type') == 'FOLDER' or 
                                          item.get('isDirectory') == True)
                            if item.get('name') == nome_diretorio and is_directory:
                                id_diretorio_pai = item['id']
                                print(f"  ✅ {nome_diretorio} encontrado (ID: {id_diretorio_pai})")
                                break
                        else:
                            logging.error(f"Diretório {nome_diretorio} existe mas não encontrado na listagem")
                            return None
                    else:
                        logging.error(f"Erro ao recarregar listagem: {response_reload.status_code}")
                        return None
                else:
                    print(f"  ❌ Erro ao criar {nome_diretorio}. Status: {response_create.status_code}")
                    logging.error(f"Erro ao criar {nome_diretorio}: {response_create.status_code} - {response_create.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                print(f"  ❌ Erro de conexão ao criar {nome_diretorio}: {e}")
                logging.error(f"Erro de conexão ao criar {nome_diretorio}: {e}")
                return None
        
        # Atualizar cache
        cache_diretorios[caminho_cache] = id_diretorio_pai
        time.sleep(0.3)  # Pequena pausa entre criações
    
    # Cachear o caminho completo
    cache_diretorios[caminho_remoto] = id_diretorio_pai
    return id_diretorio_pai

def sincronizar_arquivo(account_id: str, estrutura: EstruturaHierarquica, id_destino: str, config_data: dict) -> bool:
    """Sincroniza um arquivo com verificação de integridade"""
    headers = {"Authorization": f"Bearer {account_id}"}
    nome_arquivo = estrutura.arquivo
    caminho_local = estrutura.caminho_local
    
    try:
        # Calcula hash do arquivo local se verificação estiver habilitada
        local_hash = None
        if config_data['verify_integrity']:
            local_hash = calculate_file_hash(caminho_local)
            if not local_hash:
                logging.error(f"Não foi possível calcular hash de {nome_arquivo}")
                sync_stats.add_failed()
                sync_state.mark_failed(caminho_local)
                return False
        
        # Verifica se arquivo já foi enviado com mesmo hash (resume)
        if config_data['resume_uploads'] and local_hash:
            if sync_state.is_uploaded(caminho_local, local_hash):
                print(f"  ✅ SKIP: '{nome_arquivo}' (já enviado)")
                sync_stats.add_skipped()
                salvar_log_serie(estrutura, "pulado", "Arquivo já enviado (resume)")
                return True
        
        # Verifica conteúdo do diretório remoto
        url_get_dir = f"{API_URL_FS}/{id_destino}"
        response = requests.get(url_get_dir, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"    ❌ ERRO: Não foi possível verificar diretório {id_destino}")
            logging.error(f"Erro ao listar diretório {id_destino}: {response.status_code}")
            sync_stats.add_failed()
            sync_state.mark_failed(caminho_local)
            return False

        # Verifica se arquivo já existe remotamente
        response_data = response.json()
        if 'data' in response_data:
            children = response_data['data'].get('children', [])
        else:
            children = response_data.get('children', [])
            
        remote_file = None
        for item in children:
            if item.get('name') == nome_arquivo and item.get('type') == 'FILE':
                remote_file = item
                break
        
        if remote_file:
            # Arquivo existe - atualiza log como sucesso
            tamanho_remoto = remote_file.get('size', 0)
            print(f"  ✅ EXISTE: '{nome_arquivo}' ({format_size(tamanho_remoto)}) - atualizando log")
            
            # Salva no log como sucesso com informações do arquivo remoto
            detalhes = f"Arquivo já existe no servidor - {format_size(tamanho_remoto)}"
            if local_hash:
                detalhes += f" | Hash local: {local_hash[:8]}..."
                
            sync_stats.add_skipped()
            sync_state.mark_uploaded(caminho_local, local_hash)
            salvar_log_serie(estrutura, "sucesso", detalhes, local_hash)
            return True

        # Arquivo não existe - fazer upload
        file_size = os.path.getsize(caminho_local)
        print(f"    \033[1;94m⬆️  UPLOAD\033[0m: \033[1m{nome_arquivo}\033[0m \033[2m({format_size(file_size)})\033[0m")
        
        nome_arquivo_enc = quote(nome_arquivo)
        url_upload = f"{UPLOAD_URL_BASE}/{id_destino}/{nome_arquivo_enc}"

        # Cria monitor de progresso
        progress_monitor = UploadProgressMonitor(nome_arquivo, file_size)
        
        # Implementa retry com backoff exponencial para problemas de SSL
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(caminho_local, 'rb') as f:
                    # Wrapper que monitora o progresso
                    file_wrapper = FileUploadWrapper(f, progress_monitor)
                    upload_response = requests.put(
                        url_upload, 
                        headers=headers, 
                        data=file_wrapper, 
                        timeout=300,
                        verify=True,  # Verificação SSL habilitada
                        stream=False   # Não usar streaming para evitar problemas SSL
                    )
                break  # Se chegou aqui, upload foi bem-sucedido
            except requests.exceptions.SSLError as ssl_error:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Backoff exponencial: 1s, 2s, 4s
                    print(f"    ⚠️  Erro SSL (tentativa {attempt + 1}/{max_retries}). Tentando novamente em {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"    ❌ ERRO: Falha de conexão: {ssl_error}")
                    logging.error(f"Erro de conexão no upload de {nome_arquivo}: {ssl_error}")
                    sync_stats.add_failed()
                    sync_state.mark_failed(caminho_local)
                    salvar_log_serie(estrutura, "falha", f"Erro de conexão: {ssl_error}")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"    ⚠️  Erro de upload (tentativa {attempt + 1}/{max_retries}). Tentando novamente em {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"    ❌ ERRO: {e}")
                    logging.error(f"Erro no upload de {nome_arquivo}: {e}")
                    sync_stats.add_failed()
                    sync_state.mark_failed(caminho_local)
                    salvar_log_serie(estrutura, "falha", f"Erro: {e}")
                    return False

        if upload_response.status_code in [200, 201]:  # 200 OK ou 201 Created
            print(f"    \033[1;32m✅ SUCESSO\033[0m: \033[1m{nome_arquivo}\033[0m enviado")
            sync_stats.add_uploaded(file_size)
            
            # Marca como enviado no estado
            if local_hash:
                sync_state.mark_uploaded(caminho_local, local_hash)
            
            # Log de sucesso na série
            salvar_log_serie(estrutura, "sucesso", f"Upload realizado - {format_size(file_size)}")
            
            logging.info(f"Upload bem-sucedido: {nome_arquivo} ({format_size(file_size)})")
            return True
        else:
            print(f"    ❌ ERRO: Upload falhou (Status {upload_response.status_code})")
            logging.error(f"Erro no upload de {nome_arquivo}: {upload_response.status_code} - {upload_response.text}")
            sync_stats.add_failed()
            sync_state.mark_failed(caminho_local)
            salvar_log_serie(estrutura, "falha", f"Erro HTTP {upload_response.status_code}")
            return False
            
    except FileNotFoundError:
        print(f"    ❌ ERRO: Arquivo não encontrado: {caminho_local}")
        logging.error(f"Arquivo não encontrado: {caminho_local}")
        sync_stats.add_failed()
        sync_state.mark_failed(caminho_local)
        salvar_log_serie(estrutura, "falha", "Arquivo não encontrado")
        return False
    except requests.exceptions.RequestException as e:
        print(f"    ❌ ERRO: Falha de conexão: {e}")
        logging.error(f"Erro de conexão no upload de {nome_arquivo}: {e}")
        sync_stats.add_failed()
        sync_state.mark_failed(caminho_local)
        salvar_log_serie(estrutura, "falha", f"Erro de conexão: {str(e)}")
        return False
    except Exception as e:
        print(f"    ❌ ERRO: {e}")
        logging.error(f"Erro inesperado no upload de {nome_arquivo}: {e}")
        sync_stats.add_failed()
        sync_state.mark_failed(caminho_local)
        salvar_log_serie(estrutura, "falha", f"Erro inesperado: {str(e)}")
        return False

def exibir_estrutura_esperada(config_data: dict):
    """Exibe como o sistema espera encontrar a estrutura de pastas"""
    print(f"\n\033[1;33m📋 ESTRUTURA ESPERADA DO PROJETO\033[0m")
    print("\033[1;36m" + "="*70 + "\033[0m")
    
    # Configurações ativas
    print(f"\033[1;34m🔧 CONFIGURAÇÕES ATIVAS:\033[0m")
    print(f"   📂 Pasta raiz: \033[1m{config_data['root_path']}\033[0m")
    
    # Filtros de arquivo
    if config_data['allowed_extensions']:
        exts = ', '.join(sorted(config_data['allowed_extensions']))
        print(f"   ✅ Extensões permitidas: \033[92m{exts}\033[0m")
    else:
        print(f"   ✅ Extensões permitidas: \033[92mTodas\033[0m")
    
    if config_data['blocked_extensions']:
        blocked = ', '.join(sorted(config_data['blocked_extensions']))
        print(f"   🚫 Extensões bloqueadas: \033[91m{blocked}\033[0m")
    
    if config_data['max_file_size'] > 0:
        max_size = format_size(config_data['max_file_size'])
        print(f"   📏 Tamanho máximo: \033[93m{max_size}\033[0m")
    else:
        print(f"   📏 Tamanho máximo: \033[93mSem limite\033[0m")
    
    # Funcionalidades ativas
    features = []
    if config_data['verify_integrity']:
        features.append("🔒 Verificação de integridade")
    if config_data['resume_uploads']:
        features.append("🔄 Resume de uploads")
    if config_data.get('consolidation_enabled', False):
        consolidation_available = verificar_consolidacao_disponivel()
        if consolidation_available:
            features.append("📦 Consolidação de capítulos (Linux + libimagequant)")
        else:
            features.append("❌ Consolidação (indisponível)")
    
    # Info sobre threading
    max_workers = config_data.get('max_workers', 3)
    features.append(f"🚀 {max_workers} threads paralelas")
    
    if features:
        print(f"   🛠️  Recursos ativos: \033[96m{' • '.join(features)}\033[0m")
    
    print()
    print(f"\033[1;35m🗂️  ESTRUTURA DE PASTAS ESPERADA:\033[0m")
    print(f"   \033[92mSincronizada no BuzzHeavier:\033[0m")
    print(f"   \033[2m📁 {config_data['agregador']}/\033[0m \033[96m(Agregador)\033[0m")
    print(f"   \033[2m├── 📁 Nome do Scan/\033[0m \033[93m(Scan/Grupo)\033[0m")
    print(f"   \033[2m│   ├── 📁 Nome da Série/\033[0m \033[94m(Série/Obra)\033[0m") 
    print(f"   \033[2m│   │   ├── 📁 Capítulo 01/\033[0m \033[95m(Capítulo)\033[0m")
    print(f"   \033[2m│   │   │   ├── 🖼️ 01.jpg\033[0m")
    print(f"   \033[2m│   │   │   ├── 🖼️ 02.png\033[0m")
    print(f"   \033[2m│   │   │   └── 🖼️ 03.webp\033[0m")
    print(f"   \033[2m│   │   └── 📁 Capítulo 02/\033[0m")
    print(f"   \033[2m│   │       └── 🖼️ 01.png\033[0m")
    print(f"   \033[2m│   └── 📁 Outra Série/\033[0m")
    print(f"   \033[2m│       └── 📁 Capítulo 01/\033[0m")
    print(f"   \033[2m│           └── 🖼️ 01.jpg\033[0m")
    print(f"   \033[2m└── 📁 Outro Scan/\033[0m")
    print(f"   \033[2m    └── 📁 Série XYZ/\033[0m")
    print(f"   \033[2m        └── 📁 Parte 1/\033[0m")
    print(f"   \033[2m            └── 🖼️ 01.png\033[0m")
    
    print()
    print(f"   \033[91mApenas local (não sincronizado):\033[0m")
    print(f"   \033[2m📁 _LOGS/\033[0m \033[96m(Registros locais - fonte da verdade)\033[0m")
    print(f"   \033[2m├── 📈 Gikamura_Scan_Serie.json\033[0m")
    print(f"   \033[2m└── 📈 outros_logs.json\033[0m")
    
    print()
    print(f"\033[1;32m💡 FUNCIONAMENTO:\033[0m")
    print(f"   • \033[92mSincronizado:\033[0m Estrutura de agregador/scan/série/capítulo")
    print(f"   • \033[91mLocal apenas:\033[0m Pasta _LOGS com registros e controle")
    print(f"   • Diretórios são criados automaticamente no BuzzHeavier")
    print(f"   • Arquivos já enviados são detectados via hash MD5")
    print(f"   • Resume inteligente baseado no estado salvo localmente")
    print("\033[1;36m" + "="*70 + "\033[0m")

def exibir_relatorio_falhas():
    """Exibe relatório detalhado de arquivos que falharam"""
    failed_files = sync_state.get_failed_files()
    
    if not failed_files:
        print("\n✅ Nenhum arquivo falhou na sincronização!")
        return
    
    print(f"\n\033[1;91m📋 RELATÓRIO DE ARQUIVOS QUE FALHARAM\033[0m")
    print("\033[1;36m" + "="*70 + "\033[0m")
    print(f"\033[1;91m❌ Total de arquivos que falharam: {len(failed_files)}\033[0m")
    print()
    
    for i, file_path in enumerate(failed_files, 1):
        file_exists = "✅" if os.path.exists(file_path) else "❌"
        file_size = format_size(os.path.getsize(file_path)) if os.path.exists(file_path) else "N/A"
        print(f"{i:3d}. {file_exists} {os.path.basename(file_path)} ({file_size})")
        print(f"     📁 {file_path}")
    
    print("\n\033[1;33m💡 COMANDOS DISPONÍVEIS:\033[0m")
    print("   • Para tentar novamente: python3 sync_buzzheavier.py --retry-failed")
    print("   • Para limpar lista: python3 sync_buzzheavier.py --clear-failed")
    print("   • Para ver relatório: python3 sync_buzzheavier.py --show-failed")

def processar_arquivos_falhados(config_data: dict) -> bool:
    """Processa apenas arquivos que falharam anteriormente"""
    print("\n\033[1;33m🔄 MODO RECUPERAÇÃO: Tentando novamente arquivos que falharam\033[0m")
    print("\033[1;36m" + "="*70 + "\033[0m")
    
    # Obtém arquivos que falharam e ainda existem
    failed_files = sync_state.retry_failed_files()
    
    if not failed_files:
        print("✅ Nenhum arquivo válido para tentar novamente!")
        return True
    
    print(f"🔄 Encontrados {len(failed_files)} arquivos para retry")
    
    # Mapeia arquivos que falharam para estruturas válidas
    estruturas_retry = []
    for file_path in failed_files:
        if file_path.startswith('/tmp/'):
            # Arquivo temporário - pular (será regenerado)
            print(f"⚠️  Pulando arquivo temporário: {os.path.basename(file_path)}")
            sync_state.failed_files.discard(file_path)
            continue
            
        # Valida estrutura do arquivo
        estrutura = validar_e_mapear_estrutura(file_path, config_data['root_path'], config_data['agregador'])
        if estrutura:
            estruturas_retry.append(estrutura)
        else:
            print(f"❌ Estrutura inválida, removendo da lista: {os.path.basename(file_path)}")
            sync_state.failed_files.discard(file_path)
    
    if not estruturas_retry:
        print("⚠️  Nenhum arquivo válido encontrado para retry")
        return True
    
    # Obtém ID raiz
    account_id = config_data['account_id']
    if not obter_id_raiz(account_id):
        print("❌ Não foi possível obter ID do diretório raiz para retry")
        return False
    
    # Inicializa estatísticas para retry
    sync_stats.start_time = datetime.now()
    sync_stats.total_files = len(estruturas_retry)
    sync_stats.uploaded_files = 0
    sync_stats.failed_files = 0
    sync_stats.skipped_files = 0
    
    print(f"\n🚀 Iniciando retry com {len(estruturas_retry)} arquivos...")
    
    # Processa arquivos em retry
    progress = ProgressBar(len(estruturas_retry), "Retry")
    success_count = 0
    
    for estrutura in estruturas_retry:
        try:
            id_diretorio_destino = garantir_caminho_remoto(account_id, estrutura)
            if id_diretorio_destino:
                resultado = sincronizar_arquivo(account_id, estrutura, id_diretorio_destino, config_data)
                if resultado:
                    success_count += 1
            progress.update()
        except Exception as e:
            print(f"❌ Erro no retry de {estrutura.arquivo}: {e}")
            progress.update()
    
    # Salva estado atualizado
    sync_state.save()
    
    print(f"\n\033[1;32m📊 RESULTADO DO RETRY:\033[0m")
    print(f"   ✅ Sucessos: {success_count}/{len(estruturas_retry)}")
    print(f"   ❌ Falhas restantes: {len(sync_state.get_failed_files())}")
    
    return success_count > 0

def exibir_estatisticas_finais():
    """Exibe estatísticas finais da sincronização"""
    elapsed = time.time() - sync_stats.start_time.timestamp() if sync_stats.start_time else 0
    
    print("\n" + "\033[1;36m" + "="*70 + "\033[0m")
    print("\033[1;35m📊 RELATÓRIO FINAL DA SINCRONIZAÇÃO\033[0m".center(70))
    print("\033[1;36m" + "="*70 + "\033[0m")
    
    # Tempo e estatísticas principais
    print(f"\033[1;33m⏱️  Tempo total:\033[0m {int(elapsed // 60):02d}h:{int(elapsed % 60):02d}m")
    print(f"\033[1;34m📄 Total de arquivos:\033[0m \033[1m{sync_stats.total_files:,}\033[0m")
    print()
    
    # Resultados coloridos
    success_rate = ((sync_stats.uploaded_files + sync_stats.skipped_files) / max(sync_stats.total_files, 1) * 100)
    
    print(f"\033[1;32m⬆️  Arquivos enviados:\033[0m \033[1;32m{sync_stats.uploaded_files:,}\033[0m")
    print(f"\033[1;36m✅ Arquivos existentes:\033[0m \033[1;36m{sync_stats.skipped_files:,}\033[0m")
    
    if sync_stats.failed_files > 0:
        print(f"\033[1;91m❌ Arquivos com erro:\033[0m \033[1;91m{sync_stats.failed_files:,}\033[0m")
    
    print()
    print(f"\033[1;35m💾 Dados enviados:\033[0m \033[1m{format_size(sync_stats.uploaded_size)}\033[0m")
    
    # Taxa de sucesso com cor baseada na performance
    if success_rate >= 95:
        rate_color = '\033[1;32m'  # Verde
        rate_emoji = '🎉'
    elif success_rate >= 80:
        rate_color = '\033[1;33m'  # Amarelo
        rate_emoji = '👍'
    else:
        rate_color = '\033[1;91m'  # Vermelho
        rate_emoji = '⚠️'
        
    print(f"\033[1;34m📈 Taxa de sucesso:\033[0m {rate_color}{rate_emoji} {success_rate:.1f}%\033[0m")
    
    if sync_stats.uploaded_size > 0 and elapsed > 0:
        speed = sync_stats.uploaded_size / elapsed
        if speed > 1024 * 1024:  # > 1MB/s
            speed_color = '\033[1;32m'  # Verde
            speed_emoji = '🚀'
        elif speed > 512 * 1024:  # > 512KB/s
            speed_color = '\033[1;33m'  # Amarelo
            speed_emoji = '✈️'
        else:
            speed_color = '\033[1;91m'  # Vermelho
            speed_emoji = '🐢'
        print(f"\033[1;35m🚀 Velocidade média:\033[0m {speed_color}{speed_emoji} {format_size(speed)}/s\033[0m")
    
    # Informações sobre falhas e comandos disponíveis
    failed_count = len(sync_state.get_failed_files())
    if failed_count > 0:
        print(f"\n\033[1;91m⚠️  ATENÇÃO: {failed_count} arquivos falharam\033[0m")
        print("\033[1;33m💡 Comandos para recuperação:\033[0m")
        print("   • Ver falhas: python3 sync_buzzheavier.py --show-failed")
        print("   • Tentar novamente: python3 sync_buzzheavier.py --retry-failed")
        print("   • Limpar lista: python3 sync_buzzheavier.py --clear-failed")
    
    print("\033[1;36m" + "="*70 + "\033[0m")

def mostrar_menu_principal():
    """Mostra menu principal interativo"""
    print("\n" + "="*60)
    print("🚀 BUZZHEAVIER SYNC ENHANCED v2.0".center(60))
    print("="*60)
    
    print("\n📋 OPÇÕES DISPONÍVEIS:")
    print("   1. 🔄 Sincronizar arquivos")
    print("   2. 📊 Ver estatísticas")
    print("   3. ❌ Ver/corrigir falhas")
    print("   4. ⚙️  Configurações")
    print("   5. ❓ Ajuda")
    print("   0. 🚪 Sair")
    
    return input("\n👉 Escolha uma opção: ").strip()

def mostrar_menu_falhas():
    """Menu para gerenciar falhas"""
    failed_files = sync_state.get_failed_files()
    
    print(f"\n❌ GERENCIAR FALHAS ({len(failed_files)} arquivos)")
    print("-" * 50)
    
    if failed_files:
        print(f"📋 {len(failed_files)} arquivos falharam:")
        for i, file_path in enumerate(failed_files[:5], 1):
            nome = os.path.basename(file_path)
            existe = "✅" if os.path.exists(file_path) else "❌"
            print(f"   {i}. {existe} {nome}")
        
        if len(failed_files) > 5:
            print(f"   ... e mais {len(failed_files) - 5} arquivos")
    else:
        print("✅ Nenhum arquivo falhou!")
        return None
    
    print("\n📋 OPÇÕES:")
    print("   1. 🔄 Tentar novamente")
    print("   2. 🧹 Limpar lista")
    print("   3. 📄 Ver detalhes")
    print("   0. ⬅️  Voltar")
    
    return input("\n👉 Escolha: ").strip()

def verificar_e_executar_retry_automatico():
    """Verifica arquivos com falha e executa retry automático"""
    sync_state.load()
    failed_files = sync_state.retry_failed_files()
    
    if not failed_files:
        return
    
    print(f"\n🔄 Encontrados {len(failed_files)} arquivos com falha")
    print("🚀 Iniciando retry automático...")
    
    # Obtém ID do diretório raiz
    try:
        config_data = carregar_configuracao()
        account_id = obter_account_id(config_data)
        
        if not account_id:
            print("❌ Não foi possível obter ID do diretório raiz para retry")
            return
        
        # Converte arquivos para estruturas
        estruturas_retry = []
        for arquivo in failed_files:
            if os.path.exists(arquivo):
                estrutura = EstruturaHierarquica.from_path(arquivo)
                if estrutura:
                    estruturas_retry.append(estrutura)
        
        if not estruturas_retry:
            print("⚠️  Nenhum arquivo válido encontrado para retry")
            return
        
        # Executa retry
        sync_stats.reset()
        sync_stats.total_files = len(estruturas_retry)
        
        success_count = 0
        progress = ProgressBar(len(estruturas_retry), "Retry Automático")
        
        for estrutura in estruturas_retry:
            progress.update()
            try:
                resultado = processar_arquivo_individual(estrutura, account_id, config_data, None)
                if resultado > 0:
                    success_count += 1
                    sync_state.remove_failed_file(estrutura.arquivo)
            except Exception as e:
                print(f"❌ Erro no retry de {estrutura.arquivo}: {e}")
        
        progress.finish()
        sync_state.save()
        
        print(f"\n✅ Retry automático concluído!")
        print(f"   ✅ Sucessos: {success_count}/{len(estruturas_retry)}")
        print(f"   ❌ Restantes: {len(estruturas_retry) - success_count}")
        
    except Exception as e:
        print(f"❌ Erro no retry automático: {e}")
    
    input("\nPressione Enter para continuar...")

def main():
    """Função principal com menu interativo"""
    # Configura logging silencioso
    logging.basicConfig(level=logging.ERROR, format='%(message)s')
    
    while True:
        try:
            # Carrega estado
            sync_state.load()
            
            opcao = mostrar_menu_principal()
            
            if opcao == "0":
                print("\n👋 Até logo!")
                break
            elif opcao == "1":
                # Sincronização
                executar_sincronizacao()
            elif opcao == "2":
                # Estatísticas
                mostrar_estatisticas_simples()
            elif opcao == "3":
                # Gerenciar falhas
                while True:
                    opcao_falha = mostrar_menu_falhas()
                    if opcao_falha == "0" or opcao_falha is None:
                        break
                    elif opcao_falha == "1":
                        tentar_novamente_falhas()
                    elif opcao_falha == "2":
                        sync_state.clear_failed_files()
                        sync_state.save()
                        print("✅ Lista limpa!")
                        input("Pressione Enter...")
                    elif opcao_falha == "3":
                        mostrar_detalhes_falhas()
            elif opcao == "4":
                # Configurações
                mostrar_configuracoes()
            elif opcao == "5":
                # Ajuda
                mostrar_ajuda()
            else:
                print("❌ Opção inválida!")
                input("Pressione Enter...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrompido pelo usuário. Até logo!")
            break
        except Exception as e:
            print(f"\n❌ Erro inesperado: {e}")
            input("Pressione Enter...")

def executar_sincronizacao():
    """Executa sincronização com logs simplificados"""
    print("\n🔄 INICIANDO SINCRONIZAÇÃO...")
    print("="*50)
    
    # Carrega configurações
    config_data = carregar_config()
    if not config_data:
        print("❌ Erro na configuração!")
        input("Pressione Enter...")
        return
    
    print(f"📂 Pasta: {config_data['agregador']}")
    print(f"⚙️  Threads: {config_data['max_workers']}")
    
    # Carrega estado de sincronização
    sync_state.load()
    
    # Obtém ID raiz
    account_id = config_data['account_id']
    if not obter_id_raiz(account_id):
        print("❌ Erro ao conectar com BuzzHeavier!")
        input("Pressione Enter...")
        return
    
    print("🔍 Analisando arquivos...")
    
    # Mapeia arquivos (versão silenciosa)
    estruturas_validas = mapear_arquivos_locais_silencioso(config_data['root_path'], config_data)
    
    if not estruturas_validas:
        print("⚠️  Nenhum arquivo válido encontrado!")
        input("Pressione Enter...")
        return
    
    # Cache inteligente
    logs_existentes = carregar_logs_existentes()
    status_capitulos = analisar_status_capitulos(logs_existentes)
    estruturas_para_processar = filtrar_arquivos_por_cache(estruturas_validas, status_capitulos)
    
    if not estruturas_para_processar:
        print("✅ Todos os arquivos já foram enviados!")
        input("Pressione Enter...")
        return
    
    print(f"📊 {len(estruturas_para_processar)} arquivos para enviar")
    print(f"💾 {format_size(sum(os.path.getsize(e.caminho_local) for e in estruturas_para_processar))}")
    
    print("\n🚀 Iniciando upload automaticamente...")
    
    # Inicia sincronização com progresso simplificado
    processar_sincronizacao_simples(estruturas_para_processar, account_id, config_data)

def mostrar_estatisticas_simples():
    """Mostra estatísticas de forma simplificada"""
    print("\n📊 ESTATÍSTICAS")
    print("="*40)
    
    # Conta arquivos em cache
    logs_existentes = carregar_logs_existentes()
    total_sucessos = 0
    total_falhas = 0
    
    for chave, log_data in logs_existentes.items():
        stats = log_data.get('estatisticas', {})
        total_sucessos += stats.get('sucessos', 0)
        total_falhas += stats.get('falhas', 0)
    
    failed_count = len(sync_state.get_failed_files())
    
    print(f"✅ Arquivos enviados: {total_sucessos}")
    print(f"❌ Falhas totais: {total_falhas}")
    print(f"⚠️  Falhas pendentes: {failed_count}")
    
    if logs_existentes:
        print(f"\n📚 Séries processadas: {len(logs_existentes)}")
        print("\n🏆 RANKING DE UPLOADS:")
        
        series_stats = []
        for chave, log_data in logs_existentes.items():
            serie = log_data.get('serie', 'Desconhecida')
            sucessos = log_data.get('estatisticas', {}).get('sucessos', 0)
            if sucessos > 0:
                series_stats.append((serie, sucessos))
        
        series_stats.sort(key=lambda x: x[1], reverse=True)
        for i, (serie, count) in enumerate(series_stats[:5], 1):
            print(f"   {i}. {serie}: {count} arquivos")
    
    input("\nPressione Enter...")

def tentar_novamente_falhas():
    """Tenta novamente arquivos que falharam"""
    print("\n🔄 TENTANDO NOVAMENTE...")
    
    config_data = carregar_config()
    if not config_data:
        print("❌ Erro na configuração!")
        input("Pressione Enter...")
        return
    
    sucesso = processar_arquivos_falhados(config_data)
    if sucesso:
        print("✅ Retry concluído!")
    else:
        print("❌ Nenhum arquivo foi recuperado")
    
    input("Pressione Enter...")

def mostrar_detalhes_falhas():
    """Mostra detalhes das falhas"""
    failed_files = sync_state.get_failed_files()
    
    print(f"\n📄 DETALHES DAS FALHAS ({len(failed_files)})")
    print("="*50)
    
    for i, file_path in enumerate(failed_files, 1):
        nome = os.path.basename(file_path)
        existe = "✅" if os.path.exists(file_path) else "❌"
        tamanho = format_size(os.path.getsize(file_path)) if os.path.exists(file_path) else "N/A"
        
        print(f"{i:2d}. {existe} {nome}")
        print(f"    📁 {file_path}")
        print(f"    💾 {tamanho}")
        print()
    
    input("Pressione Enter...")

def mostrar_configuracoes():
    """Mostra configurações atuais"""
    config_data = carregar_config()
    
    print("\n⚙️  CONFIGURAÇÕES")
    print("="*40)
    
    if config_data:
        print(f"📂 Pasta raiz: {config_data['root_path']}")
        print(f"🏷️  Agregador: {config_data['agregador']}")
        print(f"🚀 Threads: {config_data['max_workers']}")
        print(f"📦 Consolidação: {'✅' if config_data.get('consolidation_enabled') else '❌'}")
        print(f"🔒 Verificação: {'✅' if config_data.get('verify_integrity') else '❌'}")
        print(f"🔄 Resume: {'✅' if config_data.get('resume_uploads') else '❌'}")
    else:
        print("❌ Erro ao carregar configurações!")
    
    input("\nPressione Enter...")

def mostrar_ajuda():
    """Mostra ajuda do sistema"""
    print("\n❓ AJUDA")
    print("="*40)
    print("🔄 SINCRONIZAÇÃO:")
    print("   • Analisa a pasta configurada")
    print("   • Envia apenas arquivos novos")
    print("   • Consolida capítulos em PNG únicos")
    print("   • Resume uploads interrompidos")
    print()
    print("📊 ESTATÍSTICAS:")
    print("   • Mostra arquivos enviados")
    print("   • Ranking de séries")
    print("   • Falhas pendentes")
    print()
    print("❌ FALHAS:")
    print("   • Lista arquivos que falharam")
    print("   • Permite retry automático")
    print("   • Limpeza de lista")
    print()
    print("⚙️  CONFIGURAÇÕES:")
    print("   • Edite config.ini para personalizar")
    print("   • Pasta raiz, threads, etc.")
    
    input("\nPressione Enter...")

def mapear_arquivos_locais_silencioso(pasta_raiz: str, config_data: dict) -> List[EstruturaHierarquica]:
    """Versão silenciosa do mapeamento de arquivos"""
    if not os.path.isdir(pasta_raiz):
        return []
    
    estruturas_validas = []
    
    for pasta_atual, subpastas, arquivos in os.walk(pasta_raiz):
        if '_LOGS' in subpastas:
            subpastas.remove('_LOGS')
        for nome_arquivo in arquivos:
            caminho_completo = os.path.join(pasta_atual, nome_arquivo)
            
            if '_LOGS' in caminho_completo:
                continue
            
            try:
                estrutura = validar_e_mapear_estrutura(caminho_completo, config_data['root_path'], config_data['agregador'])
                if estrutura and should_sync_file(caminho_completo, 
                                                config_data['allowed_extensions'],
                                                config_data['blocked_extensions'], 
                                                config_data['max_file_size']):
                    estruturas_validas.append(estrutura)
            except (OSError, IOError):
                continue
    
    return estruturas_validas

def processar_sincronizacao_simples(estruturas_para_processar: List[EstruturaHierarquica], account_id: str, config_data: dict):
    """Processamento simplificado com logs mínimos"""
    print(f"\n🚀 Enviando {len(estruturas_para_processar)} arquivos...")
    
    # Inicia estatísticas
    sync_stats.start_time = datetime.now()
    sync_stats.total_files = len(estruturas_para_processar)
    sync_stats.uploaded_files = 0
    sync_stats.failed_files = 0
    sync_stats.skipped_files = 0
    
    try:
        if config_data.get('consolidation_enabled', False):
            # Agrupa por capítulo
            capitulos = agrupar_por_capitulo(estruturas_para_processar)
            
            progress_count = 0
            total_capitulos = len(capitulos)
            
            # Processa em lotes para evitar sobrecarga de memória
            lote_size = 5  # Reduzido para evitar 'Killed'
            capitulos_lista = list(capitulos.items())
            
            for i in range(0, len(capitulos_lista), lote_size):
                lote = capitulos_lista[i:i+lote_size]
                print(f"🔄 Processando lote {(i//lote_size)+1}/{(len(capitulos_lista)+lote_size-1)//lote_size}")
                
                with ThreadPoolExecutor(max_workers=min(2, config_data.get('max_workers', 3))) as executor:
                    tasks = []
                    for chave_capitulo, arquivos_capitulo in lote:
                        task = executor.submit(processar_capitulo_simples, chave_capitulo, arquivos_capitulo, account_id, config_data)
                        tasks.append(task)
                    
                    for j, task in enumerate(tasks, 1):
                        try:
                            task.result()
                            progresso = ((i + j) / total_capitulos) * 100
                            print(f"📈 Progresso: {progresso:.1f}% ({i + j}/{total_capitulos} capítulos)")
                        except Exception as e:
                            print(f"❌ Erro: {e}")
                            sync_stats.add_failed()
        else:
            # Modo arquivo individual
            with ThreadPoolExecutor(max_workers=config_data.get('max_workers', 3)) as executor:
                tasks = []
                for estrutura in estruturas_para_processar:
                    task = executor.submit(processar_arquivo_individual, estrutura, account_id, config_data, None)
                    tasks.append(task)
                
                for i, task in enumerate(tasks, 1):
                    try:
                        task.result()
                        progresso = (i / len(estruturas_para_processar)) * 100
                        print(f"📈 Progresso: {progresso:.1f}% ({i}/{len(estruturas_para_processar)} arquivos)")
                    except Exception as e:
                        print(f"❌ Erro: {e}")
                        sync_stats.add_failed()
    
    except KeyboardInterrupt:
        print("\n⚠️  Upload interrompido pelo usuário")
    
    # Salva estado
    sync_state.save()
    
    # Resumo final
    print(f"\n✅ CONCLUÍDO!")
    print(f"📤 Enviados: {sync_stats.uploaded_files}")
    print(f"❌ Falhas: {sync_stats.failed_files}")
    
    if sync_stats.failed_files > 0:
        print("💡 Use a opção 'Ver/corrigir falhas' no menu principal")
    
    input("\nPressione Enter...")

def processar_capitulo_simples(chave_capitulo: str, arquivos_capitulo: List[EstruturaHierarquica], account_id: str, config_data: dict) -> int:
    """Versão simplificada do processamento de capítulo"""
    try:
        # Verifica se o capítulo consolidado já foi processado com sucesso
        estrutura_base = arquivos_capitulo[0]
        if verificar_sucesso_no_log(estrutura_base):
            print(f"  ⏭️  PULANDO CAPÍTULO: '{estrutura_base.capitulo}' (já processado com sucesso)")
            return 1
            
        # Se só tem 1 arquivo ou consolidação desabilitada
        if len(arquivos_capitulo) == 1 or not verificar_consolidacao_disponivel():
            for estrutura in arquivos_capitulo:
                id_diretorio_destino = garantir_caminho_remoto(account_id, estrutura)
                if id_diretorio_destino:
                    sincronizar_arquivo(account_id, estrutura, id_diretorio_destino, config_data)
        else:
            # Consolidação
            caminhos_imagens = [est.caminho_local for est in arquivos_capitulo]
            estrutura_base = arquivos_capitulo[0]
            
            arquivo_consolidado = consolidar_capitulo(caminhos_imagens, estrutura_base, config_data)
            
            if arquivo_consolidado and config_data.get('consolidation_upload_consolidated', True):
                # Extrai nome original
                nome_temp = os.path.basename(arquivo_consolidado)
                if '_' in nome_temp:
                    nome_original = '_'.join(nome_temp.split('_')[1:])
                else:
                    nome_original = nome_temp
                
                estrutura_consolidada = EstruturaHierarquica(
                    agregador=estrutura_base.agregador,
                    scan=estrutura_base.scan,
                    serie=estrutura_base.serie,
                    capitulo="",
                    arquivo=nome_original,
                    caminho_local=arquivo_consolidado,
                    caminho_relativo=f"{estrutura_base.agregador}/{estrutura_base.scan}/{estrutura_base.serie}/{nome_original}"
                )
                
                id_diretorio_serie = garantir_caminho_remoto(account_id, estrutura_consolidada)
                if id_diretorio_serie:
                    sincronizar_arquivo(account_id, estrutura_consolidada, id_diretorio_serie, config_data)
                
                # Remove arquivo temporário
                try:
                    os.remove(arquivo_consolidado)
                except:
                    pass
        
        return len(arquivos_capitulo)
        
    except Exception as e:
        print(f"❌ Erro no capítulo {chave_capitulo}: {e}")
        sync_stats.add_failed()
        return 0

if __name__ == "__main__":
    main()
