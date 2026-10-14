# Lazy Bootstrap

<p align="center">
  <img src="assets/lazy-bootstrap-logo-large.png" alt="Lazy Bootstrap logo" width="820">
</p>

<p align="center">
  <strong>One command. Less nonsense.</strong><br>
  A checkpointed Ubuntu VPS bootstrap for a repeatable shell, aaPanel, DNS/TLS, and optional local AI stack.
</p>

## What it does

Lazy Bootstrap is a single Bash installer plus a sourced environment file. It is designed for fresh Ubuntu cloud VMs and for recovering a partially completed installation without blindly repeating every operation.

The installer is intentionally **not** a cluster orchestrator. It prepares one VM. Multi-node routing, persistent research queues, scraping workers, and job scheduling belong in a separate control-plane project so a new worker can be added without turning its bootstrap into a cluster manager.

### Main sequence

1. **Preflight and recovery safety**
   - Checks Ubuntu and CPU architecture.
   - Detects the non-root SSH account and verifies its `authorized_keys`.
   - Elevates through `sudo`, loads the configuration, and records step checkpoints under `STATE_DIR`.
   - In recovery mode, checks live state before trusting an old checkpoint. The final audit retries failed categories once.

2. **Memory and base system**
   - Selects swap and conservative VM tuning from detected RAM.
   - Installs the base packages, Zsh, the configured target account, and Tailscale.
   - Installs Homebrew, GitHub CLI configuration, a Python virtual environment, Portsey, and the configured Nano syntax pack.

3. **Terminal setup**
   - Installs Zsh4Humans without starting an interactive shell in the installer.
   - Chooses one curated Nano/P10k theme pair at each bootstrap invocation. The pair is selected as a whole, rather than randomizing individual colors and prompt fragments.
   - Installs and validates the final dotfiles before marking the step complete.

4. **aaPanel and public access**
   - Installs/updates aaPanel Happy Edition using the configured primary and fallback sources.
   - Installs and verifies aaPanel's Nginx branch, registers the Cloudflare DNS provider, configures the panel hostname, and obtains a certificate.
   - Embeds the project's panel branding assets in the script, installs the custom logo/favicon and server-specific login background, and validates the branding step.
   - Adds reverse-proxy awareness for aaPanel's mobile QR/API flow, preserves the relevant HTTPS/Host headers, sets Cloudflare proxy trust according to the DNS record, and installs the `aapanel-mobile-doctor` diagnostic command.
   - Configures the guest firewall and hardens SSH last.

5. **Optional AI stack**
   - AI mode can be enabled, disabled, or prompted for during an interactive fresh install.
   - Installs Node.js and Codex CLI when AI mode is enabled.
   - Uses an aaPanel-visible Docker Compose project for Ollama and, when the VM has sufficient RAM, Open WebUI.
   - Pulls models according to detected memory and available disk, with an optional reasoning model and a small decision model.
   - Configures Open WebUI environment defaults for Exa search, Firecrawl page loading, subagents/background subagents, API endpoints, and the initial admin account.
   - Creates a Cloudflare DNS record, aaPanel site, TLS certificate, and reverse proxy for the Open WebUI dashboard.
   - Binds Ollama to loopback and, when available, the VM's Tailscale IP. It is not deliberately exposed on the public interface.

## Quick start

The repository's `env` file is a **safe template**. It contains placeholders, not working credentials.

1. Copy `bootstrap.sh` and `env` to the target Ubuntu VM while connected as the provider's normal SSH user.
2. On the target, rename `env` to `.env` because the script looks for `.env` beside itself by default.
3. Edit `.env`. Replace every `CHANGE_ME_...` value and set the correct hostname, panel domain, account details, and ports.
4. Keep the environment file private, then run:

   ```bash
   chmod 600 .env
   chmod +x bootstrap.sh
   ./bootstrap.sh
   ```

The script requests `sudo` itself. Run it from the SSH account whose public key should be carried to the configured target user. Do **not** run it with `sh bootstrap.sh`; it requires Bash.

For an alternate environment-file path, set `BOOTSTRAP_ENV_FILE=/path/to/file` when launching the script.

### Fresh vs recovery

