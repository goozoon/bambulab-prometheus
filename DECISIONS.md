# Design Decisions

This document explains key architectural and implementation decisions made during development.

## Why Standalone LXC Container?

**Decision:** Deploy exporter in its own dedicated LXC container instead of bundling with Prometheus/Grafana.

**Reasons:**
- **Separation of concerns** - Each service has one job, easier to understand
- **Independent updates** - Update exporter without touching monitoring stack
- **Better troubleshooting** - Isolated logs, clear boundaries
- **Security isolation** - Exporter can't access Prometheus data
- **Resource control** - Prevent one service from starving others
- **Flexibility** - Easy to add more printer exporters without reconfiguring Prometheus

## Why No Docker?

**Decision:** Native systemd service instead of Docker container.

**Reasons:**
- **Simpler for homelab users** - Most homelabs run Proxmox with LXC, not Docker
- **Lower overhead** - No Docker daemon, direct systemd management
- **Better integration** - Standard Linux service with `journalctl` logs
- **Easier debugging** - Direct file access, no container layers
- **Resource efficiency** - 512MB LXC vs Docker's additional overhead

## State Detection: `get_state()` vs `get_current_state()`

**Decision:** Use `get_state()` instead of `get_current_state()` for printer state.

**Reason:**
- `get_current_state()` returns stale data (shows `PRINTING` even when idle)
- `get_state()` returns accurate real-time state
- Discovered through testing and log analysis
- Mapped `RUNNING` state (not `PRINTING`) to "Printing" status

## Light State: String vs Boolean

**Decision:** Check `if light_state == "on"` instead of `if light_state`.

**Reason:**
- API returns strings `"on"`/`"off"`, not booleans
- String `"off"` is truthy in Python, causing incorrect display
- Explicit string comparison prevents false positives

## Camera Feed Architecture

**Decision:** Separate Flask server on port 9101 for camera feed, not embedded in Prometheus metrics.

**Reasons:**
- **Separation of concerns** - Metrics and media are different protocols
- **No database bloat** - Images served on-demand via HTTP, not stored
- **Grafana compatibility** - Text panel with iframe works universally
- **Bandwidth efficiency** - Only loads image when dashboard is viewed
- **Simple auto-refresh** - HTML meta refresh tag, no JavaScript needed

## Dashboard Strategy: Two Versions

**Decision:** Provide both `a1-dashboard.json` (15 panels) and `comprehensive-dashboard.json` (19 panels).

**Reasons:**
- **A1 Dashboard** - Optimized for A1/A1 Mini users (no chamber temp, simpler)
- **Comprehensive** - All metrics for X1/P1 series and advanced users
- **User choice** - Import what fits your needs
- **Maintenance** - Easier to update one without breaking the other

## Idle State Display

**Decision:** Show `--` instead of `0` for progress/layers/time when printer is idle.

**Reason:**
- `0%` progress looks like "just started printing"
- `--` clearly indicates "not applicable right now"
- Better UX - users immediately know printer is idle

## Error Code Display

**Decision:** Map `0` → "Healthy" (green) instead of showing raw number.

**Reason:**
- `0` means "no error" but isn't obvious to users
- "Healthy" is clearer and more reassuring
- Green color reinforces positive status
- Non-zero codes still show as red "Error" with the actual code

## Configuration: YAML over JSON/TOML

**Decision:** Use YAML for configuration file.

**Reasons:**
- **Human-readable** - Comments, clear structure
- **Industry standard** - Same as Prometheus/Kubernetes
- **Python native** - `PyYAML` is lightweight and standard
- **Familiar** - Most homelab users already work with YAML

## Install Script Features

**Decision:** Interactive installer with printer management (add/remove/reconfigure).

**Reasons:**
- **Beginner-friendly** - Guided setup, no manual editing
- **Multi-printer support** - Easy to add/remove printers
- **Auto-detection** - Detects LXC IP for camera configuration
- **Idempotent** - Safe to re-run, preserves existing config
- **Validation** - Checks dependencies, tests connections

## Metric Naming Convention

**Decision:** Use `bambu_` prefix and descriptive names like `bambu_nozzle_temperature_celsius`.

**Reasons:**
- **Namespace isolation** - Won't conflict with other exporters
- **Self-documenting** - Metric name tells you what it measures
- **Units in name** - `_celsius`, `_percent`, `_seconds` for clarity
- **Prometheus best practices** - Follows official naming guidelines

## Logging Strategy

**Decision:** INFO-level logging for state changes, no DEBUG spam in production.

**Reasons:**
- **Actionable logs** - See important events without noise
- **Troubleshooting** - State transitions logged at INFO level
- **Performance** - Less I/O overhead
- **Journald integration** - Works well with `journalctl -f`

## Why Flask for Camera (Not aiohttp/FastAPI)?

**Decision:** Use Flask for camera server despite the warning about "development server".

**Reasons:**
- **Simplicity** - Single-file implementation, no complex setup
- **Sufficient** - Camera endpoint is low-traffic (1-2 requests/sec max)
- **Lightweight** - No async overhead needed for simple JPEG serving
- **Proven** - Works reliably in production homelab environments
- **Easy debugging** - Standard Flask, well-documented

The "development server" warning is fine for homelab use - this isn't a public-facing web service.

## Documentation Structure

**Decision:** Multiple focused files (README, METRICS, TROUBLESHOOTING) instead of one large README.

**Reasons:**
- **Easier navigation** - Jump directly to what you need
- **Better maintenance** - Update one file without scrolling through 1000 lines
- **GitHub rendering** - Tables of contents, cross-links work better
- **Searchability** - Find specific topics quickly

## Git Workflow

**Decision:** 
- **Gitea** (private) - Full commit history, development work
- **GitHub** (public) - Single initial commit, clean public release

**Reasons:**
- **Clean public repo** - Users don't see "fix typo" commits
- **Private history preserved** - Full development trail in Gitea
- **Professional appearance** - Public repo looks polished
- **Easier contribution** - No confusing history for new contributors

## Dependencies and References

**Decision:** Use existing well-maintained libraries instead of writing custom implementations.

**Key Dependencies:**
- **bambulabs_api** - Core printer communication library
  - Source: [https://github.com/greghesp/ha-bambulab](https://github.com/greghesp/ha-bambulab)
  - Reason: Mature, actively maintained, handles MQTT complexity
  - License: MIT (compatible)
  
- **prometheus_client** - Official Prometheus Python client
  - Source: [https://github.com/prometheus/client_python](https://github.com/prometheus/client_python)
  - Reason: Industry standard, well-documented
  
- **Flask** - Lightweight web framework for camera endpoint
  - Source: [https://flask.palletsprojects.com/](https://flask.palletsprojects.com/)
  - Reason: Simple, widely used, minimal overhead
  
- **Pillow** - Image processing for camera feed
  - Source: [https://python-pillow.org/](https://python-pillow.org/)
  - Reason: Standard Python image library

**Inspiration:**
- Prometheus exporter patterns from official documentation
- Grafana dashboard design from community examples
- Systemd service structure from standard Linux practices

**Why Not Build From Scratch:**
- **Time to market** - Focus on integration, not reinventing MQTT/Prometheus
- **Reliability** - Leverage battle-tested libraries
- **Community support** - Issues already solved, documentation exists
- **Security** - Libraries receive regular security updates
- **Maintenance** - Less code to maintain ourselves