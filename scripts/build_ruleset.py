#!/usr/bin/env python3
"""Build sing-box rule-set artifacts from a plain domain list and IP list.

Inputs (defaults relative to the repo root):
    sources/domains.txt
    sources/iplist.txt

Outputs (written into dist/):
    chatgpt-domains.json   sing-box rule-set source (domains only)
    chatgpt-ips.json       sing-box rule-set source (ip_cidr only)
    chatgpt.json           combined rule-set source
    *.srs                  binary rule-sets, only when `sing-box` is on PATH

Run:
    python3 scripts/build_ruleset.py
    python3 scripts/build_ruleset.py --domains other.txt --ips other.txt --out build/
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOMAINS = REPO_ROOT / "sources" / "domains.txt"
DEFAULT_IPS = REPO_ROOT / "sources" / "iplist.txt"
DEFAULT_OUT = REPO_ROOT / "dist"

# sing-box rule-set source schema version. v3 is supported by sing-box >= 1.11.
RULESET_VERSION = 3


@dataclass
class DomainBuckets:
    domain: list[str] = field(default_factory=list)
    domain_suffix: list[str] = field(default_factory=list)
    domain_keyword: list[str] = field(default_factory=list)
    domain_regex: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.domain or self.domain_suffix or self.domain_keyword or self.domain_regex)


@dataclass
class IPBuckets:
    ip_cidr: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.ip_cidr


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        sys.exit(f"error: input file not found: {path}")
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # strip inline comments (`example.com  # note`)
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


_DOMAIN_RE = re.compile(r"^[A-Za-z0-9_*.-]+$")


def classify_domain(entry: str, buckets: DomainBuckets) -> None:
    """Sort one line from the domain file into the right sing-box bucket."""
    if ":" in entry:
        kind, _, value = entry.partition(":")
        kind = kind.strip().lower()
        value = value.strip().lower()
        if not value:
            raise ValueError(f"empty value after prefix in {entry!r}")
        if kind == "full":
            buckets.domain.append(value)
            return
        if kind in {"suffix", "domain_suffix"}:
            buckets.domain_suffix.append(value.lstrip("."))
            return
        if kind in {"keyword", "domain_keyword"}:
            buckets.domain_keyword.append(value)
            return
        if kind in {"regex", "domain_regex"}:
            buckets.domain_regex.append(value)
            return
        raise ValueError(f"unknown prefix in {entry!r}")

    value = entry.lower()
    if value.startswith("."):
        buckets.domain_suffix.append(value.lstrip("."))
        return
    if "*" in value or not _DOMAIN_RE.match(value):
        # treat anything wildcard-ish or with regex meta as regex
        buckets.domain_regex.append(value)
        return
    # bare domain → cover apex + subdomains (suffix match against the apex
    # in sing-box matches both `example.com` and `*.example.com`)
    buckets.domain_suffix.append(value)


def classify_ip(entry: str, buckets: IPBuckets) -> None:
    try:
        net = ipaddress.ip_network(entry, strict=False)
    except ValueError as exc:
        raise ValueError(f"invalid CIDR/IP {entry!r}: {exc}") from exc
    buckets.ip_cidr.append(str(net))


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_domain_buckets(path: Path) -> DomainBuckets:
    buckets = DomainBuckets()
    for entry in read_lines(path):
        try:
            classify_domain(entry, buckets)
        except ValueError as exc:
            sys.exit(f"error: {exc}")
    buckets.domain = dedupe(buckets.domain)
    buckets.domain_suffix = dedupe(buckets.domain_suffix)
    buckets.domain_keyword = dedupe(buckets.domain_keyword)
    buckets.domain_regex = dedupe(buckets.domain_regex)
    return buckets


def build_ip_buckets(path: Path) -> IPBuckets:
    buckets = IPBuckets()
    for entry in read_lines(path):
        try:
            classify_ip(entry, buckets)
        except ValueError as exc:
            sys.exit(f"error: {exc}")
    buckets.ip_cidr = dedupe(buckets.ip_cidr)
    return buckets


def make_rule(domains: DomainBuckets | None, ips: IPBuckets | None) -> dict:
    rule: dict[str, list[str]] = {}
    if domains and not domains.is_empty():
        if domains.domain:
            rule["domain"] = domains.domain
        if domains.domain_suffix:
            rule["domain_suffix"] = domains.domain_suffix
        if domains.domain_keyword:
            rule["domain_keyword"] = domains.domain_keyword
        if domains.domain_regex:
            rule["domain_regex"] = domains.domain_regex
    if ips and not ips.is_empty():
        rule["ip_cidr"] = ips.ip_cidr
    return rule


def write_ruleset(path: Path, rule: dict) -> None:
    if not rule:
        return
    payload = {"version": RULESET_VERSION, "rules": [rule]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compile_srs(json_path: Path) -> Path | None:
    """Compile a JSON rule-set to .srs via the sing-box CLI, if available."""
    sing_box = shutil.which("sing-box")
    if not sing_box:
        return None
    srs_path = json_path.with_suffix(".srs")
    cmd = [sing_box, "rule-set", "compile", "--output", str(srs_path), str(json_path)]
    subprocess.run(cmd, check=True)
    return srs_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domains", type=Path, default=DEFAULT_DOMAINS, help="path to the domain list")
    parser.add_argument("--ips", type=Path, default=DEFAULT_IPS, help="path to the IP/CIDR list")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--name", default="chatgpt", help="base name for output files")
    parser.add_argument("--no-compile", action="store_true", help="skip .srs compilation even if sing-box is present")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    domains = build_domain_buckets(args.domains)
    ips = build_ip_buckets(args.ips)

    args.out.mkdir(parents=True, exist_ok=True)

    artifacts: list[Path] = []

    domain_rule = make_rule(domains, None)
    if domain_rule:
        domain_path = args.out / f"{args.name}-domains.json"
        write_ruleset(domain_path, domain_rule)
        artifacts.append(domain_path)

    ip_rule = make_rule(None, ips)
    if ip_rule:
        ip_path = args.out / f"{args.name}-ips.json"
        write_ruleset(ip_path, ip_rule)
        artifacts.append(ip_path)

    combined_rule = make_rule(domains, ips)
    if combined_rule:
        combined_path = args.out / f"{args.name}.json"
        write_ruleset(combined_path, combined_rule)
        artifacts.append(combined_path)

    if not artifacts:
        sys.exit("error: both inputs were empty; nothing to build")

    print(f"wrote {len(artifacts)} JSON rule-set(s) to {args.out}")
    for path in artifacts:
        print(f"  {path.relative_to(REPO_ROOT)}")

    if args.no_compile:
        return 0

    sing_box = shutil.which("sing-box")
    if not sing_box:
        print("note: sing-box not found on PATH, skipping .srs compilation")
        return 0

    print(f"compiling .srs with {sing_box}")
    for path in artifacts:
        srs = compile_srs(path)
        if srs:
            print(f"  {srs.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
