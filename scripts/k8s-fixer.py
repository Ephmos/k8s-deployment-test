#!/usr/bin/env python3
"""
Agente corrector de YAML de Kubernetes usando OpenAI.
Requiere: pip install openai ruamel.yaml
Configurar variable de entorno OPENAI_API_KEY.
"""

import os
import sys
from pathlib import Path
from ruamel.yaml import YAML
from openai import OpenAI

# Configuración de YAML para preservar formato y comentarios
yaml_loader = YAML()
yaml_loader.preserve_quotes = True
yaml_loader.indent(mapping=2, sequence=4, offset=2)

# Cliente OpenAI (se puede ajustar para usar Azure o endpoints compatibles)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Eres un experto en Kubernetes y YAML. Tu tarea es recibir el contenido de un archivo YAML que contiene uno o más recursos de Kubernetes y devolver EXACTAMENTE el mismo contenido pero con las siguientes correcciones y mejoras:

1. Corregir errores de sintaxis YAML (indentación incorrecta, caracteres inválidos).
2. Actualizar apiVersion obsoletas (ej. extensions/v1beta1 -> apps/v1 para Deployments).
3. Asegurar que cada recurso tenga 'apiVersion', 'kind' y 'metadata.name'. Si falta 'name', invéntalo basado en 'kind' + sufijo corto aleatorio.
4. Agregar 'namespace: default' a recursos con namespace si no existe y no son cluster-scoped.
5. Para Deployments/StatefulSets: sincronizar spec.selector.matchLabels con spec.template.metadata.labels.
6. Agregar etiquetas recomendadas: app.kubernetes.io/name, app.kubernetes.io/instance (usando el nombre del recurso).
7. Corregir referencias a imágenes (ej. cambiar 'latest' por una versión específica sugerida, o añadir 'imagePullPolicy: IfNotPresent').
8. Asegurar que los Services tengan 'ports.name' si hay más de un puerto.

IMPORTANTE:
- Devuelve SOLO el YAML corregido, sin explicaciones, sin markdown, sin texto adicional.
- Preserva los comentarios existentes en la medida de lo posible.
- Si el YAML contiene múltiples documentos separados por '---', mantén esa estructura.
- No cambies nombres de recursos intencionalmente, excepto cuando sea necesario generar uno.
- Responde únicamente con el YAML válido."""

def fix_yaml_with_ai(content: str) -> str:
    """Envía el contenido a OpenAI y devuelve la versión corregida."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # o "gpt-3.5-turbo" para menor coste
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content}
            ],
            temperature=0.1,  # Baja temperatura para resultados deterministas
        )
        corrected = response.choices[0].message.content
        # Limpiar posibles delimitadores de código
        if corrected.startswith("```yaml"):
            corrected = corrected[7:]
        if corrected.startswith("```"):
            corrected = corrected[3:]
        if corrected.endswith("```"):
            corrected = corrected[:-3]
        return corrected.strip()
    except Exception as e:
        print(f"  ❌ Error al llamar a OpenAI: {e}")
        return content  # En caso de error, no modificar

def process_file(filepath: Path) -> bool:
    """Lee el archivo, lo envía a la IA y sobrescribe si hay cambios."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ No se pudo leer {filepath}: {e}")
        return False

    print(f"🤖 Analizando {filepath}...")
    corrected_content = fix_yaml_with_ai(original_content)

    if corrected_content == original_content.strip():
        return False

    # Validar que el resultado sea YAML parseable (opcional)
    try:
        list(yaml_loader.load_all(corrected_content))
    except Exception as e:
        print(f"⚠️ La IA generó YAML inválido para {filepath}: {e}")
        print("   Se conserva el archivo original.")
        return False

    # Escribir cambios
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(corrected_content)
    print(f"✅ {filepath} corregido por IA.")
    return True

def main():
    if len(sys.argv) < 2:
        print("Uso: python ai_k8s_fixer.py <directorio|archivo>")
        sys.exit(1)

    target = Path(sys.argv[1])
    yaml_files = []
    if target.is_dir():
        yaml_files = list(target.rglob("*.yaml")) + list(target.rglob("*.yml"))
    else:
        yaml_files = [target]

    fixed_count = 0
    for yf in yaml_files:
        if process_file(yf):
            fixed_count += 1

    print(f"\n📊 Procesados {len(yaml_files)} archivos. Corregidos por IA: {fixed_count}")

if __name__ == "__main__":
    main()
