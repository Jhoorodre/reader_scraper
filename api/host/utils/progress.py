#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitários de progresso e interface de usuário
"""

import time
from typing import Optional


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
        if percent < 30:
            emoji = "🔴"
        elif percent < 70:
            emoji = "🟡"
        else:
            emoji = "🟢"
        
        print(f"\r{emoji} {self.description}: {bar} {percent:.1f}% ({self.current}/{self.total}) ETA: {eta}{speed_text}", end='', flush=True)
    
    def finish(self):
        """Finaliza a barra de progresso"""
        self._display()
        print()  # Nova linha


class StatusDisplay:
    """Display de status para operações longas"""
    
    def __init__(self, initial_message: str = "Processando..."):
        self.message = initial_message
        self.start_time = time.time()
        self._last_update = 0
    
    def update(self, message: str, force: bool = False):
        """Atualiza mensagem de status"""
        current_time = time.time()
        
        # Atualiza no máximo a cada 0.5s para evitar spam
        if force or (current_time - self._last_update) >= 0.5:
            elapsed = current_time - self.start_time
            elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
            
            print(f"\r⏳ {message} [{elapsed_str}]", end='', flush=True)
            self._last_update = current_time
            self.message = message
    
    def finish(self, final_message: Optional[str] = None):
        """Finaliza o display de status"""
        if final_message:
            elapsed = time.time() - self.start_time
            elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
            print(f"\r✅ {final_message} [{elapsed_str}]")
        else:
            print()  # Nova linha