- **Fresh** clears the bootstrap's completion markers and applies the sequence from the start.
- **Recovery** verifies actual system state and repairs steps that are missing or broken, even when a stale checkpoint exists.
- If stdin is not a terminal, the script selects a mode from existing checkpoint state. For unattended use, test that behavior on a disposable VM first.

The script randomizes the **predefined theme pair** on each invocation, including recovery. It does not randomly invent a color palette or mix incompatible prompt fragments.

## AI model policy

The defaults are conservative about concurrent memory use: Ollama is configured for one loaded model and one parallel request. The bootstrap's model choice is based on physical RAM, not on the VM's marketing label.

| Detected RAM | Primary model | Open WebUI |
| --- | --- | --- |
| Below 6 GiB | Small decision-model service only; no general model | Skipped |
| 6 to under 20 GiB | `qwen3.5:4b` | Enabled |
| 20 GiB or more | `qwen3.5:9b` | Enabled |

When RAM is at least 20 GiB, `AI_PULL_REASONING_MODEL=1`, and the filesystem has at least `AI_MODEL_MIN_FREE_GIB` free (default 35 GiB), the bootstrap also pulls `AI_REASONING_MODEL`, whose template default is `gpt-oss:20b`. That model can be useful for a specialist reasoning role, but it is larger and CPU inference can be slow on a 4-OCPU ARM VM. Set `AI_PULL_REASONING_MODEL=0` if disk, latency, or RAM headroom matters more than keeping that option cached.

The small decision model defaults to `tev1:0.8b`. Set `AI_PULL_DECISION_MODEL=0` to skip it. `AI_PRIMARY_MODEL=auto` enables RAM-based selection; setting a model name overrides the primary selection.

The bootstrap does **not** deploy LiteLLM, a multi-node scheduler, Redis, a durable task queue, or MCP servers. It exposes per-VM Ollama endpoints and records their local/Tailscale URLs in `~/.config/jq-ai/endpoints.env`. Add a separate gateway/queue layer when you are ready to make ORA5/ORA6/ORA7/AWS nodes a coordinated worker pool.

### Open WebUI defaults

The template enables web search with Exa, uses Firecrawl for page loading, enables subagents and background subagents, enables the Ollama and OpenAI-compatible endpoints, and disables web-search confirmation by default. Actual search/loading requires valid Exa and Firecrawl credentials.

`WEBUI_ADMIN_NAME`, `WEBUI_ADMIN_EMAIL`, and `WEBUI_ADMIN_PASSWORD` are only used to create the initial admin user when the Open WebUI database is empty. Existing Open WebUI databases retain their saved settings and accounts; changing these environment variables does not reset an existing installation.

The Open WebUI domain defaults to `oui-<hostname>.<Cloudflare zone>` when `OPENWEBUI_SUBDOMAIN=auto`. Use a unique hostname/subdomain for each VM. If a DNS record already points at another address, the bootstrap refuses to overwrite it unless `OPENWEBUI_DNS_OVERWRITE=1` is explicitly set.

## Environment reference

The `env` file is Bash syntax and is sourced by the installer. Keep values quoted as supplied, especially JSON-valued settings. The following variables are configurable.

### Identity and account

| Variable | Purpose |
| --- | --- |
| `HOSTNAME` | Desired server hostname. |
| `TARGET_USER` | User account the bootstrap prepares. |
| `TARGET_HOME` | Home directory for that user. |
| `SOURCE_USER_OVERRIDE` | Optional override when the source SSH-key account cannot be detected safely. Leave empty normally. |
| `NEW_USER_PASSWORD` | Password configured for the target account. Replace the placeholder before use. |

### Tailscale, GitHub, and SSH

| Variable | Purpose |
| --- | --- |
| `TAILSCALE_AUTH_KEY` | Tailscale auth key for joining the tailnet. Use a suitable short-lived/reusable key for your policy. |
| `GITHUB_USERNAME` | GitHub username used by the bootstrap's GitHub setup. |
| `GITHUB_TOKEN` | GitHub CLI authentication token. |
| `SSH_PORT` | SSH port configured during hardening. Also open it in the cloud firewall/security list. |

### Swap and VM tuning

