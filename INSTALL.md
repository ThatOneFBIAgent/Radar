# Installation Guide

Complete setup instructions for Radar on Windows and Linux.

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **Python** | 3.11 | 3.12+ |
| **OS** | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| **RAM** | 256 MB | 512 MB |
| **Display** | 1280×720 | 1920×1080 |
| **Network** | Internet connection required for live data | — |

### Optional (for native extensions)

| Tool | Purpose |
|---|---|
| **Rust toolchain** | Build `radar_accel` (fast JSON parsing) |
| **C compiler** | Build `radar_signal` (signal smoothing) |
| **maturin** | Python ↔ Rust build tool |
| **cffi** | Python ↔ C build tool |

> **Note:** The application works fully without Rust/C extensions. They're optional performance boosters.

---

## Python Installation

### 1. Verify Python version

```bash
python --version
# Must be 3.11 or higher
```

If you need Python 3.11+:

- **Windows:** Download from [python.org](https://www.python.org/downloads/)
- **Linux:** `sudo apt install python3.11 python3.11-venv`

### 2. Clone the repository

```bash
git clone https://github.com/yourusername/radar.git
cd radar
```

### 3. Create a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. Install Radar

```bash
# Standard install
pip install -e .

# With development tools (pytest, ruff, mypy)
pip install -e ".[dev]"
```

### 5. Run

```bash
python -m radar
```

---

## Rust Extension Setup (Optional)

The Rust extension (`radar_accel`) provides faster GeoJSON parsing. Benchmark: ~5x faster for feeds with 1000+ events.

### 1. Install Rust toolchain

```bash
# Windows: Download from https://rustup.rs/
# Or run:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Linux:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### 2. Install maturin

```bash
pip install maturin
```

### 3. Build the extension

```bash
cd rust/radar_accel
maturin develop --release
cd ../..
```

### 4. Verify

```bash
python -c "import radar_accel; print('Rust accelerator loaded')"
```

If the import succeeds, Radar will automatically use it. Check the logs for:
```
INFO │ radar.data.earthquake │ Rust accelerator (radar_accel) loaded
```

---

## C Extension Setup (Optional)

The C extension (`radar_signal`) provides optimized signal smoothing for weather gauge animations.

### 1. Ensure a C compiler is available

**Windows:**
- Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- Or install MinGW-w64 via [MSYS2](https://www.msys2.org/)

**Linux:**
```bash
sudo apt install build-essential
```

### 2. Install cffi

```bash
pip install cffi
```

### 3. Build the extension

```bash
python c_ext/build_c.py
```

### 4. Verify

```bash
python -c "import _radar_signal; print('C signal module loaded')"
```

---

## Font Setup

Radar uses **JetBrains Mono** for its monospaced TUI aesthetic. The app works without it (uses a default font), but looks much better with it.

### Download JetBrains Mono

1. Visit [jetbrains.com/lp/mono](https://www.jetbrains.com/lp/mono/)
2. Download the TTF files
3. Place `JetBrainsMono-Regular.ttf` in `assets/fonts/`

```
Radar/
└── assets/
    └── fonts/
        └── JetBrainsMono-Regular.ttf
```

---

## Running in Development Mode

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run with debug logging
# Edit config.toml: log_level = "DEBUG"
python -m radar

# Run tests
pytest tests/ -v

# Type checking
mypy src/

# Linting
ruff check src/
```

---

## Packaging for Release

### Using PyInstaller

```bash
pip install pyinstaller

pyinstaller --name radar \
    --onedir \
    --add-data "themes:themes" \
    --add-data "config.toml:." \
    --add-data "assets:assets" \
    --hidden-import dearpygui \
    src/radar/__main__.py
```

### Using Nuitka

```bash
pip install nuitka

nuitka --standalone \
    --include-data-dir=themes=themes \
    --include-data-files=config.toml=config.toml \
    --include-data-dir=assets=assets \
    src/radar/__main__.py
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: dearpygui` | Run `pip install dearpygui` |
| Black window on startup | Ensure GPU drivers are up to date (DearPyGui uses GPU rendering) |
| No earthquake data | Check internet connection; USGS may have temporary outages |
| Font looks blurry | Place `JetBrainsMono-Regular.ttf` in `assets/fonts/` |
| Theme not loading | Check JSON syntax in your theme file |
| Rust build fails | Ensure `rustup` is installed and `rustc --version` works |
| C build fails | Ensure a C compiler is available (`gcc --version` or `cl`) |

---

## Platform Notes

### Windows

- DearPyGui requires Windows 10 or later
- Use PowerShell or Windows Terminal for best experience
- If using MinGW for C extension, ensure it's on your PATH

### Linux

- Install `libgl1-mesa-dev` if you get OpenGL errors:
  ```bash
  sudo apt install libgl1-mesa-dev libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev
  ```
- Wayland users: DearPyGui uses X11 — you may need XWayland
