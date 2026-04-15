#!/usr/bin/env python3
"""
Agente de corrección automática para manifiestos YAML de Kubernetes.
Uso: python k8s-fixer.py <directorio_o_archivo>
"""

import os
import sys
import random
import string
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# Mapa de apiVersions obsoletas y sus reemplazos recomendados
OBSOLETE_API_MAP = {
    "extensions/v1beta1": {
        "Deployment": "apps/v1",
        "Ingress": "networking.k8s.io/v1",
        "DaemonSet": "apps/v1",
        "ReplicaSet": "apps/v1"
    },
    "apps/v1beta1": {"Deployment": "apps/v1", "StatefulSet": "apps/v1"},
    "apps/v1beta2": {"Deployment": "apps/v1", "StatefulSet": "apps/v1", "DaemonSet": "apps/v1"},
    "batch/v1beta1": {"CronJob": "batch/v1"},
}

def random_suffix(length=4):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def fix_kubernetes_manifest(data, filepath):
    """Aplica correcciones a un diccionario que representa un manifiesto K8s."""
    if not isinstance(data, dict):
        return False

    modified = False

    # 1. Verificar campos obligatorios
    if "apiVersion" not in data:
        print(f"  ⚠️  Falta apiVersion en {filepath}, se asume 'v1' (puede requerir ajuste manual)")
        data["apiVersion"] = "v1"
        modified = True

    if "kind" not in data:
        print(f"  ❌ Falta 'kind' en {filepath}, no se puede corregir automáticamente.")
        return modified

    kind = data.get("kind", "")

    # 2. Actualizar apiVersion obsoleta
    current_api = data.get("apiVersion")
    if current_api in OBSOLETE_API_MAP and kind in OBSOLETE_API_MAP[current_api]:
        new_api = OBSOLETE_API_MAP[current_api][kind]
        print(f"  🔄 Actualizando apiVersion: {current_api} -> {new_api} para {kind}")
        data["apiVersion"] = new_api
        modified = True

    # 3. Asegurar metadata
    if "metadata" not in data:
        data["metadata"] = {}
        modified = True

    metadata = data["metadata"]

    if "name" not in metadata:
        generated_name = f"{kind.lower()}-{random_suffix()}"
        print(f"  🏷️  Generando metadata.name: {generated_name}")
        metadata["name"] = generated_name
        modified = True

    if "namespace" not in metadata:
        # Opcional: agregar 'default' o dejarlo sin namespace (cluster-scoped)
        if kind not in ["Namespace", "ClusterRole", "ClusterRoleBinding", "StorageClass", "PersistentVolume"]:
            metadata["namespace"] = "default"
            modified = True

    # 4. Correcciones específicas por kind
    if kind in ["Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"]:
        # Asegurar que spec.selector.matchLabels coincida con spec.template.metadata.labels
        spec = data.get("spec", {})
        selector = spec.get("selector", {})
        template_metadata = spec.get("template", {}).get("metadata", {})

        if not selector.get("matchLabels") and template_metadata.get("labels"):
            # Si no hay matchLabels pero sí labels en el template, copiar
            selector["matchLabels"] = template_metadata["labels"].copy()
            spec["selector"] = selector
            data["spec"] = spec
            print(f"  🔗 Sincronizando selector.matchLabels con template.labels")
            modified = True

    if kind == "Service":
        # Corregir puertos sin nombre (requerido en algunos entornos)
        ports = data.get("spec", {}).get("ports", [])
        for idx, port in enumerate(ports):
            if "name" not in port:
                port["name"] = f"port-{idx}"
                modified = True
                print(f"  🌐 Agregando nombre a puerto {port.get('port')}: {port['name']}")

    return modified

def process_file(filepath):
    """Procesa un archivo YAML (puede contener múltiples documentos)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            docs = list(yaml.load_all(f))
    except Exception as e:
        print(f"❌ Error al leer {filepath}: {e}")
        return False

    modified_any = False
    for doc_idx, doc in enumerate(docs):
        if doc is None:
            continue
        if fix_kubernetes_manifest(doc, f"{filepath}#doc{doc_idx}"):
            modified_any = True

    if modified_any:
        # Escribir de vuelta preservando comentarios y estructura
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump_all(docs, f)
        print(f"✅ Archivo corregido: {filepath}")
    return modified_any

def main():
    if len(sys.argv) < 2:
        print("Uso: python k8s-fixer.py <directorio|archivo>")
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

    print(f"\n📊 Procesados {len(yaml_files)} archivos. Corregidos: {fixed_count}")

if __name__ == "__main__":
    main()