| Variable | Purpose |
| --- | --- |
| `SWAP_FILE` | Swapfile path. |
| `SWAP_SIZE_MIB_OVERRIDE` | Explicit swap size in MiB; blank means auto-size from RAM. Set to `0` to disable the swapfile requirement. |
| `VM_SWAPPINESS_OVERRIDE` | Override the selected Linux swappiness. |
| `VM_VFS_CACHE_PRESSURE_OVERRIDE` | Override VFS cache pressure. |
| `VM_DIRTY_BACKGROUND_RATIO_OVERRIDE` | Override dirty-background ratio. |
| `VM_DIRTY_RATIO_OVERRIDE` | Override dirty ratio. |

### aaPanel and Nginx

| Variable | Purpose |
| --- | --- |
| `AAPANEL_URL_PRIMARY` | Primary Happy Edition installer URL. |
| `AAPANEL_URL_FALLBACK` | Fallback installer URL. |
| `AAPANEL_UPGRADE_URL_PRIMARY` | Primary Happy Edition update script. |
| `AAPANEL_UPGRADE_URL_FALLBACK` | Fallback update script. |
| `AAPANEL_EXPECTED_VERSION` | Expected installed aaPanel version. |
| `AAPANEL_PANEL_CERT_MODE` | Panel certificate mode; template uses `exact`. |
| `AAPANEL_DNS_PROPAGATION_SECONDS` | DNS propagation wait used for certificate issuance. |
| `AAPANEL_DOWNLOAD_CONNECT_TIMEOUT` | Connect timeout for installer downloads. |
| `AAPANEL_DOWNLOAD_MAX_TIME` | Maximum time for installer downloads. |
| `AAPANEL_ROOT` | aaPanel installation root. |
| `AAPANEL_PANEL_DIR` | aaPanel panel directory. |
| `AAPANEL_NGINX_DIR` | aaPanel-managed Nginx directory. |
| `AAPANEL_NGINX_FALLBACK_VERSION` | Fallback Nginx branch when catalog metadata is unavailable. |
| `AAPANEL_NGINX_VERSION_OVERRIDE` | Force a specific Nginx branch, such as `1.30`. |
| `AAPANEL_NGINX_CHECK_INTERVAL` | Interval between Nginx installation checks. |
| `AAPANEL_NGINX_STALL_SECONDS` | Duration used to detect a stalled Nginx build. |
| `AAPANEL_NGINX_HARD_TIMEOUT` | Wall-clock cutoff; `0` disables it. |
| `AAPANEL_NGINX_QUICK_FIRST` | Enables the quick-first Nginx installation path. |
| `AAPANEL_NGINX_COMPILE_FALLBACK` | Allows a source-compile fallback. |
| `AAPANEL_NGINX_TYPE0_FALLBACK` | Controls the alternate type-0 fallback path. |
| `AAPANEL_WWWROOT` | aaPanel website root directory. |
| `AAPANEL_PORT` | aaPanel listening port. |
| `AAPANEL_USER` | aaPanel login username. |
| `AAPANEL_PASSWORD` | aaPanel login password. |
| `AAPANEL_DOMAIN` | Public aaPanel hostname; set this for each VM. |

### Cloudflare

| Variable | Purpose |
| --- | --- |
| `CLOUDFLARE_EMAIL` | Cloudflare account email used for DNS/certificate automation. |
| `CLOUDFLARE_API_KEY` | Cloudflare API key used by the bootstrap. Keep it private. |
| `CLOUDFLARE_ALIAS` | Named Cloudflare credential/profile alias used by the local setup. |

### AI, Ollama, and Open WebUI lifecycle

