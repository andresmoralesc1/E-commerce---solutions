#!/usr/bin/env python3
"""
Namecheap DNS sync — script SEGURO para no perder records.

ESTRATEGIA:
1. GET actuales
2. Merge con desired (upsert por host+type)
3. Whitelist: NUNCA tocar hosts/types críticos (MX, mail, DKIM, _dmarc)
4. Dry-run default — diff visible antes de aplicar
5. Backup automático pre-write
6. SET atómico solo si se confirma explícitamente

USO:
  python namecheap-dns-sync.py --dry-run              # ver diff, no aplica
  python namecheap-dns-sync.py --apply --confirm      # aplicar (peligroso)

⚠️ NO EJECUTAR --apply hasta que el sistema esté probado en local.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_USER = os.environ.get("NAMECHEAP_API_USER", "")
API_KEY = os.environ.get("NAMECHEAP_API_KEY", "")
CLIENT_IP = os.environ.get("NAMECHEAP_IP", "")
API_BASE = "https://api.namecheap.com/xml.response"

# ─── Hosts / Types NUNCA tocar ────────────────────────────────────────────
PROTECTED_HOSTS = {
    "@", "", "mail", "autodiscover", "autoconfig", "mta-sts",
    "_dmarc", "webmail", "smtp", "imap", "pop", "pop3",
    # TLD-level (otro dominio)
    "cleida.com.co", "mail.cleida.com.co", "autodiscover.cleida.com.co",
    "autoconfig.cleida.com.co", "mta-sts.cleida.com.co",
}
PROTECTED_TYPES = {"MX", "TXT", "NS", "CAA", "SRV"}

# ─── Subdominios que queremos gestionar ──────────────────────────────────
# Cada entrada: (host, type, value) — el host es relativo al dominio raíz.
DESIRED_RECORDS: list[tuple[str, str, str]] = [
    # host, type, value
    ("ecommerce.dashboard", "A", "38.242.194.196"),
    ("ecommerce.api", "A", "38.242.194.196"),
    ("ecommerce.flows", "A", "38.242.194.196"),
    ("ecommerce.wa", "A", "38.242.194.196"),
]


def _parse_xml(body: str) -> ET.Element:
    """Parse XML Namecheap con namespace. Si el namespace no se usa,
    funciona también."""
    return ET.fromstring(body)


def api_call(command: str, **params: Any) -> ET.Element:
    qs = urlencode({
        "ApiUser": API_USER,
        "ApiKey": API_KEY,
        "UserName": API_USER,
        "ClientIp": CLIENT_IP,
        "Command": command,
        **params,
    })
    req = Request(f"{API_BASE}?{qs}")
    with urlopen(req, timeout=30) as r:
        body = r.read().decode()
    root = _parse_xml(body)
    if root.attrib.get("Status") != "OK":
        # Error element está en {ns}Error (namespace de Namecheap)
        err = None
        for candidate in root.iter():
            if candidate.tag.endswith("}Error") or candidate.tag == "Error":
                err = candidate
                break
        err_number = err.get("Number") if err is not None else None
        err_text = err.text if err is not None else body[:300]
        if err_number == "2019166":
            raise NamecheapDNSNotOurs(err_text or "domain not using our DNS")
        raise SystemExit(f"Namecheap API error ({err_number}): {err_text}")
    return root


class NamecheapDNSNotOurs(Exception):
    """El dominio no usa nameservers de Namecheap."""


def get_hosts(domain: str) -> tuple[list[dict[str, str]], bool]:
    """Returns (hosts, is_using_namedns). Si is_using_namedns=False,
    no podemos editar los records vía API — el cliente debe migrar
    primero los nameservers a Namecheap."""
    root = api_call(
        "namecheap.domains.dns.getHosts",
        SLd=domain,
    )
    is_our_dns = root.find(
        ".//DomainDNSGetHostsResult"
    ).get("IsUsingOurDNS", "true") == "true"

    hosts: list[dict[str, str]] = []
    for h in root.findall(".//host"):
        hosts.append({
            "host_id": h.get("HostId", ""),
            "name": h.get("Name", ""),
            "type": h.get("Type", ""),
            "address": h.get("Address", ""),
            "ttl": h.get("TTL", ""),
        })
    return hosts, is_our_dns


def set_hosts(domain: str, hosts: list[dict[str, str]]) -> None:
    params: dict[str, Any] = {"SLd": domain}
    for i, h in enumerate(hosts):
        params[f"HostName{i+1}"] = h["name"]
        params[f"RecordType{i+1}"] = h["type"]
        params[f"Address{i+1}"] = h["address"]
        params[f"TTL{i+1}"] = h.get("ttl") or 1800
    api_call("namecheap.domains.dns.setHostRecords", **params)


def merge_desired(
    current: list[dict[str, str]],
    desired: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    """Upsert desired en current. Mantiene el resto intacto."""
    by_key: dict[tuple[str, str], dict[str, str]] = {
        (h["name"], h["type"]): h for h in current
    }
    for name, type_, address in desired:
        key = (name, type_)
        if key in by_key:
            by_key[key]["address"] = address  # update
        else:
            by_key[key] = {"name": name, "type": type_, "address": address, "ttl": "1800", "host_id": ""}
    return list(by_key.values())


def filter_protected(hosts: list[dict[str, str]]) -> list[dict[str, str]]:
    """Quita cambios accidentales a hosts críticos. (El merge no los tocaba ya,
    pero esto es safety belt adicional.)"""
    return [
        h for h in hosts
        if h["name"] not in PROTECTED_HOSTS and h["type"] not in PROTECTED_TYPES
        or h["host_id"]  # conservar records existentes (tienen HostId)
    ]


def diff_records(
    before: list[dict[str, str]],
    after: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    bset = {(h["name"], h["type"]): h for h in before}
    aset = {(h["name"], h["type"]): h for h in after}
    return {
        "added": [aset[k] for k in aset.keys() - bset.keys()],
        "modified": [
            {"before": bset[k], "after": aset[k]}
            for k in aset.keys() & bset.keys()
            if bset[k]["address"] != aset[k]["address"]
        ],
        "removed": [bset[k] for k in bset.keys() - aset.keys()],
    }


def backup(hosts: list[dict[str, str]]) -> Path:
    backups = Path("backups")
    backups.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    p = backups / f"dns-{ts}.json"
    p.write_text(json.dumps(hosts, indent=2, ensure_ascii=False))
    return p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True, help="e.g. andresmorales.com.co")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="skip interactive prompt")
    args = parser.parse_args()

    if not (API_USER and API_KEY and CLIENT_IP):
        sys.exit("Faltan vars: NAMECHEAP_API_USER, NAMECHEAP_API_KEY, NAMECHEAP_IP")

    print(f"🔍 GET hosts de {args.domain}…")
    try:
        current, is_our_dns = get_hosts(args.domain)
    except NamecheapDNSNotOurs as e:
        print()
        print("⚠️  ESTE DOMINIO USA NAMESERVERS CUSTOM (no Namecheap).")
        print(f"   {e}")
        print()
        print("   No podemos editar DNS vía API hasta que migres a Namecheap DNS.")
        print()
        print("Pasos para migrar:")
        print(f"  1. Namecheap Dashboard → Domain List → {args.domain} → Manage")
        print("  2. Nameservers → 'Namecheap BasicDNS' → Save")
        print("  3. Espera 5-30 min a que propague")
        print("  4. Vuelve a correr este script")
        print()
        print("Alternativa: crea los records manualmente en tu proveedor DNS")
        print("apuntando a 38.242.194.196:")
        for name, type_, addr in DESIRED_RECORDS:
            print(f"  {name:<30} {type_:<5} {addr}")
        sys.exit(0)
    if not is_our_dns:
        print()
        print("⚠️  ESTE DOMINIO USA NAMESERVERS CUSTOM (no Namecheap).")
        print("    No podemos editar DNS hasta que migres a Namecheap DNS.")
        print()
        print("Pasos para migrar:")
        print(f"  1. Namecheap Dashboard → Domain List → {args.domain} → Manage")
        print("  2. Nameservers → 'Namecheap BasicDNS' → Save")
        print("  3. Espera 5-30 min a que propague")
        print("  4. Vuelve a correr este script")
        print()
        print("Alternativa: crea los records manualmente en tu proveedor DNS")
        print("apuntando a 38.242.194.196:")
        for name, type_, addr in DESIRED_RECORDS:
            print(f"  {name:<30} {type_:<5} {addr}")
        sys.exit(0)
    print(f"   {len(current)} records actuales")
    for h in current[:5]:
        print(f"     - {h['name'] or '@':<30} {h['type']:<5} {h['address']}")
    if len(current) > 5:
        print(f"     … (+{len(current) - 5} más)")

    desired = DESIRED_RECORDS
    print(f"\n🎯 DESIRED: {len(desired)} nuevos/updates:")
    for name, type_, addr in desired:
        print(f"     - {name:<30} {type_:<5} {addr}")

    merged = merge_desired(current, desired)
    diff = diff_records(current, merged)

    print("\n📊 DIFF:")
    print(f"   ➕ added   : {len(diff['added'])}")
    for h in diff["added"]:
        print(f"      - {h['name']:<30} {h['type']:<5} {h['address']}")
    print(f"   ✏️ modified: {len(diff['modified'])}")
    for d in diff["modified"]:
        print(f"      - {d['before']['name']:<30} {d['before']['type']:<5} "
              f"{d['before']['address']} → {d['after']['address']}")
    print(f"   ❌ removed : {len(diff['removed'])}")
    for h in diff["removed"]:
        print(f"      - {h['name']:<30} {h['type']:<5} {h['address']}")

    if not (diff["added"] or diff["modified"] or diff["removed"]):
        print("\n✅ Sin cambios. No-op.")
        return

    if args.dry_run or not args.apply:
        print("\n🚧 DRY-RUN (no se aplicó nada). Para aplicar:")
        print(f"   python {sys.argv[0]} --domain {args.domain} --apply --confirm")
        return

    if not args.confirm:
        resp = input("\n⚠️  CONFIRMA aplicar cambios (escribe 'SI' en mayúsculas): ")
        if resp != "SI":
            sys.exit("Cancelado.")

    bkp = backup(current)
    print(f"\n💾 Backup guardado en {bkp}")
    set_hosts(args.domain, merged)
    print(f"✅ {len(diff['added']) + len(diff['modified'])} cambios aplicados.")


if __name__ == "__main__":
    main()