# morphing/gradual_analyzer.py
import logging
from typing import Dict, Any, List, Optional
from collections import Counter
import re

logger = logging.getLogger(__name__)

class GradualMorphAnalyzer:
    """
    Capa 2: Análisis gradual basado en múltiples señales.
    Esta capa analiza keywords, patrones y contexto para decisiones más complejas.
    """
    
    def __init__(self, morphs_config: Dict[str, Any]):
        """
        Inicializo el analizador con la configuración de morphs.
        
        Args:
            morphs_config: Configuración de todos los morphs disponibles
        """
        self.morphs_config = morphs_config
        self.morphs_gradual_config = {}
        
        # Extraigo las configuraciones graduales de cada morph
        for morph_name, morph_config in morphs_config.items():
            gradual_triggers = morph_config.get('gradual_triggers', {})
            if gradual_triggers:
                self.morphs_gradual_config[morph_name] = {
                    'keywords': [kw.lower() for kw in gradual_triggers.get('keywords', [])],
                    'min_score': gradual_triggers.get('min_score', 2),
                    'intents': gradual_triggers.get('intents', []),
                    'emotions': gradual_triggers.get('emotions', [])
                }
                logger.info(f"📊 Morph '{morph_name}' configurado con análisis gradual")
    
    def analyze(self, user_input: str, conversation_history: List[Dict[str, str]], 
                current_morph: str = "general") -> Optional[Dict[str, Any]]:
        """
        Analizo el mensaje y conversación para determinar el mejor morph.
        
        Args:
            user_input: Mensaje actual del usuario
            conversation_history: Historial completo de conversación
            current_morph: Morph actualmente activo
            
        Returns:
            Dict con el morph recomendado, score y razón, o None si no hay cambio necesario
        """
        if not self.morphs_gradual_config:
            return None
        
        # Analizo múltiples señales
        signals = {
            'keywords': self._analyze_keywords(user_input),
            'context': self._analyze_conversation_context(conversation_history),
            'patterns': self._analyze_linguistic_patterns(user_input),
            'intent': self._analyze_basic_intent(user_input)
        }
        
        # Calculo scores para cada morph
        morph_scores = self._calculate_morph_scores(signals, current_morph)
        
        # Determino si hay un morph ganador claro
        best_morph = self._determine_best_morph(morph_scores, current_morph)
        
        if best_morph and best_morph != current_morph:
            return {
                'morph_name': best_morph,
                'confidence': morph_scores[best_morph]['total_score'] / 10.0,  # Normalizo a 0-1
                'reason': morph_scores[best_morph]['reason'],
                'scores': morph_scores
            }
        
        return None
    
    def _analyze_keywords(self, text: str) -> Dict[str, int]:
        """
        Analizo keywords en el texto y cuento matches por morph.
        """
        text_lower = text.lower()
        keyword_counts = {}
        
        for morph_name, config in self.morphs_gradual_config.items():
            count = 0
            matched_keywords = []
            
            for keyword in config['keywords']:
                if keyword in text_lower:
                    count += 1
                    matched_keywords.append(keyword)
            
            if count > 0:
                keyword_counts[morph_name] = {
                    'count': count,
                    'matched': matched_keywords
                }
        
        return keyword_counts
    
    def _analyze_conversation_context(self, conversation: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Analizo el contexto de los últimos mensajes de la conversación.
        """
        # Tomo los últimos 3 mensajes del usuario
        recent_user_messages = []
        for msg in reversed(conversation):
            if msg.get('role') == 'user' and len(recent_user_messages) < 3:
                recent_user_messages.append(msg.get('content', '').lower())
        
        # Analizo tendencias en los mensajes recientes
        context_signals = {
            'repeated_themes': self._find_repeated_themes(recent_user_messages),
            'conversation_length': len(conversation),
            'user_message_count': sum(1 for msg in conversation if msg.get('role') == 'user')
        }
        
        return context_signals
    
    def _analyze_linguistic_patterns(self, text: str) -> Dict[str, Any]:
        """
        Analizo patrones lingüísticos básicos del texto.
        """
        patterns = {
            'has_question': '?' in text,
            'has_exclamation': '!' in text,
            'word_count': len(text.split()),
            'is_short': len(text.split()) < 5,
            'is_long': len(text.split()) > 20,
            'has_please': any(word in text.lower() for word in ['por favor', 'please']),
            'has_urgency': any(word in text.lower() for word in ['urgente', 'rápido', 'ahora', 'ya'])
        }
        
        return patterns
    
    def _analyze_basic_intent(self, text: str) -> str:
        """
        Intento detectar el intent básico del mensaje.
        """
        text_lower = text.lower()
        
        # Patterns simples para detectar intents
        if any(word in text_lower for word in ['comprar', 'precio', 'costo', 'oferta', 'producto']):
            return 'purchase_inquiry'
        elif any(word in text_lower for word in ['problema', 'error', 'falla', 'no funciona', 'ayuda']):
            return 'support_request'
        elif any(word in text_lower for word in ['crear', 'diseñar', 'idea', 'imaginar']):
            return 'creative_request'
        elif '?' in text:
            return 'question'
        else:
            return 'statement'
    
    def _calculate_morph_scores(self, signals: Dict[str, Any], current_morph: str) -> Dict[str, Dict[str, Any]]:
        """
        Calculo scores para cada morph basándome en las señales analizadas.
        """
        morph_scores = {}
        
        for morph_name, config in self.morphs_gradual_config.items():
            score = 0
            reasons = []
            
            # Score por keywords
            keyword_data = signals['keywords'].get(morph_name, {})
            keyword_count = keyword_data.get('count', 0)
            if keyword_count > 0:
                score += keyword_count * 2  # Cada keyword vale 2 puntos
                reasons.append(f"Keywords encontradas: {', '.join(keyword_data.get('matched', []))}")
            
            # Score por intent
            detected_intent = signals['intent']
            if detected_intent in config.get('intents', []):
                score += 3  # Intent match vale 3 puntos
                reasons.append(f"Intent detectado: {detected_intent}")
            
            # Score por contexto
            context = signals['context']
            if morph_name in context.get('repeated_themes', []):
                score += 2  # Tema repetido vale 2 puntos
                reasons.append("Tema recurrente en conversación")
            
            # Score por patrones lingüísticos
            patterns = signals['patterns']
            if morph_name == 'support' and patterns.get('has_urgency'):
                score += 1  # Urgencia para support vale 1 punto
                reasons.append("Urgencia detectada")
            
            # Penalización por estar en el morph actual (para evitar cambios innecesarios)
            if morph_name == current_morph:
                score -= 2
            
            morph_scores[morph_name] = {
                'total_score': score,
                'min_score_required': config['min_score'],
                'meets_threshold': score >= config['min_score'],
                'reason': ' | '.join(reasons) if reasons else 'Sin señales claras'
            }
        
        return morph_scores
    
    def _determine_best_morph(self, morph_scores: Dict[str, Dict[str, Any]], current_morph: str) -> Optional[str]:
        """
        Determino el mejor morph basándome en los scores calculados.
        """
        # Filtro solo morphs que cumplen su threshold mínimo
        eligible_morphs = {
            name: data for name, data in morph_scores.items() 
            if data['meets_threshold']
        }
        
        if not eligible_morphs:
            return None
        
        # Encuentro el morph con mayor score
        best_morph = max(eligible_morphs.items(), key=lambda x: x[1]['total_score'])
        
        # Solo cambio si el score es significativamente mejor que mantener el actual
        if best_morph[0] != current_morph and best_morph[1]['total_score'] > 0:
            logger.info(f"📈 Análisis gradual sugiere: {best_morph[0]} (score: {best_morph[1]['total_score']})")
            return best_morph[0]
        
        return None
    
    def _find_repeated_themes(self, messages: List[str]) -> List[str]:
        """
        Encuentro temas que se repiten en los mensajes recientes.
        """
        if len(messages) < 2:
            return []
        
        # Extraigo palabras significativas de todos los mensajes
        all_words = []
        for msg in messages:
            words = re.findall(r'\b\w{4,}\b', msg.lower())  # Palabras de 4+ letras
            all_words.extend(words)
        
        # Encuentro palabras que aparecen múltiples veces
        word_counts = Counter(all_words)
        repeated_words = [word for word, count in word_counts.items() if count >= 2]
        
        # Mapeo palabras repetidas a morphs
        themes = []
        for morph_name, config in self.morphs_gradual_config.items():
            morph_keywords = config['keywords']
            if any(keyword in repeated_words for keyword in morph_keywords):
                themes.append(morph_name)
        
        return themes