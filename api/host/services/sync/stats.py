#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerenciamento de estatísticas de sincronização
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class SyncStatsManager:
    """Gerenciador thread-safe de estatísticas de sincronização"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.reset()
    
    def reset(self):
        """Reseta todas as estatísticas"""
        with self._lock:
            self.total_files = 0
            self.uploaded_files = 0
            self.skipped_files = 0
            self.failed_files = 0
            self.total_size = 0
            self.uploaded_size = 0
            self.start_time: Optional[datetime] = None
            self.end_time: Optional[datetime] = None
            
            # Estatísticas detalhadas
            self.upload_speeds = []  # Lista de velocidades por arquivo
            self.file_sizes = []     # Lista de tamanhos de arquivo
            self.error_counts = {}   # Contagem por tipo de erro
            
            self.logger.debug("Estatísticas resetadas")
    
    def start_timer(self):
        """Inicia timer de sincronização"""
        with self._lock:
            self.start_time = datetime.now()
            self.logger.debug("Timer iniciado")
    
    def stop_timer(self):
        """Para timer de sincronização"""
        with self._lock:
            self.end_time = datetime.now()
            self.logger.debug("Timer parado")
    
    def set_total_files(self, count: int):
        """Define total de arquivos para processamento"""
        with self._lock:
            self.total_files = count
    
    def add_uploaded(self, size: int = 0, upload_time: float = 0):
        """Adiciona arquivo uploadado às estatísticas"""
        with self._lock:
            self.uploaded_files += 1
            self.uploaded_size += size
            
            if size > 0:
                self.file_sizes.append(size)
            
            if upload_time > 0 and size > 0:
                speed = size / upload_time  # bytes por segundo
                self.upload_speeds.append(speed)
    
    def add_skipped(self):
        """Adiciona arquivo pulado às estatísticas"""
        with self._lock:
            self.skipped_files += 1
    
    def add_failed(self, error_type: str = "unknown"):
        """Adiciona arquivo com falha às estatísticas"""
        with self._lock:
            self.failed_files += 1
            
            if error_type not in self.error_counts:
                self.error_counts[error_type] = 0
            self.error_counts[error_type] += 1
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas atuais"""
        with self._lock:
            processed = self.uploaded_files + self.skipped_files + self.failed_files
            
            # Calcula progresso
            progress_percent = 0.0
            if self.total_files > 0:
                progress_percent = (processed / self.total_files) * 100
            
            # Calcula tempo decorrido
            elapsed_seconds = 0
            if self.start_time:
                end_time = self.end_time or datetime.now()
                elapsed_seconds = (end_time - self.start_time).total_seconds()
            
            # Calcula velocidade média
            avg_speed = 0.0
            if self.upload_speeds:
                avg_speed = sum(self.upload_speeds) / len(self.upload_speeds)
            
            # Calcula ETA
            eta_seconds = 0
            if processed > 0 and elapsed_seconds > 0 and self.total_files > processed:
                rate = processed / elapsed_seconds
                remaining = self.total_files - processed
                eta_seconds = remaining / rate
            
            return {
                'total_files': self.total_files,
                'uploaded_files': self.uploaded_files,
                'skipped_files': self.skipped_files,
                'failed_files': self.failed_files,
                'processed_files': processed,
                'total_size': self.total_size,
                'uploaded_size': self.uploaded_size,
                'progress_percent': progress_percent,
                'elapsed_seconds': elapsed_seconds,
                'eta_seconds': eta_seconds,
                'avg_upload_speed': avg_speed,
                'is_complete': processed >= self.total_files,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None
            }
    
    def get_final_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas finais completas"""
        self.stop_timer()
        
        with self._lock:
            current_stats = self.get_current_stats()
            
            # Estatísticas adicionais
            additional_stats = {
                'success_rate': 0.0,
                'failure_rate': 0.0,
                'skip_rate': 0.0,
                'avg_file_size': 0,
                'min_file_size': 0,
                'max_file_size': 0,
                'total_upload_time': current_stats['elapsed_seconds'],
                'error_breakdown': dict(self.error_counts),
                'performance_metrics': self._calculate_performance_metrics()
            }
            
            # Calcula taxas
            total_processed = self.uploaded_files + self.skipped_files + self.failed_files
            if total_processed > 0:
                additional_stats['success_rate'] = (self.uploaded_files / total_processed) * 100
                additional_stats['failure_rate'] = (self.failed_files / total_processed) * 100
                additional_stats['skip_rate'] = (self.skipped_files / total_processed) * 100
            
            # Estatísticas de tamanho de arquivo
            if self.file_sizes:
                additional_stats['avg_file_size'] = sum(self.file_sizes) / len(self.file_sizes)
                additional_stats['min_file_size'] = min(self.file_sizes)
                additional_stats['max_file_size'] = max(self.file_sizes)
            
            return {**current_stats, **additional_stats}
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calcula métricas de performance"""
        metrics = {
            'avg_speed_mbps': 0.0,
            'peak_speed_mbps': 0.0,
            'min_speed_mbps': 0.0,
            'speed_consistency': 0.0,  # Desvio padrão normalizado
            'throughput_efficiency': 0.0
        }
        
        if not self.upload_speeds:
            return metrics
        
        # Converte para Mbps (megabits por segundo)
        speeds_mbps = [speed * 8 / (1024 * 1024) for speed in self.upload_speeds]
        
        metrics['avg_speed_mbps'] = sum(speeds_mbps) / len(speeds_mbps)
        metrics['peak_speed_mbps'] = max(speeds_mbps)
        metrics['min_speed_mbps'] = min(speeds_mbps)
        
        # Calcula consistência (menor desvio padrão = mais consistente)
        if len(speeds_mbps) > 1:
            avg = metrics['avg_speed_mbps']
            variance = sum((speed - avg) ** 2 for speed in speeds_mbps) / len(speeds_mbps)
            std_dev = variance ** 0.5
            metrics['speed_consistency'] = 100 - min(100, (std_dev / avg) * 100)
        
        # Eficiência de throughput (taxa real vs teórica)
        if self.start_time and self.end_time:
            total_time = (self.end_time - self.start_time).total_seconds()
            if total_time > 0:
                theoretical_throughput = self.uploaded_size / total_time
                actual_throughput = sum(self.upload_speeds) / len(self.upload_speeds) if self.upload_speeds else 0
                if theoretical_throughput > 0:
                    metrics['throughput_efficiency'] = min(100, (actual_throughput / theoretical_throughput) * 100)
        
        return metrics
    
    def get_summary_text(self) -> str:
        """Retorna resumo textual das estatísticas"""
        stats = self.get_current_stats()
        
        lines = [
            f"📊 Estatísticas de Sincronização",
            f"├─ Total: {stats['total_files']} arquivos",
            f"├─ ✅ Uploaded: {stats['uploaded_files']}",
            f"├─ ⏭️  Pulados: {stats['skipped_files']}",
            f"├─ ❌ Falhas: {stats['failed_files']}",
            f"├─ 📈 Progresso: {stats['progress_percent']:.1f}%",
            f"├─ ⏱️  Tempo: {self._format_duration(stats['elapsed_seconds'])}",
            f"├─ 💾 Tamanho: {self._format_size(stats['uploaded_size'])}"
        ]
        
        if stats['avg_upload_speed'] > 0:
            speed_text = self._format_speed(stats['avg_upload_speed'])
            lines.append(f"└─ 🚀 Velocidade: {speed_text}")
        else:
            lines.append("└─ 🚀 Velocidade: N/A")
        
        return "\n".join(lines)
    
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
    
    def _format_size(self, bytes_size: int) -> str:
        """Formata tamanho em texto legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
    
    def _format_speed(self, bytes_per_sec: float) -> str:
        """Formata velocidade em texto legível"""
        return f"{self._format_size(bytes_per_sec)}/s"