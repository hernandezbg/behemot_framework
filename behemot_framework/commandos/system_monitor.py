# app/commandos/system_monitor.py
import logging
import time
import os
import json
import asyncio
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timedelta

# Importar funciones de verificación del sistema
from behemot_framework.commandos.system_status import (
    get_memory_usage,
    check_redis,
    check_model,
    check_config,
    BEHEMOT_START_TIME
)

logger = logging.getLogger(__name__)

# Clase para rastrear métricas del sistema en tiempo real
class SystemMetricsTracker:
    """Rastreador de métricas del sistema en tiempo real."""
    
    # Instancia singleton
    _instance = None
    
    # Datos de monitoreo
    _metrics_history = {}
    _monitoring_active = False
    _monitoring_task = None
    _start_time = None
    _end_time = None
    _interval_seconds = 10
    _max_history_points = 500  # Limitar para evitar consumo excesivo de memoria
    
    # Contadores
    api_calls = 0
    tool_calls = 0
    sessions_created = 0
    errors_count = 0
    messages_processed = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemMetricsTracker, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Inicializa el rastreador de métricas."""
        self._metrics_history = {
            "timestamp": [],
            "memory_usage": [],
            "active_sessions": [],
            "api_calls": [],
            "tool_calls": [],
            "errors": [],
            "messages_processed": []
        }
        self._monitoring_active = False
    
    def start_monitoring(self, duration_minutes: int = 5, interval_seconds: int = 10) -> bool:
        """
        Inicia el monitoreo del sistema.
        
        Args:
            duration_minutes: Duración del monitoreo en minutos
            interval_seconds: Intervalo entre mediciones en segundos
            
        Returns:
            bool: True si se inició correctamente, False si ya estaba activo
        """
        if self._monitoring_active:
            return False
        
        self._start_time = datetime.now()
        self._end_time = self._start_time + timedelta(minutes=duration_minutes)
        self._interval_seconds = max(1, min(interval_seconds, 60))  # Entre 1 y 60 segundos
        self._monitoring_active = True
        
        # Limpiar historial anterior
        for key in self._metrics_history:
            if isinstance(self._metrics_history[key], list):
                self._metrics_history[key] = []
        
        # Iniciar tarea de monitoreo asíncrona
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"Monitoreo iniciado por {duration_minutes} minutos con intervalo de {interval_seconds} segundos")
        return True
    
    def stop_monitoring(self) -> dict:
        """
        Detiene el monitoreo y devuelve un resumen de los resultados.
        
        Returns:
            dict: Resumen de las métricas recolectadas
        """
        if not self._monitoring_active:
            return {"error": "El monitoreo no está activo"}
        
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        self._end_time = datetime.now()
        duration = (self._end_time - self._start_time).total_seconds()
        
        # Calcular estadísticas
        result = self._calculate_statistics()
        result["duration_seconds"] = duration
        result["interval_seconds"] = self._interval_seconds
        result["start_time"] = self._start_time.strftime("%Y-%m-%d %H:%M:%S")
        result["end_time"] = self._end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"Monitoreo detenido después de {duration:.1f} segundos")
        return result
    
    def is_monitoring_active(self) -> bool:
        """Verifica si el monitoreo está activo."""
        return self._monitoring_active
    
    def get_current_metrics(self) -> dict:
        """
        Obtiene las métricas actuales del sistema.
        
        Returns:
            dict: Métricas actuales
        """
        metrics = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "memory_usage_mb": get_memory_usage(),
            "uptime_seconds": time.time() - BEHEMOT_START_TIME,
            "api_calls": self.api_calls,
            "tool_calls": self.tool_calls,
            "active_sessions": self._count_active_sessions(),
            "errors": self.errors_count,
            "messages_processed": self.messages_processed
        }
        return metrics
    
    def _count_active_sessions(self) -> int:
        """
        Cuenta el número de sesiones activas en Redis.
        
        Returns:
            int: Número de sesiones activas
        """
        try:
            from behemot_framework.context import redis_client
            keys = redis_client.keys("chat:*")
            return len(keys)
        except Exception as e:
            logger.error(f"Error al contar sesiones activas: {e}")
            return -1
    
    def _add_metric_point(self, metrics: dict) -> None:
        """
        Añade un punto de métrica al historial.
        
        Args:
            metrics: Diccionario con las métricas medidas
        """
        # Añadir cada métrica a su lista correspondiente
        self._metrics_history["timestamp"].append(metrics["timestamp"])
        self._metrics_history["memory_usage"].append(metrics["memory_usage_mb"])
        self._metrics_history["active_sessions"].append(metrics["active_sessions"])
        self._metrics_history["api_calls"].append(metrics["api_calls"])
        self._metrics_history["tool_calls"].append(metrics["tool_calls"])
        self._metrics_history["errors"].append(metrics["errors"])
        self._metrics_history["messages_processed"].append(metrics["messages_processed"])
        
        # Limitar el tamaño del historial
        if len(self._metrics_history["timestamp"]) > self._max_history_points:
            for key in self._metrics_history:
                if isinstance(self._metrics_history[key], list):
                    self._metrics_history[key] = self._metrics_history[key][-self._max_history_points:]
    
    def _calculate_statistics(self) -> dict:
        """
        Calcula estadísticas basadas en el historial de métricas.
        
        Returns:
            dict: Estadísticas calculadas
        """
        stats = {}
        
        # Calcular estadísticas para métricas numéricas
        for key in ["memory_usage", "active_sessions", "api_calls", "tool_calls", "errors", "messages_processed"]:
            values = self._metrics_history[key]
            if not values:
                continue
                
            stats[key] = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "last": values[-1],
                "samples": len(values)
            }
        
        return stats
    
    async def _monitoring_loop(self) -> None:
        """
        Bucle de monitoreo ejecutado de forma asíncrona.
        """
        try:
            while self._monitoring_active and datetime.now() < self._end_time:
                # Tomar medidas
                metrics = self.get_current_metrics()
                
                # Añadir al historial
                self._add_metric_point(metrics)
                
                # Esperar hasta el próximo intervalo
                await asyncio.sleep(self._interval_seconds)
                
            # Marcar como inactivo al finalizar
            self._monitoring_active = False
            
        except asyncio.CancelledError:
            logger.info("Tarea de monitoreo cancelada")
            self._monitoring_active = False
        except Exception as e:
            logger.error(f"Error en bucle de monitoreo: {e}", exc_info=True)
            self._monitoring_active = False

# Funciones auxiliares para el comando monitor

def format_monitoring_results(results: dict) -> str:
    """
    Formatea los resultados del monitoreo en texto legible.
    
    Args:
        results: Resultados de monitoreo
        
    Returns:
        str: Texto formateado
    """
    if "error" in results:
        return f"Error: {results['error']}"
    
    output = "📊 RESULTADOS DEL MONITOREO DEL SISTEMA 📊\n\n"
    
    # Información general
    output += f"⏱️ Duración: {results['duration_seconds']:.1f} segundos\n"
    output += f"🕒 Inicio: {results['start_time']}\n"
    output += f"🕘 Fin: {results['end_time']}\n"
    output += f"⏱️ Intervalo de muestreo: {results['interval_seconds']} segundos\n\n"
    
    # Métricas principales
    output += "📈 MÉTRICAS PRINCIPALES\n\n"
    
    # Memoria
    if "memory_usage" in results:
        mem = results["memory_usage"]
        output += f"💾 Memoria (MB):\n"
        output += f"  - Mínima: {mem['min']:.2f} MB\n"
        output += f"  - Máxima: {mem['max']:.2f} MB\n"
        output += f"  - Promedio: {mem['avg']:.2f} MB\n"
        output += f"  - Última medición: {mem['last']:.2f} MB\n\n"
    
    # Sesiones activas
    if "active_sessions" in results:
        sessions = results["active_sessions"]
        output += f"👥 Sesiones activas:\n"
        output += f"  - Mínimo: {sessions['min']}\n"
        output += f"  - Máximo: {sessions['max']}\n"
        output += f"  - Promedio: {sessions['avg']:.1f}\n"
        output += f"  - Última medición: {sessions['last']}\n\n"
    
    # Llamadas
    if "api_calls" in results and "tool_calls" in results:
        api = results["api_calls"]
        tool = results["tool_calls"]
        output += f"🔄 Llamadas:\n"
        output += f"  - API: {api['last']} llamadas\n"
        output += f"  - Herramientas: {tool['last']} llamadas\n\n"
    
    # Errores
    if "errors" in results:
        errors = results["errors"]
        output += f"⚠️ Errores: {errors['last']}\n\n"
    
    # Mensajes procesados
    if "messages_processed" in results:
        msgs = results["messages_processed"]
        output += f"💬 Mensajes procesados: {msgs['last']}\n\n"
    
    # Recomendaciones
    output += "🧠 ANÁLISIS Y RECOMENDACIONES\n\n"
    
    # Analizar memoria
    if "memory_usage" in results:
        mem = results["memory_usage"]
        mem_growth = mem['max'] - mem['min']
        if mem_growth > 50:
            output += "⚠️ Se detectó un crecimiento significativo de memoria durante el monitoreo.\n"
            output += "   Recomendación: Verificar posibles fugas de memoria en el código.\n\n"
        elif mem['max'] > 500:
            output += "⚠️ Uso de memoria elevado.\n"
            output += "   Recomendación: Considerar optimizar el uso de memoria.\n\n"
    
    # Analizar sesiones
    if "active_sessions" in results:
        sessions = results["active_sessions"]
        if sessions['max'] > 20:
            output += "ℹ️ Gran cantidad de sesiones activas.\n"
            output += "   Recomendación: Considerar mecanismos de limpieza automática de sesiones inactivas.\n\n"
    
    # Analizar errores
    if "errors" in results:
        errors = results["errors"]
        if errors['max'] > 0:
            output += f"⚠️ Se detectaron {errors['max']} errores durante el monitoreo.\n"
            output += "   Recomendación: Revisar los logs para más detalles.\n\n"
    
    return output

async def get_monitoring_data(duration_minutes: int = 5, interval_seconds: int = 10) -> dict:
    """
    Obtiene datos de monitoreo durante el período especificado.
    
    Args:
        duration_minutes: Duración del monitoreo en minutos
        interval_seconds: Intervalo entre mediciones en segundos
        
    Returns:
        dict: Resultados del monitoreo
    """
    tracker = SystemMetricsTracker()
    
    # Verificar si ya está activo
    if tracker.is_monitoring_active():
        return {"error": "El monitoreo ya está activo. Espera a que termine o detenlo con &monitor stop=true"}
    
    # Iniciar monitoreo
    started = tracker.start_monitoring(duration_minutes, interval_seconds)
    if not started:
        return {"error": "No se pudo iniciar el monitoreo"}
    
    # Esperar a que termine
    await asyncio.sleep(duration_minutes * 60)
    
    # Obtener resultados
    return tracker.stop_monitoring()

async def get_quick_monitoring_snapshot() -> dict:
    """
    Obtiene una instantánea rápida del estado actual del sistema.
    
    Returns:
        dict: Instantánea de métricas
    """
    tracker = SystemMetricsTracker()
    return {
        "metrics": tracker.get_current_metrics(),
        "redis_status": await check_redis(),
        "config": check_config(),
        "model": check_model()
    }

def format_monitoring_snapshot(snapshot: dict) -> str:
    """
    Formatea una instantánea de monitoreo.
    
    Args:
        snapshot: Datos de la instantánea
        
    Returns:
        str: Texto formateado
    """
    metrics = snapshot["metrics"]
    
    output = "📊 INSTANTÁNEA DEL SISTEMA 📊\n"
    output += f"Tiempo: {metrics['timestamp']}\n\n"
    
    # Métricas principales
    output += f"💾 Memoria: {metrics['memory_usage_mb']:.2f} MB\n"
    output += f"⏱️ Tiempo activo: {metrics['uptime_seconds']:.1f} segundos\n"
    output += f"👥 Sesiones activas: {metrics['active_sessions']}\n"
    output += f"🔄 Llamadas API: {metrics['api_calls']}\n"
    output += f"🔧 Llamadas a herramientas: {metrics['tool_calls']}\n"
    output += f"⚠️ Errores: {metrics['errors']}\n"
    output += f"💬 Mensajes procesados: {metrics['messages_processed']}\n\n"
    
    # Estado de Redis
    redis = snapshot["redis_status"]
    output += f"🗄️ Redis: {redis['status']}\n"
    if redis["connected"]:
        output += f"  - Tiempo de respuesta: {redis['response_time_ms']} ms\n"
        output += f"  - Lectura/Escritura: {redis['read_write']}\n\n"
    
    # Configuración
    config = snapshot["config"]
    output += f"⚙️ Configuración: {config['status']}\n"
    output += f"  - Asistente: {config['assistant_name']}\n"
    output += f"  - Modelo: {config['model']}\n\n"
    
    return output

def stop_monitoring() -> dict:
    """
    Detiene el monitoreo activo.
    
    Returns:
        dict: Resultados del monitoreo
    """
    tracker = SystemMetricsTracker()
    
    if not tracker.is_monitoring_active():
        return {"error": "No hay monitoreo activo para detener"}
    
    return tracker.stop_monitoring()
