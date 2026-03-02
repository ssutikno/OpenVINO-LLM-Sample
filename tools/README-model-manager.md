# OVMS Model Manager

A local Streamlit app to browse the Hugging Face OpenVINO model catalog, download models, register them in Open WebUI, and monitor the OVMS server — all from a single UI.

---

## Features

| Feature | Detail |
|---|---|
| **Model catalog** | Cached in SQLite (`tools/model_catalog_cache.db`), synced from Hugging Face on demand |
| **Category classification** | All 280+ models tagged with `pipeline_tag` (auto-inferred via architecture heuristics when Hugging Face does not supply one) |
| **Filterable/sortable table** | Built-in category dropdown, model name search, sortable columns, 25-row pagination |
| **Row colour coding** | 🟢 green = downloaded locally · 🔵 blue = registered in Open WebUI · 🟡 yellow = both |
| **Action multiselects** | Select models to Download / Remove / Register / Unregister — then click **Apply Actions** |
| **OVMS monitoring** | Live health indicator, loaded model list, Start / Stop / Restart controls |
| **Multi-model only** | OVMS always starts in multi-model mode via `start-ovms-multi.ps1` |
| **Auto-sync** | On load and after refresh, downloaded models are automatically registered in Open WebUI |

---

## Quick Start

### 1 — Install dependencies (once)

```powershell
.\.venv\Scripts\pip.exe install -r .\tools\requirements-model-manager.txt
```

### 2 — Launch the manager

```powershell
.\start-manager.ps1
```

Open **http://localhost:8501** in your browser.

> `start-manager.ps1` uses the project `.venv` virtual environment. If Streamlit is not found it prints the install command above and exits.

---

## Pages

### 📊 Dashboard

System overview at a glance:

- **Stat cards**: Available Models · Downloaded · Registered in Open WebUI · OVMS Status
- **System metrics**: RAM, VRAM, disk usage (requires `psutil`)
- **Live logs**: OVMS startup log + Open WebUI Docker log (last 10 lines each, auto-scrolled)

---

### 📦 Model Manager

Browse and manage the full OpenVINO model catalog.

#### Catalog Table

The table is rendered as an interactive HTML component with data embedded directly — no CDN dependencies.

| Column | Description |
|---|---|
| DL | Downloaded locally (✔ / –) |
| Reg | Registered in Open WebUI (✔ / –) |
| Model ID | Hugging Face model ID |
| Category | Pipeline tag badge (e.g. `text-generation`, `automatic-speech-recognition`) |
| Downloads | HF download count |
| Params | Parameter count |
| Size | File size on disk |
| Context | Max context length |
| License | Model license |
| Private | Private model flag |

**Table controls (built into the HTML table):**

- **Category** dropdown — filter by pipeline tag
- **Search** box — filter by model name (substring, case-insensitive)
- **Column headers** — click to sort ascending/descending
- **Pagination** — 25 rows per page with Prev / Next

#### Action Multiselects

Below the table, four multiselect dropdowns let you queue actions:

| Widget | Pool |
|---|---|
| ⬇ **Download to `models/`** | Models not yet downloaded |
| 🗑 **Remove downloaded** | Currently downloaded models |
| 📋 **Register in Open WebUI** | Downloaded but not yet registered |
| ❌ **Unregister** | Currently registered models |

Click **Apply Actions** to execute all queued operations.

#### Other Controls

| Button | Action |
|---|---|
| **Refresh OpenVINO Model List** | Syncs the local SQLite cache from Hugging Face, then reloads the catalog |

---

### ⚙️ Settings

| Setting | Default | Description |
|---|---|---|
| Models folder | `models/` | Local path where model folders are downloaded |
| OpenWebUI container | `open-webui` | Docker container name for Open WebUI |
| Max models to list | `0` (all) | Limit catalog size; 0 = no limit |
| HF token | _(empty)_ | Hugging Face access token for gated/private models |
| Sync full model details on refresh | ✔ | Also fetch parameters, size, context, and license from HF on refresh |
| Auto-sync downloaded models to Open WebUI | ✔ | Register any locally downloaded model that is missing from Open WebUI on startup and refresh |
| Restart Open WebUI after register/unregister | ✔ | Trigger `docker restart open-webui` so the model list updates immediately |

Click **Apply Settings** to persist changes for the current session.

---

## Pipeline Tag Categories

All catalog models carry a `pipeline_tag` category. When Hugging Face does not provide one, it is inferred from model architecture keywords:

| Category | Examples |
|---|---|
| `text-generation` | LLMs: GPT, Llama, Qwen, Phi, Mistral, DeepSeek, … |
| `image-text-to-text` | VLMs / multimodal: LLaVA, InternVL, Phi-Vision, … |
| `automatic-speech-recognition` | Whisper and similar ASR models |
| `text-to-image` | Stable Diffusion, FLUX, … |
| `feature-extraction` | Embedding / sentence-transformer models |
| `text-ranking` | Reranker / cross-encoder models |
| `text-classification` | Classifier models |

---

## OVMS — Multi-Model Mode

OVMS runs in **multi-model mode only**. There is no single-model override.

- **Start OVMS** calls `start-ovms-multi.ps1`, which:
  1. Scans `models/OpenVINO/` for valid model folders (must contain `openvino_model.xml` + `openvino_model.bin` or `openvino_model.bin.idx`)
  2. Auto-generates missing `graph.pbtxt` files
  3. Builds `ovms/multi-model-config.json`
  4. Launches the OVMS process on port `8000`
- Invalid model folders (missing required files) are **auto-skipped** with a warning; they do not block startup.
- The OVMS API is available at `http://localhost:8000/v3`.

---

## File Layout

```
project-root/
├── start-manager.ps1          # Launch script (uses .venv)
├── start-ovms-multi.ps1       # Start OVMS in multi-model mode
├── docker-compose.yml         # Open WebUI Docker service
├── models/
│   └── OpenVINO/              # Downloaded model folders live here
└── tools/
    ├── model_manager_app.py   # Streamlit app (this app)
    ├── model_catalog_cache.db # SQLite cache (auto-created)
    ├── requirements-model-manager.txt
    └── README-model-manager.md
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit >= 1.41` | Web UI framework |
| `requests >= 2.32` | HTTP calls to HF API and OVMS |
| `huggingface_hub >= 0.27` | Hugging Face Hub integration |

Install:

```powershell
.\.venv\Scripts\pip.exe install -r .\tools\requirements-model-manager.txt
```

---

## Open WebUI

Open WebUI runs in Docker and is configured in `docker-compose.yml`:

- **Port**: `3000` (host) → `8080` (container)
- **Backend**: `http://host.docker.internal:8000/v3` (points to native OVMS)
- **Data volume**: `open-webui` (persists chat history and model registration DB)

Start Open WebUI:

```powershell
docker compose up -d
```

Models registered via the Model Manager appear automatically in the Open WebUI model picker after the container restarts (handled automatically if **Restart Open WebUI after register/unregister** is enabled).
