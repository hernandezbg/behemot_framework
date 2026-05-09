"""
Validación de seguridad para fuentes RAG (paths locales y URLs).

Mitiga:
- Path traversal: lectura de archivos sensibles fuera de los directorios permitidos.
- SSRF: requests a metadata de cloud providers (AWS/GCP/Azure), loopback, redes
  internas o link-local.

La política se configura en el YAML/env:
- RAG_ALLOWED_ROOTS: lista de directorios permitidos para fuentes locales.
- RAG_ALLOWED_URL_HOSTS: lista blanca opcional de hosts HTTP/HTTPS.
- RAG_ALLOW_PRIVATE_NETWORKS: false por defecto. Permitir redes privadas solo
  para casos avanzados de despliegue interno controlado.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
from typing import Iterable, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# Hosts asociados a metadata services de cloud providers. Acceder a ellos desde
# una instancia con rol IAM permite robar credenciales temporales.
_METADATA_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "metadata.aws.internal",
        "metadata.azure.com",
        "169.254.169.254",   # AWS/GCP/Azure metadata IP
        "fd00:ec2::254",     # AWS IPv6 metadata
    }
)


class RagSourceRejected(ValueError):
    """Fuente rechazada por la política de seguridad."""


def _normalize_roots(roots: Iterable[str]) -> List[str]:
    """Resuelve cada root a una ruta absoluta canónica con separador final."""
    normalized: List[str] = []
    for r in roots:
        if not r:
            continue
        absroot = os.path.realpath(os.path.abspath(r))
        if not absroot.endswith(os.sep):
            absroot += os.sep
        normalized.append(absroot)
    return normalized


def validate_local_path(path: str, allowed_roots: Iterable[str]) -> str:
    """
    Valida que `path` esté dentro de alguno de los `allowed_roots`.

    Resuelve symlinks (`os.path.realpath`) antes de comparar para evitar
    bypass por enlaces simbólicos. Devuelve la ruta canónica.

    Levanta RagSourceRejected si la ruta cae fuera de la política.
    """
    if not path:
        raise RagSourceRejected("Ruta vacía no permitida")

    roots = _normalize_roots(allowed_roots)
    if not roots:
        # Si el operador no ha configurado roots, somos estrictos: rechazar
        # rutas absolutas y aceptar solo relativas resueltas contra el CWD.
        # Esto evita que un agente recién creado lea /etc/passwd "por accidente".
        absolute_resolved = os.path.realpath(os.path.abspath(path))
        cwd_root = os.path.realpath(os.getcwd()) + os.sep
        if not absolute_resolved.startswith(cwd_root):
            raise RagSourceRejected(
                f"RAG_ALLOWED_ROOTS no configurado y la ruta '{path}' "
                f"queda fuera del directorio de trabajo. Configura "
                f"RAG_ALLOWED_ROOTS para autorizar fuentes externas."
            )
        return absolute_resolved

    resolved = os.path.realpath(os.path.abspath(path))
    for root in roots:
        # Comparación con separador final para evitar que '/foo' matchee '/foobar'.
        if resolved == root.rstrip(os.sep) or resolved.startswith(root):
            return resolved

    raise RagSourceRejected(
        f"Ruta '{path}' fuera de los RAG_ALLOWED_ROOTS configurados"
    )


def _resolve_host_ips(hostname: str) -> List[ipaddress._BaseAddress]:
    """Resuelve hostname a todas sus IPs (v4 + v6)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise RagSourceRejected(f"No se pudo resolver el host '{hostname}': {exc}")
    ips: List[ipaddress._BaseAddress] = []
    for family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ips.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    return ips


def _is_disallowed_ip(ip: ipaddress._BaseAddress) -> bool:
    """Devuelve True si la IP está en un rango sensible (privado, loopback, etc.)."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(
    url: str,
    allowed_hosts: Optional[Iterable[str]] = None,
    allow_private_networks: bool = False,
) -> str:
    """
    Valida que la URL sea segura para hacer una request desde el servidor.

    - Rechaza esquemas distintos a http/https.
    - Rechaza dominios de metadata cloud y la IP 169.254.169.254.
    - Rechaza hosts cuya resolución dé IPs privadas/loopback/link-local
      (a menos que `allow_private_networks=True`).
    - Si `allowed_hosts` está definido, solo permite hosts en la lista.
    """
    if not url:
        raise RagSourceRejected("URL vacía no permitida")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise RagSourceRejected(f"Esquema no permitido: {parsed.scheme!r}")

    host = (parsed.hostname or "").lower()
    if not host:
        raise RagSourceRejected(f"URL sin host: {url}")

    if host in _METADATA_HOSTS:
        raise RagSourceRejected(
            f"Host bloqueado (metadata cloud / link-local): {host}"
        )

    if allowed_hosts:
        allowed_set = {h.lower() for h in allowed_hosts if h}
        if allowed_set and host not in allowed_set:
            raise RagSourceRejected(
                f"Host '{host}' no está en RAG_ALLOWED_URL_HOSTS"
            )

    # Resolver el host: aunque el nombre no sea metadata.*, podría apuntar a
    # 169.254.169.254 vía DNS rebinding. Validamos la IP real.
    ips = _resolve_host_ips(host)
    if not ips:
        raise RagSourceRejected(f"No se obtuvieron IPs para '{host}'")

    for ip in ips:
        if str(ip) in _METADATA_HOSTS:
            raise RagSourceRejected(f"IP bloqueada (metadata): {ip}")
        if _is_disallowed_ip(ip) and not allow_private_networks:
            raise RagSourceRejected(
                f"IP en rango privado/loopback/link-local bloqueada: {ip}"
            )

    return url


def get_policy_from_config(config) -> dict:
    """
    Extrae la política RAG desde el `Config` global. Devuelve un dict con
    claves: allowed_roots, allowed_url_hosts, allow_private_networks.
    """
    raw_roots = config.get("RAG_ALLOWED_ROOTS", None)
    if raw_roots is None:
        # Fallback razonable: usar RAG_FOLDERS como roots permitidos cuando el
        # operador no haya definido RAG_ALLOWED_ROOTS explícitamente.
        raw_roots = config.get("RAG_FOLDERS", []) or []
    if isinstance(raw_roots, str):
        raw_roots = [r.strip() for r in raw_roots.split(",") if r.strip()]

    raw_hosts = config.get("RAG_ALLOWED_URL_HOSTS", []) or []
    if isinstance(raw_hosts, str):
        raw_hosts = [h.strip() for h in raw_hosts.split(",") if h.strip()]

    allow_private = bool(config.get("RAG_ALLOW_PRIVATE_NETWORKS", False))

    return {
        "allowed_roots": list(raw_roots),
        "allowed_url_hosts": list(raw_hosts),
        "allow_private_networks": allow_private,
    }
