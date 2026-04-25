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

## Stable download URLs

Each push to `main` reruns `.github/workflows/main.yml`, which:

1. Installs `sing-box`, regenerates the JSON rule-sets, and compiles `.srs`.
2. Uploads `dist/` as a workflow run artifact (handy for inspecting a single run).
3. Republishes the rolling **`latest`** GitHub Release with the freshly built
   files attached. The tag `latest` is force-moved to the new commit, and the
   release is marked as the repository's latest, so the URLs below never change:

   | file                   | URL                                                                                         |
   | ---------------------- | ------------------------------------------------------------------------------------------- |
   | combined `.srs`        | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt.srs`                    |
   | domains-only `.srs`    | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt-domains.srs`            |
   | ips-only `.srs`        | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt-ips.srs`                |
   | combined source JSON   | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt.json`                   |
   | domains source JSON    | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt-domains.json`           |
   | ips source JSON        | `https://github.com/<owner>/<repo>/releases/latest/download/chatgpt-ips.json`               |

   GitHub resolves `/releases/latest/download/<file>` to whichever release is
   marked latest, so you can paste these URLs straight into your sing-box
   config and they keep returning the most recent build.

### How the auto-publish is wired up

- The workflow declares `permissions: contents: write` so the default
  `GITHUB_TOKEN` can create/update releases — no PAT or extra secret needed.
- `softprops/action-gh-release@v2` upserts the release: it moves the `latest`
  tag to the current commit, replaces the attached files, and re-marks the
  release as latest (`make_latest: "true"`).
- Pull requests build but skip the publish step (`if: github.event_name != 'pull_request'`),
  so forks/PRs can still validate without touching releases.
- To trigger a rebuild without changing the inputs, open
  **Actions → build-ruleset → Run workflow** (`workflow_dispatch`).
- After the first successful run on `main`, the rolling release page lives at
  `https://github.com/<owner>/<repo>/releases/tag/latest`.

### Using the rolling release in sing-box

Remote rule-set (recommended — sing-box re-fetches on `update_interval`):

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "chatgpt",
        "format": "binary",
        "url": "https://github.com/<owner>/<repo>/releases/latest/download/chatgpt.srs",
        "download_detour": "direct",
        "update_interval": "24h"
      }
    ],
    "rules": [
      { "rule_set": "chatgpt", "outbound": "proxy" }
    ]
  }
}
```

Or download manually and use as a local rule-set:

```json
{
  "type": "local",
  "tag": "chatgpt",
  "format": "binary",
  "path": "chatgpt.srs"
}
```