| Variable | Purpose |
| --- | --- |
| `AI_INFERENCE_MODE` | `ask`, `1`/`yes`, or `0`/`no`. In non-interactive runs, `ask` disables AI unless explicitly forced on. |
| `OPENWEBUI_SUBDOMAIN` | Single DNS label for the dashboard, or `auto` for `oui-<hostname>`. |
| `WEBUI_URL` | Public Open WebUI URL or `auto`. |
| `OPENWEBUI_PORT` | Loopback port for the Open WebUI container. |
| `OLLAMA_PORT` | Local/Tailscale Ollama API port. |
| `AI_COMPOSE_NAME` | aaPanel Docker Compose project name. |
| `AI_PRIMARY_MODEL` | `auto` for RAM-based model selection, or an explicit Ollama model name. |
| `AI_REASONING_MODEL` | Optional secondary reasoning model; default `gpt-oss:20b`. |
| `AI_PULL_REASONING_MODEL` | `1` to pull the secondary model when RAM/disk conditions allow; `0` to skip it. |
| `AI_DECISION_MODEL` | Small decision/routing model name; default `tev1:0.8b`. |
| `AI_PULL_DECISION_MODEL` | Whether to pull the decision model. |
| `OPENWEBUI_IMAGE` | Open WebUI container image and tag. |
| `OLLAMA_MAX_LOADED_MODELS` | Maximum number of simultaneously loaded Ollama models. |
| `OLLAMA_NUM_PARALLEL` | Ollama parallel request count. Higher concurrency increases RAM pressure. |
| `OLLAMA_KEEP_ALIVE` | Ollama model keep-alive duration. |
| `OPENWEBUI_CF_PROXIED` | `1` to create a Cloudflare-proxied dashboard DNS record; otherwise DNS-only. |
| `OPENWEBUI_DNS_OVERWRITE` | `1` to permit replacing an existing dashboard A record that points elsewhere. |
| `TERMINAL_THEME` | Theme selector; `random` chooses one of the curated Nano/P10k combinations. |

### Open WebUI account and tools

| Variable | Purpose |
| --- | --- |
| `WEBUI_ADMIN_NAME` | Initial Open WebUI administrator display name. |
| `WEBUI_ADMIN_EMAIL` | Initial Open WebUI administrator email. |
| `WEBUI_ADMIN_PASSWORD` | Initial Open WebUI administrator password. |
| `ENABLE_WEB_SEARCH` | Enables Open WebUI web search. |
| `WEB_SEARCH_ENGINE` | Search provider name; template uses `exa`. |
| `EXA_API_KEY` | Exa search API key. |
| `WEB_LOADER_ENGINE` | Page-loader provider; template uses `firecrawl`. |
| `FIRECRAWL_API_BASE_URL` | Firecrawl API endpoint. |
| `FIRECRAWL_API_KEY` | Firecrawl API key. |
| `ENABLE_WEB_SEARCH_CONFIRMATION` | Enables/disables search confirmation prompts. |
| `ENABLE_SUBAGENTS` | Enables subagents. |
| `SUBAGENTS_BACKGROUND_ENABLED` | Enables background subagent work. |
| `SUBAGENTS_MAX_CONCURRENT` | Maximum concurrent subagents. |
| `SUBAGENTS_MAX_ASYNC` | Maximum asynchronous subagents. |
| `SUBAGENTS_MAX_ITERATIONS` | Maximum subagent iterations. |
| `SUBAGENTS_MAX_OUTPUT` | Maximum subagent output setting. |
| `TASK_MODEL` | Model used for task/helper operations. |
| `ENABLE_API_KEYS` | Enables API keys in Open WebUI. |
| `ENABLE_OLLAMA_API` | Enables the Ollama API integration. |
| `ENABLE_OPENAI_API` | Enables OpenAI-compatible API integration. |
| `DEFAULT_MODEL_PARAMS` | JSON for default model parameters. Keep valid JSON inside the supplied shell quotes. |
| `DEFAULT_MODEL_METADATA` | JSON for default model metadata/capabilities. |
| `DEFAULT_INTERFACE_SETTINGS` | JSON for initial interface defaults. |

### Repositories, paths, logging, and Zsh4Humans

| Variable | Purpose |
| --- | --- |
| `PORTSEY_REPO` | Portsey repository URL. |
| `NANORC_REPO` | Nano syntax-highlighting repository URL. |
| `BREW_PREFIX` | Homebrew installation prefix. |
| `BREW_BIN` | Homebrew executable path. |
| `STATE_DIR` | Checkpoint and persistent bootstrap state directory. |
| `LOG_FILE` | Bootstrap log file path. |
| `OXRC_GEMINI_API_KEY` | Optional key for the Ox editor Gemini plugin. Blank disables key-based plugin access; configure privately if needed. |
| `AUTO_ENTER_TARGET_SHELL` | `1` to switch into the target user's shell after a successful interactive run. |
| `STEP_WATCHDOG_SECONDS` | Interval for progress/watchdog messages during long steps. |
| `HOMEBREW_AUTO_YES` | Automatically answer Homebrew install/cask confirmation prompts. |
| `Z4H_UPSTREAM_URL` | Zsh4Humans source URL. |
| `Z4H_CORE_TIMEOUT` | Timeout for the core Zsh4Humans setup. |
| `Z4H_FINALIZE_TIMEOUT` | Timeout for final Zsh4Humans initialization/verification. |
| `Z4H_NET_CONNECT_TIMEOUT` | Connection timeout for Zsh4Humans network operations. |
| `Z4H_NET_MAX_TIME` | Maximum transfer time for Zsh4Humans network operations. |
| `Z4H_KEYBOARD` | Zsh4Humans keyboard/terminal keyboard mode. |
| `Z4H_START_TMUX` | Whether Zsh4Humans starts tmux. |
| `Z4H_DIRENV` | Whether Zsh4Humans enables direnv integration. |

