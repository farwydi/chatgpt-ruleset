# chatgpt-ruleset

Generator of [sing-box](https://sing-box.sagernet.org/) rule-set artifacts
(`.json` source + compiled `.srs`) from two plain-text inputs:

- `sources/domains.txt` — one domain per line
- `sources/iplist.txt` — one CIDR (or bare IP) per line

## Usage

```sh
# build JSON rule-sets (and .srs if `sing-box` is on PATH)
python3 scripts/build_ruleset.py

# or via make
make build
```

Outputs land in `dist/`:

| file                    | content                                |
| ----------------------- | -------------------------------------- |
| `chatgpt-domains.json`  | domain-only rule-set                   |
| `chatgpt-ips.json`      | ip_cidr-only rule-set                  |
| `chatgpt.json`          | combined rule-set                      |
| `*.srs`                 | binary form, compiled by `sing-box`    |

Override paths or naming:

```sh
python3 scripts/build_ruleset.py \
  --domains sources/domains.txt \
  --ips sources/iplist.txt \
  --out dist/ \
  --name chatgpt
```

## Input format

### `sources/domains.txt`

Comments start with `#`. By default each entry is auto-classified:

| line                       | sing-box rule           |
| -------------------------- | ----------------------- |
| `openai.com`               | `domain_suffix`         |
| `.openai.com`              | `domain_suffix`         |
| `*.chatgpt.com`            | `domain_regex`          |
| `full:platform.openai.com` | `domain` (exact match)  |
| `suffix:openai.com`        | `domain_suffix`         |
| `keyword:openai`           | `domain_keyword`        |
| `regex:^chat-.*\.com$`     | `domain_regex`          |

A bare apex like `openai.com` becomes a `domain_suffix`, which in sing-box
matches the apex **and** every subdomain.

### `sources/iplist.txt`

One entry per line. Bare IPv4/IPv6 addresses are normalized to `/32` and `/128`.
Comments start with `#`.

## Using the artifact in sing-box

```json
{
  "route": {
    "rule_set": [
      {
        "type": "local",
        "tag": "chatgpt",
        "format": "binary",
        "path": "chatgpt.srs"
      }
    ],
    "rules": [
      { "rule_set": "chatgpt", "outbound": "proxy" }
    ]
  }
}
```

For remote use, host the `.srs` file (or the `.json` source with
`"format": "source"`) and reference it via `"type": "remote"`.

## CI

A GitHub Actions workflow that rebuilds the rule-sets on every push and
uploads `dist/` as an artifact can be added at `.github/workflows/build.yml`
(the file is intentionally not committed here so the repo can be pushed with
a token that lacks the `workflow` scope).
