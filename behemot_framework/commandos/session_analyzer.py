# app/commandos/session_analyzer.py
import logging
import json
import time
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

class SessionAnalyzer:
    """Analizador de sesiones para el framework Behemot."""
    
    @staticmethod
    async def analyze_session(session_id: str, detailed: bool = False) -> Dict[str, Any]:
        """
        Analiza una sesión específica para obtener estadísticas e insights.
        
        Args:
            session_id: ID de la sesión a analizar
            detailed: Si es True, incluye análisis más detallados
            
        Returns:
            Dict: Resultados del análisis con estadísticas e insights
        """
        try:
            # Obtener datos de la sesión desde Redis
            from behemot_framework.context import redis_client
            
            key = f"chat:{session_id}"
            if not redis_client.exists(key):
                return {"error": f"La sesión {session_id} no existe"}
                
            # Cargar la conversación
            session_data = redis_client.get(key)
            if not session_data:
                return {"error": f"No se pudieron leer los datos de la sesión {session_id}"}
                
            conversation = json.loads(session_data)
            
            # Iniciar análisis
            return SessionAnalyzer._process_conversation(conversation, detailed)
            
        except Exception as e:
            logger.error(f"Error al analizar sesión {session_id}: {e}", exc_info=True)
            return {"error": f"Error al analizar sesión: {str(e)}"}
    
    @staticmethod
    def _process_conversation(conversation: List[Dict[str, Any]], detailed: bool = False) -> Dict[str, Any]:
        """
        Procesa la conversación para extraer estadísticas e insights.
        
        Args:
            conversation: Lista de mensajes de la conversación
            detailed: Si es True, incluye análisis más detallados
            
        Returns:
            Dict: Resultados del análisis
        """
        # Inicializar resultados
        results = {
            "general": {},
            "user": {},
            "assistant": {},
            "tools": {},
            "topics": {},
            "time": {},
            "insights": []
        }
        
        # Verificar que la conversación tenga mensajes
        if not conversation:
            results["error"] = "La conversación está vacía"
            return results
            
        # Extraer mensajes por rol
        system_msg = None
        user_msgs = []
        assistant_msgs = []
        function_msgs = []
        
        for msg in conversation:
            role = msg.get("role", "")
            
            if role == "system":
                system_msg = msg
            elif role == "user":
                user_msgs.append(msg)
            elif role == "assistant":
                assistant_msgs.append(msg)
            elif role == "function":
                function_msgs.append(msg)
        
        # Estadísticas generales
        results["general"]["total_messages"] = len(conversation)
        results["general"]["user_messages"] = len(user_msgs)
        results["general"]["assistant_messages"] = len(assistant_msgs)
        results["general"]["function_calls"] = len(function_msgs)
        results["general"]["turns"] = min(len(user_msgs), len(assistant_msgs))
        
        # Extraer timestamps (si están disponibles)
        timestamps = SessionAnalyzer._extract_timestamps(conversation)
        if timestamps:
            results["time"] = SessionAnalyzer._analyze_timestamps(timestamps)
        
        # Análisis de mensajes del usuario
        results["user"] = SessionAnalyzer._analyze_user_messages(user_msgs)
        
        # Análisis de mensajes del asistente
        results["assistant"] = SessionAnalyzer._analyze_assistant_messages(assistant_msgs)
        
        # Análisis de herramientas utilizadas
        results["tools"] = SessionAnalyzer._analyze_tool_usage(function_msgs)
        
        # Análisis de tópicos (solo si se solicita detallado)
        if detailed:
            results["topics"] = SessionAnalyzer._analyze_topics(user_msgs, assistant_msgs)
        
        # Generar insights
        results["insights"] = SessionAnalyzer._generate_insights(results)
        
        return results
    
    @staticmethod
    def _extract_timestamps(conversation: List[Dict[str, Any]]) -> List[Tuple[str, datetime]]:
        """
        Extrae timestamps de los mensajes si están disponibles.
        
        Args:
            conversation: Lista de mensajes de la conversación
            
        Returns:
            List[Tuple]: Lista de tuplas (role, timestamp)
        """
        timestamps = []
        
        for msg in conversation:
            # Intentar obtener timestamp del mensaje (si existe)
            if "timestamp" in msg:
                try:
                    ts = datetime.fromisoformat(msg["timestamp"])
                    timestamps.append((msg.get("role", "unknown"), ts))
                except (ValueError, TypeError):
                    pass
        
        return timestamps
    
    @staticmethod
    def _analyze_timestamps(timestamps: List[Tuple[str, datetime]]) -> Dict[str, Any]:
        """
        Analiza los timestamps para obtener estadísticas de tiempo.
        
        Args:
            timestamps: Lista de tuplas (role, timestamp)
            
        Returns:
            Dict: Estadísticas de tiempo
        """
        if not timestamps or len(timestamps) < 2:
            return {"available": False}
            
        results = {"available": True}
        
        # Ordenar por timestamp
        sorted_ts = sorted(timestamps, key=lambda x: x[1])
        
        # Calcular duración total
        start_time = sorted_ts[0][1]
        end_time = sorted_ts[-1][1]
        duration = (end_time - start_time).total_seconds()
        
        results["start_time"] = start_time.isoformat()
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = duration
        
        # Extraer timestamps por rol
        user_ts = [ts for role, ts in sorted_ts if role == "user"]
        assistant_ts = [ts for role, ts in sorted_ts if role == "assistant"]
        
        # Calcular tiempos de respuesta (si hay suficientes mensajes)
        response_times = []
        for i in range(len(user_ts)):
            if i < len(assistant_ts):
                # Encontrar el primer mensaje del asistente después del mensaje del usuario
                user_time = user_ts[i]
                assistant_time = None
                
                for ts in assistant_ts:
                    if ts > user_time:
                        assistant_time = ts
                        break
                
                if assistant_time:
                    resp_time = (assistant_time - user_time).total_seconds()
                    response_times.append(resp_time)
        
        if response_times:
            results["avg_response_time"] = sum(response_times) / len(response_times)
            results["min_response_time"] = min(response_times)
            results["max_response_time"] = max(response_times)
        
        return results
    
    @staticmethod
    def _analyze_user_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza los mensajes del usuario.
        
        Args:
            messages: Lista de mensajes del usuario
            
        Returns:
            Dict: Estadísticas de mensajes del usuario
        """
        if not messages:
            return {"count": 0}
            
        results = {"count": len(messages)}
        
        # Obtener longitudes de mensajes
        lengths = [len(msg.get("content", "")) for msg in messages]
        
        # Calcular estadísticas
        results["avg_length"] = sum(lengths) / len(lengths) if lengths else 0
        results["min_length"] = min(lengths) if lengths else 0
        results["max_length"] = max(lengths) if lengths else 0
        
        # Detectar preguntas
        question_count = 0
        for msg in messages:
            content = msg.get("content", "")
            if "?" in content:
                question_count += 1
        
        results["questions"] = question_count
        results["question_ratio"] = question_count / len(messages) if messages else 0
        
        # Detectar comandos
        command_count = 0
        for msg in messages:
            content = msg.get("content", "")
            if content.strip().startswith("&"):
                command_count += 1
        
        results["commands"] = command_count
        
        return results
    
    @staticmethod
    def _analyze_assistant_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza los mensajes del asistente.
        
        Args:
            messages: Lista de mensajes del asistente
            
        Returns:
            Dict: Estadísticas de mensajes del asistente
        """
        if not messages:
            return {"count": 0}
            
        results = {"count": len(messages)}
        
        # Obtener longitudes de mensajes
        lengths = [len(msg.get("content", "")) for msg in messages]
        
        # Calcular estadísticas
        results["avg_length"] = sum(lengths) / len(lengths) if lengths else 0
        results["min_length"] = min(lengths) if lengths else 0
        results["max_length"] = max(lengths) if lengths else 0
        
        # Analizar uso de funciones
        function_calls = 0
        for msg in messages:
            if msg.get("function_call") or "tool_calls" in msg:
                function_calls += 1
        
        results["function_calls"] = function_calls
        results["function_call_ratio"] = function_calls / len(messages) if messages else 0
        
        return results
    
    @staticmethod
    def _analyze_tool_usage(function_msgs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza el uso de herramientas en la conversación.
        
        Args:
            function_msgs: Lista de mensajes de función
            
        Returns:
            Dict: Estadísticas de uso de herramientas
        """
        if not function_msgs:
            return {"count": 0, "used": False}
            
        results = {"count": len(function_msgs), "used": True}
        
        # Contar uso por herramienta
        tool_counter = Counter()
        for msg in function_msgs:
            tool_name = msg.get("name", "unknown")
            tool_counter[tool_name] += 1
        
        # Herramientas más utilizadas
        results["most_used"] = tool_counter.most_common(5)
        results["unique_tools"] = len(tool_counter)
        
        return results
    
    @staticmethod
    def _analyze_topics(user_msgs: List[Dict[str, Any]], assistant_msgs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza los tópicos principales de la conversación.
        
        Args:
            user_msgs: Lista de mensajes del usuario
            assistant_msgs: Lista de mensajes del asistente
            
        Returns:
            Dict: Estadísticas de tópicos
        """
        try:
            # Combinar todos los mensajes para análisis de texto
            all_text = ""
            
            for msg in user_msgs:
                all_text += msg.get("content", "") + " "
                
            for msg in assistant_msgs:
                all_text += msg.get("content", "") + " "
            
            if not all_text.strip():
                return {"available": False}
                
            # Obtener palabras más frecuentes (excluyendo stopwords)
            word_counter = SessionAnalyzer._count_meaningful_words(all_text)
            top_words = word_counter.most_common(20)
            
            # Intentar resumir tópicos generales
            topics = SessionAnalyzer._extract_topics_from_words(top_words)
            
            return {
                "available": True,
                "top_words": top_words,
                "detected_topics": topics
            }
            
        except Exception as e:
            logger.error(f"Error al analizar tópicos: {e}")
            return {"available": False, "error": str(e)}
    
    @staticmethod
    def _count_meaningful_words(text: str) -> Counter:
        """
        Cuenta palabras significativas en un texto, excluyendo stopwords.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Counter: Contador de palabras significativas
        """
        # Lista básica de stopwords en español e inglés
        stopwords = {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "a", "ante", "bajo",
            "con", "de", "desde", "en", "entre", "hacia", "hasta", "para", "por", "según", "sin",
            "sobre", "tras", "the", "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were",
            "will", "with", "que", "es", "no", "sí", "si", "yes", "no", "pero", "más", "menos",
            "este", "esta", "estos", "estas", "aquel", "aquella", "su", "sus", "mi", "mis",
            "tu", "tus", "se", "lo", "me", "te", "nos", "les"
        }
        
        # Normalizar texto
        text = text.lower()
        
        # Separar en palabras
        import re
        words = re.findall(r'\b\w+\b', text)
        
        # Filtrar stopwords y palabras demasiado cortas
        meaningful_words = [word for word in words if word not in stopwords and len(word) > 2]
        
        return Counter(meaningful_words)
    
    @staticmethod
    def _extract_topics_from_words(top_words: List[Tuple[str, int]]) -> List[str]:
        """
        Intenta extraer tópicos generales a partir de las palabras más frecuentes.
        
        Args:
            top_words: Lista de tuplas (palabra, frecuencia)
            
        Returns:
            List: Lista de posibles tópicos
        """
        # Mapa de palabras clave a tópicos
        topic_keywords = {
            "programación": ["código", "programa", "función", "clase", "variable", "objeto", "python", "javascript"],
            "finanzas": ["dinero", "banco", "cuenta", "inversión", "crédito", "préstamo", "financiero"],
            "educación": ["curso", "aprender", "estudiar", "universidad", "escuela", "educación", "enseñar"],
            "tecnología": ["tecnología", "tech", "sistema", "aplicación", "app", "software", "hardware"],
            "salud": ["salud", "médico", "doctor", "enfermedad", "síntoma", "tratamiento", "medicina"],
            "viajes": ["viaje", "hotel", "vuelo", "país", "ciudad", "turismo", "visitar"],
            "datos": ["datos", "análisis", "estadística", "gráfico", "base", "información"],
            "inteligencia artificial": ["ia", "ai", "machine", "aprendizaje", "modelo", "ml", "neural", "llm", "gpt"],
            "legal": ["legal", "ley", "contrato", "derecho", "jurídico", "abogado"]
        }
        
        # Inicializar contadores para cada tópico
        topic_counts = defaultdict(int)
        
        # Contar coincidencias de palabras con los tópicos
        for word, count in top_words:
            for topic, keywords in topic_keywords.items():
                if word in keywords:
                    topic_counts[topic] += count
                    
        # Seleccionar tópicos con más de 2 coincidencias
        detected_topics = [topic for topic, count in topic_counts.items() if count > 2]
        
        return detected_topics
    
    @staticmethod
    def _generate_insights(results: Dict[str, Any]) -> List[str]:
        """
        Genera insights basados en los resultados del análisis.
        
        Args:
            results: Resultados del análisis
            
        Returns:
            List: Lista de insights
        """
        insights = []
        
        # Insight sobre longitud de la conversación
        msg_count = results["general"]["total_messages"]
        if msg_count < 5:
            insights.append("La conversación es muy corta, posiblemente una interacción inicial o de prueba.")
        elif msg_count > 20:
            insights.append("Conversación extensa que muestra un uso prolongado del asistente.")
        
        # Insight sobre tiempo de respuesta
        if "time" in results and results["time"].get("available"):
            avg_resp_time = results["time"].get("avg_response_time", 0)
            if avg_resp_time > 5:
                insights.append(f"El tiempo promedio de respuesta ({avg_resp_time:.1f}s) es alto, lo que podría indicar procesamiento complejo o uso de herramientas externas.")
            elif avg_resp_time < 1:
                insights.append(f"El tiempo promedio de respuesta ({avg_resp_time:.1f}s) es muy rápido, lo que sugiere respuestas simples o una carga del sistema baja.")
        
        # Insight sobre uso de herramientas
        if results["tools"].get("used", False):
            tool_count = results["tools"]["count"]
            unique_tools = results["tools"].get("unique_tools", 0)
            
            if tool_count > 5:
                insights.append(f"Alto uso de herramientas ({tool_count} llamadas), lo que indica un asistente que complementa respuestas con información externa.")
                
            if unique_tools > 3:
                insights.append(f"La conversación utilizó {unique_tools} herramientas diferentes, mostrando un caso de uso variado.")
                
            # Mencionar la herramienta más usada
            if results["tools"].get("most_used"):
                top_tool, top_count = results["tools"]["most_used"][0]
                insights.append(f"La herramienta más utilizada fue '{top_tool}' con {top_count} usos.")
        else:
            insights.append("No se utilizaron herramientas en esta conversación, indicando respuestas basadas únicamente en el conocimiento del modelo.")
        
        # Insight sobre relación preguntas/afirmaciones
        question_ratio = results["user"].get("question_ratio", 0)
        if question_ratio > 0.8:
            insights.append("El usuario principalmente hace preguntas, usando el asistente como fuente de información.")
        elif question_ratio < 0.3:
            insights.append("El usuario raramente hace preguntas directas, sugiriendo un uso más conversacional o instructivo.")
        
        # Insight sobre longitud de mensajes
        user_avg = results["user"].get("avg_length", 0)
        assistant_avg = results["assistant"].get("avg_length", 0)
        
        if user_avg > 200:
            insights.append(f"El usuario tiende a escribir mensajes largos (promedio: {user_avg:.0f} caracteres), proporcionando contexto detallado.")
        elif user_avg < 50:
            insights.append(f"El usuario tiende a escribir mensajes cortos (promedio: {user_avg:.0f} caracteres), siendo conciso en sus interacciones.")
            
        if assistant_avg > 500:
            insights.append(f"El asistente proporciona respuestas extensas (promedio: {assistant_avg:.0f} caracteres), ofreciendo explicaciones detalladas.")
        
        # Insight sobre tópicos
        if "topics" in results and results["topics"].get("available") and results["topics"].get("detected_topics"):
            topics = results["topics"]["detected_topics"]
            if topics:
                topics_str = ", ".join(topics)
                insights.append(f"Los principales temas detectados en la conversación son: {topics_str}.")
        
        # Insight sobre uso de comandos
        commands = results["user"].get("commands", 0)
        if commands > 0:
            insights.append(f"El usuario ha ejecutado {commands} comandos, indicando un uso avanzado del sistema.")
        
        return insights


def format_session_analysis(analysis: Dict[str, Any], detailed: bool = False) -> str:
    """
    Formatea los resultados del análisis de sesión en texto legible.
    
    Args:
        analysis: Resultados del análisis
        detailed: Si es True, incluye más detalles en el formato
        
    Returns:
        str: Texto formateado
    """
    if "error" in analysis:
        return f"Error al analizar la sesión: {analysis['error']}"
    
    output = "📊 ANÁLISIS DE SESIÓN 📊\n\n"
    
    # Estadísticas generales
    output += "📈 ESTADÍSTICAS GENERALES\n"
    general = analysis["general"]
    output += f"Total de mensajes: {general['total_messages']}\n"
    output += f"Mensajes del usuario: {general['user_messages']}\n"
    output += f"Mensajes del asistente: {general['assistant_messages']}\n"
    output += f"Llamadas a funciones: {general['function_calls']}\n"
    output += f"Turnos de conversación: {general['turns']}\n\n"
    
    # Información de tiempo (si está disponible)
    if "time" in analysis and analysis["time"].get("available"):
        time_data = analysis["time"]
        
        output += "⏱️ INFORMACIÓN TEMPORAL\n"
        output += f"Inicio: {time_data['start_time']}\n"
        output += f"Fin: {time_data['end_time']}\n"
        
        # Convertir segundos a formato más legible
        duration_sec = time_data['duration_seconds']
        hours, remainder = divmod(duration_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        duration_str = ""
        if hours > 0:
            duration_str += f"{int(hours)}h "
        if minutes > 0 or hours > 0:
            duration_str += f"{int(minutes)}m "
        duration_str += f"{int(seconds)}s"
        
        output += f"Duración total: {duration_str}\n"
        
        if "avg_response_time" in time_data:
            output += f"Tiempo de respuesta promedio: {time_data['avg_response_time']:.2f}s\n"
            output += f"Tiempo de respuesta mínimo: {time_data['min_response_time']:.2f}s\n"
            output += f"Tiempo de respuesta máximo: {time_data['max_response_time']:.2f}s\n"
        
        output += "\n"
    
    # Análisis de mensajes del usuario
    user = analysis["user"]
    output += "👤 ANÁLISIS DEL USUARIO\n"
    output += f"Longitud promedio de mensajes: {user.get('avg_length', 0):.0f} caracteres\n"
    output += f"Longitud mínima: {user.get('min_length', 0)} caracteres\n"
    output += f"Longitud máxima: {user.get('max_length', 0)} caracteres\n"
    output += f"Preguntas realizadas: {user.get('questions', 0)} ({user.get('question_ratio', 0)*100:.0f}% de mensajes)\n"
    output += f"Comandos ejecutados: {user.get('commands', 0)}\n\n"
    
    # Análisis de mensajes del asistente
    assistant = analysis["assistant"]
    output += "🤖 ANÁLISIS DEL ASISTENTE\n"
    output += f"Longitud promedio de respuestas: {assistant.get('avg_length', 0):.0f} caracteres\n"
    output += f"Longitud mínima: {assistant.get('min_length', 0)} caracteres\n"
    output += f"Longitud máxima: {assistant.get('max_length', 0)} caracteres\n"
    
    # Uso de herramientas
    tools = analysis["tools"]
    output += "\n🔧 USO DE HERRAMIENTAS\n"
    
    if tools.get("used", False):
        output += f"Llamadas a herramientas: {tools['count']}\n"
        output += f"Herramientas únicas utilizadas: {tools.get('unique_tools', 0)}\n"
        
        if tools.get("most_used"):
            output += "Top herramientas:\n"
            for tool, count in tools["most_used"]:
                output += f"- {tool}: {count} veces\n"
    else:
        output += "No se utilizaron herramientas en esta conversación.\n"
    
    # Tópicos (si están disponibles y se solicitó detallado)
    if detailed and "topics" in analysis and analysis["topics"].get("available"):
        topics = analysis["topics"]
        output += "\n📑 ANÁLISIS DE TÓPICOS\n"
        
        if topics.get("detected_topics"):
            output += "Tópicos detectados:\n"
            for topic in topics["detected_topics"]:
                output += f"- {topic}\n"
        else:
            output += "No se pudieron detectar tópicos específicos.\n"
            
        if detailed and topics.get("top_words"):
            output += "\nPalabras más frecuentes:\n"
            for word, count in topics["top_words"][:10]:  # Mostrar solo las 10 más frecuentes
                output += f"- {word}: {count} veces\n"
    
    # Insights
    if analysis.get("insights"):
        output += "\n💡 INSIGHTS\n"
        for i, insight in enumerate(analysis["insights"], 1):
            output += f"{i}. {insight}\n"
    
    return output

async def analyze_session(session_id: str, detailed: bool = False) -> Dict[str, Any]:
    """
    Función principal para analizar una sesión.
    
    Args:
        session_id: ID de la sesión a analizar
        detailed: Si es True, incluye análisis más detallados
        
    Returns:
        Dict: Resultados del análisis
    """
    return await SessionAnalyzer.analyze_session(session_id, detailed)

async def analyze_current_session(current_id: str, detailed: bool = False) -> Dict[str, Any]:
    """
    Analiza la sesión actual.
    
    Args:
        current_id: ID de la sesión actual
        detailed: Si es True, incluye análisis más detallados
        
    Returns:
        Dict: Resultados del análisis
    """
    return await SessionAnalyzer.analyze_session(current_id, detailed)
