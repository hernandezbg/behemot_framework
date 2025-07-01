# Conversor de Markdown a formato Google Chat
import re
import logging

logger = logging.getLogger(__name__)

def markdown_to_google_chat(text: str) -> str:
    """
    Convierte texto en formato Markdown a formato Google Chat.
    
    Google Chat soporta:
    - *negrita*
    - _cursiva_
    - ~tachado~
    - `código inline`
    - ```código en bloque```
    """
    
    logger.debug(f"🔄 Iniciando conversión de Markdown a Google Chat")
    
    # Detectar si hay markdown en el texto
    has_markdown = any([
        '**' in text,
        '##' in text,
        '- ' in text,
        '```' in text,
        '[' in text and '](' in text
    ])
    
    if has_markdown:
        logger.info(f"📋 Markdown detectado en el texto")
    
    # Primero, procesar los títulos que están en líneas independientes con **Título:**
    # para darles un formato especial antes de la conversión general
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        # Detectar líneas que son solo un título con formato **Texto:**
        if re.match(r'^\*\*[^*]+:\*\*\s*$', line.strip()):
            # Extraer el título y formatearlo de manera especial
            title = re.sub(r'\*\*([^*]+):\*\*', r'\1', line.strip())
            processed_lines.append(f"\n▬▬▬ *{title}* ▬▬▬")
        else:
            processed_lines.append(line)
    
    text = '\n'.join(processed_lines)
    
    # Ahora convertir ** a * para negrita en el resto del texto
    text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
    
    # Convertir __ a _ para cursiva (pero no interferir con _cursiva_ existente)
    text = re.sub(r'(?<!_)__([^_]+?)__(?!_)', r'_\1_', text)
    
    # Convertir ~~tachado~~ a ~tachado~
    text = re.sub(r'~~(.*?)~~', r'~\1~', text)
    
    # Convertir headers a negrita
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    
    # Convertir listas con - a • 
    text = re.sub(r'^-\s+', '• ', text, flags=re.MULTILINE)
    
    # Convertir listas numeradas a formato simple
    text = re.sub(r'^\d+\.\s+', '• ', text, flags=re.MULTILINE)
    
    # Los enlaces en Google Chat se detectan automáticamente, pero podemos limpiar formato [texto](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    
    # Convertir tablas simples a texto formateado
    # Buscar líneas que parecen encabezados de tabla
    lines = text.split('\n')
    new_lines = []
    in_table = False
    
    for i, line in enumerate(lines):
        # Detectar separador de tabla
        if re.match(r'^[\|\s\-:]+$', line) and i > 0:
            if '|' in lines[i-1]:
                in_table = True
                # Convertir encabezado a negrita
                header = lines[i-1]
                header_parts = [part.strip() for part in header.split('|') if part.strip()]
                new_header = ' | '.join([f'*{part}*' for part in header_parts])
                new_lines[-1] = new_header
                continue
        elif in_table and not line.strip():
            in_table = False
        elif in_table and '|' in line:
            # Procesar fila de tabla
            parts = [part.strip() for part in line.split('|') if part.strip()]
            new_lines.append(' | '.join(parts))
            continue
            
        new_lines.append(line)
    
    return '\n'.join(new_lines)