The script also supports internal tuning variables such as `AI_MIN_LOCAL_RAM_MIB` (default 6144) and `AI_MODEL_MIN_FREE_GIB` (default 35); these are not included in the default template but can be exported before launch or added to the local `.env`.

## Important operational notes

- **Cloud firewall:** the script configures the guest OS firewall where supported, but it cannot open Oracle Cloud security lists or AWS security groups for you. Before running it, plan to allow TCP 80, 443, and your configured SSH port. The panel port may also need to be reachable if you access it directly.
- **Credentials:** never commit a real `.env`. The repository's `env` is a placeholder template; `.env` is ignored by Git. Use least-privilege credentials where the provider supports them, and rotate any credential that was accidentally committed.
- **aaPanel:** this project installs a third-party Happy Edition distribution and uses its installer/update endpoints. Review those sources and the script before using it on a sensitive machine.
- **Recovery is not a VM snapshot:** checkpoints make steps idempotent, but they do not replace a cloud snapshot or backup. Take one before recovering a production VM.
- **Model performance:** RAM fit is not the same as speed. A 20B model may fit in memory yet run slowly on CPU-only ARM hardware. Increase parallelism only after measuring actual memory use.
- **No automatic remote cloud firewall edits:** the bootstrap has no Oracle/AWS API credentials and will not mutate cloud-side network rules.

## Validation

The repository's CI checks Bash syntax and scans the tracked template for accidental credentials. You can run the basic local check with:

```bash
bash -n bootstrap.sh
bash -n env
```

The `env` file is intended to be renamed to `.env` only on the target VM, not committed under that name.

## Project assets

- `assets/lazy-bootstrap-logo-large.png` — large transparent wordmark.
- `assets/lazy-bootstrap-logo.png` — primary square mark.
- `assets/lazy-bootstrap-logo-small.png` — small icon.
- `assets/lazy-bootstrap-logo-large.svg` — scalable wordmark source.

### aaPanel updates and post-upgrade recovery

Bootstrap now targets **aaPanel Happy Edition 8.0.7 as a minimum**. If a VM already has
8.0.7 or a later version, a recovery run will not attempt to downgrade it,
including when an older `.env` still specifies `AAPANEL_EXPECTED_VERSION=8.0.6`.
The installer pins its requested version instead of relying on the upstream
updater's fragile two-second latest-version lookup, which otherwise can fall
back to an obsolete release when the network is slow.

A checkpointed `22c-panel-upgrade-guard` step installs the narrowly scoped
`jq-aapanel-upgrade-guard` service and systemd timer. It runs shortly after boot
and approximately every two minutes. It **skips active vendor upgrades**,
checks whether the panel is reachable on its configured internal HTTP or HTTPS
port, starts stopped panel services, and keeps the canonical Nginx panel
reverse proxy aligned with that protocol. It also repairs an unsupported
`lua_package_path` setting *only* when Nginx explicitly reports the missing
Lua directive **and** no active Lua/WAF directives are present. It validates
Nginx syntax before applying changes, retains root-only backups under
`/root/jq-aapanel-guard-backups/`, and never changes other website configurations,
DNS, or SSH. It also normalizes the stock Nginx SysV init script's misleading
"already running" exit status, so systemd can represent healthy Nginx correctly.

Inspect the guard with `systemctl status jq-aapanel-upgrade-guard.timer`,
`systemctl status jq-aapanel-upgrade-guard.service`, and
`journalctl -t jq-aapanel-upgrade-guard`. The guard is a safeguard for known
configuration drift, **not** a guarantee against unrelated future upstream
breakages, incompatible WAF updates, or failed packages.
