import html
import json
import os
import re
import shutil
import sqlite3
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as st_components
from huggingface_hub import HfApi
from huggingface_hub import hf_hub_download
from huggingface_hub import snapshot_download


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = WORKSPACE_ROOT / "models"
DEFAULT_OPENWEBUI_CONTAINER = "open-webui"
START_OVMS_MULTI_SCRIPT = WORKSPACE_ROOT / "start-ovms-multi.ps1"
CACHE_DB_PATH = WORKSPACE_ROOT / "tools" / "model_catalog_cache.db"
HF_API = HfApi()
STATE_UNCHECKED = "☐"
STATE_WILL_APPLY = "✅"
STATE_ALREADY = "🟥✔"

# ── Model table HTML template — data injected at render time ────────────────
_TABLE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    padding: 6px 8px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 12.5px; background: transparent; color: #1f2937;
  }
  #toolbar {
    display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap;
  }
  #toolbar label { font-weight: 600; font-size: 12px; color: #374151; }
  #catFilter, #searchBox {
    padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 5px;
    font-size: 12px; background: #fff; color: #111827;
  }
  #catFilter { min-width: 180px; }
  #searchBox { min-width: 220px; }
  #infoLine { margin-left: auto; font-size: 11.5px; color: #6b7280; }
  #pager { display: flex; gap: 4px; align-items: center; margin-top: 6px; flex-wrap: wrap; }
  #pager button {
    padding: 2px 8px; font-size: 11.5px; border: 1px solid #d1d5db;
    border-radius: 4px; background: #fff; cursor: pointer; color: #374151;
  }
  #pager button:hover { background: #f3f4f6; }
  #pager button.active { background: #2563eb; color: #fff; border-color: #2563eb; }
  #pager button:disabled { opacity: .4; cursor: default; }
  #pgInfo { font-size: 11.5px; color: #6b7280; margin-left: 4px; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  thead th {
    background: #f3f4f6; color: #374151; font-size: 12px;
    padding: 5px 7px; border-bottom: 2px solid #e5e7eb;
    white-space: nowrap; cursor: pointer; user-select: none;
    overflow: hidden; text-overflow: ellipsis;
  }
  thead th:hover { background: #e5e7eb; }
  thead th.sort-asc::after  { content: " \u25b4"; color: #2563eb; }
  thead th.sort-desc::after { content: " \u25be"; color: #2563eb; }
  tbody td {
    padding: 4px 7px; border-bottom: 1px solid #f0f0f0;
    vertical-align: middle; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap;
  }
  tbody tr:hover td { background: #f9fafb !important; }
  tr.dl-row td   { background: #f0fdf4; }
  tr.reg-row td  { background: #eff6ff; }
  tr.both-row td { background: #fefce8; }
  .mid { font-family: monospace; font-size: 11px; color: #1d4ed8; white-space: normal; word-break: break-all; }
  .badge {
    display: inline-block; padding: 1px 7px; border-radius: 999px;
    font-size: 10.5px; font-weight: 600; white-space: nowrap;
  }
  .b-tg   { background:#dbeafe; color:#1e40af; }
  .b-asr  { background:#ede9fe; color:#5b21b6; }
  .b-vl   { background:#dcfce7; color:#15803d; }
  .b-t2i  { background:#ffedd5; color:#c2410c; }
  .b-emb  { background:#f3f4f6; color:#374151; }
  .b-rank { background:#ccfbf1; color:#0f766e; }
  .b-cls  { background:#fce7f3; color:#9d174d; }
  .b-unk  { background:#f3f4f6; color:#6b7280; }
  .chk { width: 15px; height: 15px; cursor: pointer; accent-color: #2563eb; }
  td.priv-y { color: #dc2626; font-weight: 600; text-align: center; }
  td.priv-n { color: #9ca3af; text-align: center; }
  th.col-chk { width: 36px; text-align: center; }
  th.col-cat { width: 110px; }
  th.col-dls { width: 70px; }
  th.col-par { width: 70px; }
  th.col-sz  { width: 80px; }
  th.col-ctx { width: 70px; }
  th.col-lic { width: 90px; }
  th.col-prv { width: 36px; text-align: center; }
</style>
</head>
<body>
<div id="toolbar">
  <label for="catFilter">Category:</label>
  <select id="catFilter"><option value="">All</option></select>
  <label for="searchBox">Search:</label>
  <input id="searchBox" type="text" placeholder="model name\u2026">
  <span id="infoLine"></span>
</div>
<table>
  <thead><tr>
    <th class="col-chk" data-col="0" title="Download">\u2b07</th>
    <th class="col-chk" data-col="1" title="Register">\U0001F4CB</th>
    <th data-col="2">Model</th>
    <th class="col-cat" data-col="3">Category</th>
    <th class="col-dls" data-col="4">DLs</th>
    <th class="col-par" data-col="5">Params</th>
    <th class="col-sz"  data-col="6">Size</th>
    <th class="col-ctx" data-col="7">Context</th>
    <th class="col-lic" data-col="8">License</th>
    <th class="col-prv" data-col="9">Prv</th>
  </tr></thead>
  <tbody id="tbody"></tbody>
</table>
<div id="pager"></div>

<script>
const BADGE = {
  "text-generation":              ["b-tg",   "text-gen"],
  "automatic-speech-recognition": ["b-asr",  "asr"],
  "image-text-to-text":           ["b-vl",   "vision-LM"],
  "text-to-image":                ["b-t2i",  "text\u2192img"],
  "feature-extraction":           ["b-emb",  "embedding"],
  "text-ranking":                 ["b-rank", "reranker"],
  "text-classification":          ["b-cls",  "cls"],
};

const PAGE_SIZE = 25;
let allRows = [];
let filtered = [];
let dlState  = {};
let regState = {};
let sortCol  = 4;
let sortAsc  = false;
let page     = 0;
let catFilter = "";
let textFilter = "";

function pushState() {
  const dl  = Object.keys(dlState).filter(k => dlState[k]);
  const reg = Object.keys(regState).filter(k => regState[k]);
  window.parent.postMessage({
    type: "streamlit:setComponentValue",
    value: { download: dl, register: reg },
    dataType: "json"
  }, "*");
}

function syncHeight() {
  window.parent.postMessage({
    type: "streamlit:setFrameHeight",
    height: document.body.scrollHeight + 24
  }, "*");
}

function badgeHtml(cat) {
  const [cls, lbl] = BADGE[cat] || ["b-unk", cat || "unknown"];
  return '<span class="badge ' + cls + '">' + lbl + '</span>';
}

function cmpVal(r, col) {
  switch (col) {
    case 0: return dlState[r.id]  ? 1 : 0;
    case 1: return regState[r.id] ? 1 : 0;
    case 2: return r.id;
    case 3: return r.category || "";
    case 4: return r.downloads || 0;
    case 5: return r.parameters || "";
    case 6: return r.file_size  || "";
    case 7: return r.max_context || "";
    case 8: return r.license || "";
    case 9: return r.private ? 1 : 0;
    default: return "";
  }
}

function applyFilters() {
  const catLo  = catFilter.toLowerCase();
  const textLo = textFilter.toLowerCase();
  filtered = allRows.filter(r => {
    if (catLo  && (r.category || "unknown").toLowerCase() !== catLo) return false;
    if (textLo && !r.id.toLowerCase().includes(textLo)) return false;
    return true;
  });
  filtered.sort((a, b) => {
    const av = cmpVal(a, sortCol), bv = cmpVal(b, sortCol);
    const c = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? c : -c;
  });
  page = 0;
}

function rowClass(id) {
  const d = !!dlState[id], r = !!regState[id];
  if (d && r) return "both-row";
  if (d) return "dl-row";
  if (r) return "reg-row";
  return "";
}

function renderTable() {
  const tbody = document.getElementById("tbody");
  const start = page * PAGE_SIZE;
  const slice = filtered.slice(start, start + PAGE_SIZE);
  const html = [];
  slice.forEach(r => {
    const cls = rowClass(r.id);
    html.push('<tr class="' + cls + '">');
    html.push('<td class="col-chk" style="text-align:center"><input type="checkbox" class="chk dl-chk" data-id="' + r.id + '"' + (dlState[r.id]  ? " checked" : "") + '></td>');
    html.push('<td class="col-chk" style="text-align:center"><input type="checkbox" class="chk reg-chk" data-id="' + r.id + '"' + (regState[r.id] ? " checked" : "") + '></td>');
    html.push('<td><span class="mid">' + r.id + '</span></td>');
    html.push('<td>' + badgeHtml(r.category || "Unknown") + '</td>');
    html.push('<td>' + Number(r.downloads || 0).toLocaleString() + '</td>');
    html.push('<td>' + (r.parameters  || "\u2014") + '</td>');
    html.push('<td>' + (r.file_size   || "\u2014") + '</td>');
    html.push('<td>' + (r.max_context || "\u2014") + '</td>');
    html.push('<td>' + (r.license     || "\u2014") + '</td>');
    html.push(r.private
      ? '<td class="priv-y">\U0001F512</td>'
      : '<td class="priv-n">\u25cb</td>');
    html.push('</tr>');
  });
  tbody.innerHTML = html.join("");

  // checkboxes
  tbody.querySelectorAll(".dl-chk").forEach(cb => {
    cb.addEventListener("change", function() {
      dlState[this.dataset.id] = this.checked;
      refreshRow(this.closest("tr"), this.dataset.id);
      pushState();
    });
  });
  tbody.querySelectorAll(".reg-chk").forEach(cb => {
    cb.addEventListener("change", function() {
      regState[this.dataset.id] = this.checked;
      refreshRow(this.closest("tr"), this.dataset.id);
      pushState();
    });
  });

  renderPager();
  updateInfo();
  syncHeight();
}

function refreshRow(tr, id) {
  tr.className = rowClass(id);
}

function renderPager() {
  const total = filtered.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pager = document.getElementById("pager");
  const html = [];
  html.push('<button id="pgPrev" ' + (page === 0 ? "disabled" : "") + '>&laquo; Prev</button>');
  const lo = Math.max(0, page - 3), hi = Math.min(pages - 1, page + 3);
  if (lo > 0) html.push('<button data-pg="0">1</button><span>\u2026</span>');
  for (let i = lo; i <= hi; i++) {
    html.push('<button data-pg="' + i + '"' + (i === page ? ' class="active"' : '') + '>' + (i+1) + '</button>');
  }
  if (hi < pages - 1) html.push('<span>\u2026</span><button data-pg="' + (pages-1) + '">' + pages + '</button>');
  html.push('<button id="pgNext" ' + (page >= pages-1 ? "disabled" : "") + '>Next &raquo;</button>');
  html.push('<span id="pgInfo">Page ' + (page+1) + ' / ' + pages + '</span>');
  pager.innerHTML = html.join("");
  pager.querySelectorAll("button[data-pg]").forEach(b => {
    b.addEventListener("click", () => { page = +b.dataset.pg; renderTable(); });
  });
  const prev = document.getElementById("pgPrev");
  const next = document.getElementById("pgNext");
  if (prev) prev.addEventListener("click", () => { if (page > 0) { page--; renderTable(); } });
  if (next) next.addEventListener("click", () => { if (page < pages-1) { page++; renderTable(); } });
}

function updateInfo() {
  const start = page * PAGE_SIZE + 1;
  const end   = Math.min((page + 1) * PAGE_SIZE, filtered.length);
  const el    = document.getElementById("infoLine");
  if (filtered.length === 0) { el.textContent = "No models"; return; }
  el.textContent = start + "\u2013" + end + " of " + filtered.length +
    (filtered.length !== allRows.length ? " (filtered from " + allRows.length + ")" : "");
}

function updateSortHeaders() {
  document.querySelectorAll("thead th").forEach(th => {
    th.classList.remove("sort-asc", "sort-desc");
    if (+th.dataset.col === sortCol) {
      th.classList.add(sortAsc ? "sort-asc" : "sort-desc");
    }
  });
}

function initCatFilter(rows) {
  const cats = [...new Set(rows.map(r => r.category || "Unknown"))].sort();
  const sel  = document.getElementById("catFilter");
  sel.innerHTML = '<option value="">All</option>' +
    cats.map(c => '<option value="' + c + '">' + c + '</option>').join("");
  sel.value = catFilter;
}

function buildTable(rows) {
  rows.forEach(r => {
    if (!(r.id in dlState))  dlState[r.id]  = !!r.downloaded;
    if (!(r.id in regState)) regState[r.id] = !!r.registered;
  });
  allRows = rows;
  initCatFilter(rows);
  applyFilters();
  updateSortHeaders();
  renderTable();
  pushState();
}

// ── Sort header clicks ─────────────────────────────────────────────────────
document.querySelectorAll("thead th[data-col]").forEach(th => {
  th.addEventListener("click", () => {
    const c = +th.dataset.col;
    if (c === 0 || c === 1) return;   // checkboxes not sortable this way
    if (sortCol === c) sortAsc = !sortAsc;
    else { sortCol = c; sortAsc = c === 2 || c === 3; }
    applyFilters();
    updateSortHeaders();
    renderTable();
  });
});

// ── Filters ────────────────────────────────────────────────────────────────
document.getElementById("catFilter").addEventListener("change", function() {
  catFilter = this.value.toLowerCase();
  applyFilters(); renderTable();
});
document.getElementById("searchBox").addEventListener("input", function() {
  textFilter = this.value;
  applyFilters(); renderTable();
});

// Data embedded directly — no message passing needed
buildTable(%%ROWS_JSON%%);
</script>
</body>
</html>
"""


def _build_table_html(rows: list) -> str:
    import json as _json
    safe = _json.dumps(rows, ensure_ascii=True)
    return _TABLE_HTML_TEMPLATE.replace("%%ROWS_JSON%%", safe)



def _format_size_bytes(size_bytes: int | None) -> str:
    if not size_bytes or size_bytes <= 0:
        return "Unknown"
    gib = size_bytes / (1024**3)
    return f"{gib:.2f} GiB"


def _guess_params_label(model_id: str, tags: list[str], card_data: dict | None) -> str:
    if card_data:
        for key in ["parameters", "params", "model_parameters"]:
            value = card_data.get(key)
            if value:
                return str(value)

    search_space = [model_id] + tags
    for token in search_space:
        token_l = token.lower()
        for suffix in ["b", "m"]:
            marker = f"{suffix}"
            idx = token_l.find(marker)
            if idx > 0:
                candidate = token_l[: idx + 1].split("-")[-1].split("_")[-1]
                if candidate[:-1].replace(".", "", 1).isdigit():
                    return candidate.upper()
    return "Unknown"


def _extract_context_length(info, model_id: str) -> str:
    candidates = []
    config = getattr(info, "config", None)
    card_data = getattr(info, "cardData", None)

    if isinstance(config, dict):
        for key in ["max_position_embeddings", "n_positions", "max_sequence_length", "seq_length"]:
            value = config.get(key)
            if isinstance(value, int) and value > 0:
                candidates.append(value)

    if isinstance(card_data, dict):
        for key in ["context_length", "max_context_length", "max_position_embeddings"]:
            value = card_data.get(key)
            if isinstance(value, int) and value > 0:
                candidates.append(value)

    if not candidates:
        keys = {
            "max_position_embeddings",
            "n_positions",
            "max_sequence_length",
            "seq_length",
            "context_length",
            "model_max_length",
            "max_model_input_sizes",
        }
        for file_name in ["config.json", "tokenizer_config.json", "generation_config.json", "openvino_config.json"]:
            try:
                local_file = hf_hub_download(repo_id=model_id, filename=file_name)
                with open(local_file, "r", encoding="utf-8") as file_obj:
                    content = json.load(file_obj)

                stack = [content]
                while stack:
                    current = stack.pop()
                    if isinstance(current, dict):
                        for key, value in current.items():
                            if key in keys:
                                if isinstance(value, int) and value > 0:
                                    candidates.append(value)
                                elif isinstance(value, dict):
                                    for nested_value in value.values():
                                        if isinstance(nested_value, int) and nested_value > 0:
                                            candidates.append(nested_value)
                            if isinstance(value, (dict, list)):
                                stack.append(value)
                    elif isinstance(current, list):
                        stack.extend(current)
            except Exception:
                continue

    return str(max(candidates)) if candidates else "Unknown"


# ── Model task-category inference ─────────────────────────────────────────────
_LLM_ARCH_TAGS = {
    "qwen2", "qwen3", "llama", "llama2", "llama3", "mistral", "phi3",
    "phi4", "gemma", "gemma2", "gemma3", "deepseek", "gpt2", "gptj",
    "gpt_neox", "internlm", "falcon", "bloom", "bloomz", "stablelm",
    "starcoder", "starcoder2", "codellama", "codegen", "mpt",
}
_ASR_NAME_HINTS = {"whisper", "wav2vec", "hubert", "parakeet", "canary"}
_VLM_NAME_HINTS = {"llava", "internvl", "minicpm", "moondream"}
_TEXT_TO_IMAGE_HINTS = {"stable-diffusion", "lcm_dreamshaper", "lcm-dreamshaper", "dreamshaper", "sdxl", "sd-"}
_RERANKER_HINTS = {"reranker", "rerank"}
_EMBEDDING_HINTS = {"bge-base", "bge-large", "bge-small", "bge-m3", "e5-", "nomic-embed", "gte-"}
_TEXT_CLASSIFICATION_HINTS = {"sst2", "sst-2", "-nli", "sentiment", "-cls", "classifier"}


def _infer_pipeline_tag(model_id: str, tags: list[str]) -> str | None:
    """Derive a pipeline_tag from model name and HF tag list when HF doesn't set one."""
    name = model_id.lower()
    tag_set = {t.lower() for t in tags}

    # 1. Explicit pipeline-tag values already in the tag list
    for known in (
        "text-generation", "automatic-speech-recognition",
        "image-text-to-text", "text-to-image",
        "feature-extraction", "text-ranking", "text-classification",
    ):
        if known in tag_set:
            return known
    if "conversational" in tag_set or "text2text-generation" in tag_set:
        return "text-generation"

    # 2. Architecture tags that HF sets when pipeline_tag is absent
    if tag_set & _LLM_ARCH_TAGS:
        if any(kw in name or kw in tag_set for kw in _VLM_NAME_HINTS):
            return "image-text-to-text"
        return "text-generation"

    # 3. Model-name heuristics (most specific first)
    if any(kw in name for kw in _RERANKER_HINTS):
        return "text-ranking"
    if any(kw in name for kw in _EMBEDDING_HINTS):
        return "feature-extraction"
    if any(kw in name for kw in _TEXT_CLASSIFICATION_HINTS):
        return "text-classification"
    if any(kw in name for kw in _TEXT_TO_IMAGE_HINTS):
        return "text-to-image"
    for kw in _ASR_NAME_HINTS:
        if kw in name:
            return "automatic-speech-recognition"
    for kw in _VLM_NAME_HINTS:
        if kw in name:
            return "image-text-to-text"

    return None


@st.cache_data(show_spinner=False)
def get_model_details(model_id: str) -> dict:
    info = HF_API.model_info(repo_id=model_id, files_metadata=True)
    tags = list(getattr(info, "tags", []) or [])
    card_data = getattr(info, "cardData", None)
    siblings = getattr(info, "siblings", []) or []

    total_size = 0
    for file_item in siblings:
        size = getattr(file_item, "size", None)
        if isinstance(size, int) and size > 0:
            total_size += size

    hf_pipeline_tag = getattr(info, "pipeline_tag", None) or None
    resolved_tag = hf_pipeline_tag or _infer_pipeline_tag(model_id, tags)

    return {
        "id": model_id,
        "parameters": _guess_params_label(model_id, tags, card_data if isinstance(card_data, dict) else None),
        "file_size": _format_size_bytes(total_size),
        "max_context": _extract_context_length(info, model_id),
        "license": str(getattr(info, "license", None) or (card_data or {}).get("license") or "Unknown"),
        "pipeline_tag": resolved_tag,
        "tags": ", ".join(tags[:8]) if tags else "",
    }


def list_openvino_models(limit: int) -> list[dict]:
    params = {
        "author": "OpenVINO",
        "sort": "downloads",
        "direction": "-1",
    }
    if limit and limit > 0:
        params["limit"] = str(limit)
    response = requests.get(
        "https://huggingface.co/api/models",
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    models = []
    for item in response.json():
        model_id = item.get("id", "")
        if not model_id.endswith("-ov"):
            continue
        raw_tags = list(item.get("tags") or [])
        api_pipeline_tag = item.get("pipeline_tag") or None
        resolved_tag = api_pipeline_tag or _infer_pipeline_tag(model_id, raw_tags)
        models.append(
            {
                "id": model_id,
                "downloads": item.get("downloads", 0),
                "updated": item.get("lastModified", ""),
                "private": item.get("private", False),
                "pipeline_tag": resolved_tag,
                "tags": ", ".join(raw_tags[:8]) if raw_tags else "",
            }
        )
    return models


def init_cache_db() -> None:
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS model_cache (
                id TEXT PRIMARY KEY,
                downloads INTEGER,
                updated TEXT,
                private INTEGER,
                parameters TEXT,
                file_size TEXT,
                max_context TEXT,
                license TEXT,
                pipeline_tag TEXT,
                tags TEXT,
                synced_at INTEGER
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def backfill_pipeline_tags() -> int:
    """Re-infer pipeline_tag for cached rows where it is NULL, empty, or 'Unknown'."""
    if not CACHE_DB_PATH.exists():
        return 0
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tags FROM model_cache "
            "WHERE pipeline_tag IS NULL OR pipeline_tag = '' OR pipeline_tag = 'Unknown'"
        )
        rows = cursor.fetchall()
        updated = 0
        for model_id, tags_str in rows:
            tag_list = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
            inferred = _infer_pipeline_tag(model_id, tag_list)
            if inferred:
                cursor.execute(
                    "UPDATE model_cache SET pipeline_tag = ? WHERE id = ?",
                    (inferred, model_id),
                )
                updated += 1
        conn.commit()
        return updated
    finally:
        conn.close()


def sync_cache_from_hf(
    limit: int,
    include_details: bool,
    progress_callback=None,  # callable(current, total, model_id) or None
) -> int:
    init_cache_db()

    # ── Step 1: fetch model list ───────────────────────────────────────────
    if progress_callback:
        progress_callback(0, 1, "Fetching model list from Hugging Face…")
    models = list_openvino_models(limit)
    total = len(models)
    synced_at = int(time.time())

    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        cursor = conn.cursor()

        # ── Step 2: upsert each model ──────────────────────────────────────
        for idx, model in enumerate(models):
            model_id = model["id"]

            if progress_callback:
                progress_callback(idx, total, model_id)

            details = {}
            if include_details:
                try:
                    details = get_model_details(model_id)
                except Exception:
                    details = {}

            # Resolve pipeline_tag: prefer details (full API), fall back to list-API value.
            # Never store "Unknown" — use None so COALESCE works correctly.
            _det_tag = details.get("pipeline_tag")
            _list_tag = model.get("pipeline_tag")
            _final_tag = (_det_tag if _det_tag and _det_tag != "Unknown" else None) or _list_tag or None
            _final_tags = details.get("tags") or model.get("tags") or None

            cursor.execute(
                """
                INSERT INTO model_cache (id, downloads, updated, private, parameters, file_size, max_context, license, pipeline_tag, tags, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    downloads=excluded.downloads,
                    updated=excluded.updated,
                    private=excluded.private,
                    synced_at=excluded.synced_at,
                    parameters=COALESCE(excluded.parameters, model_cache.parameters),
                    file_size=COALESCE(excluded.file_size, model_cache.file_size),
                    max_context=COALESCE(excluded.max_context, model_cache.max_context),
                    license=COALESCE(excluded.license, model_cache.license),
                    pipeline_tag=COALESCE(excluded.pipeline_tag,
                        CASE WHEN model_cache.pipeline_tag IN ('', 'Unknown') THEN NULL ELSE model_cache.pipeline_tag END),
                    tags=COALESCE(excluded.tags, model_cache.tags)
                """,
                (
                    model_id,
                    int(model.get("downloads", 0) or 0),
                    str(model.get("updated", "") or ""),
                    1 if model.get("private", False) else 0,
                    details.get("parameters"),
                    details.get("file_size"),
                    details.get("max_context"),
                    details.get("license"),
                    _final_tag,
                    _final_tags,
                    synced_at,
                ),
            )

        conn.commit()

        if progress_callback:
            progress_callback(total, total, "Done")
    finally:
        conn.close()

    backfill_pipeline_tags()
    return total


def load_cached_models(limit: int) -> list[dict]:
    init_cache_db()
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        cursor = conn.cursor()
        if limit and limit > 0:
            cursor.execute(
                """
                SELECT id, downloads, updated, private, parameters, file_size, max_context, license, pipeline_tag, tags
                FROM model_cache
                ORDER BY downloads DESC, id ASC
                LIMIT ?
                """,
                (int(limit),),
            )
        else:
            cursor.execute(
                """
                SELECT id, downloads, updated, private, parameters, file_size, max_context, license, pipeline_tag, tags
                FROM model_cache
                ORDER BY downloads DESC, id ASC
                """
            )
        rows = cursor.fetchall()

        models = []
        for row in rows:
            models.append(
                {
                    "id": row[0],
                    "downloads": int(row[1] or 0),
                    "updated": row[2] or "",
                    "private": bool(row[3]),
                    "parameters": row[4] or "Unknown",
                    "file_size": row[5] or "Unknown",
                    "max_context": row[6] or "Unknown",
                    "license": row[7] or "Unknown",
                    "pipeline_tag": row[8] or "Unknown",
                    "tags": row[9] or "",
                }
            )
        return models
    finally:
        conn.close()


def download_model(model_id: str, models_dir: Path, hf_token: str | None) -> Path:
    target_dir = models_dir.joinpath(*model_id.split("/"))
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=model_id,
        local_dir=str(target_dir),
        token=hf_token or None,
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    return target_dir


def is_model_downloaded(model_id: str, models_dir: Path) -> bool:
    target_dir = models_dir.joinpath(*model_id.split("/"))
    return target_dir.exists() and target_dir.is_dir() and any(target_dir.iterdir())


def get_downloaded_model_ids(catalog: list[dict], models_dir: Path) -> list[str]:
    downloaded = []
    for item in catalog:
        model_id = item.get("id")
        if model_id and is_model_downloaded(model_id, models_dir):
            downloaded.append(model_id)
    return downloaded


def get_downloaded_model_ids_from_fs(models_dir: Path) -> list[str]:
    downloaded: list[str] = []
    if not models_dir.exists() or not models_dir.is_dir():
        return downloaded

    for org_dir in models_dir.iterdir():
        if not org_dir.is_dir():
            continue
        for model_dir in org_dir.iterdir():
            if not model_dir.is_dir():
                continue
            try:
                has_content = any(model_dir.iterdir())
            except Exception:
                has_content = False
            if has_content:
                downloaded.append(f"{org_dir.name}/{model_dir.name}")

    return sorted(set(downloaded))


def is_model_valid_for_ovms(model_id: str, models_dir: Path) -> tuple[bool, str]:
    model_path = models_dir.joinpath(*model_id.split("/"))
    if not model_path.exists() or not model_path.is_dir():
        return False, "model folder not found"

    xml_path = model_path / "openvino_model.xml"
    bin_path = model_path / "openvino_model.bin"
    if not xml_path.exists():
        return False, "openvino_model.xml missing"
    if not bin_path.exists():
        return False, "openvino_model.bin missing"

    return True, ""


def split_valid_invalid_models(model_ids: list[str], models_dir: Path) -> tuple[list[str], list[tuple[str, str]]]:
    valid: list[str] = []
    invalid: list[tuple[str, str]] = []
    for model_id in model_ids:
        ok, reason = is_model_valid_for_ovms(model_id, models_dir)
        if ok:
            valid.append(model_id)
        else:
            invalid.append((model_id, reason))
    return valid, invalid


def sync_downloaded_models_to_openwebui(catalog: list[dict], models_dir: Path, container_name: str) -> tuple[int, list[str]]:
    downloaded = get_downloaded_model_ids(catalog, models_dir)
    if not downloaded:
        return 0, []

    registered = get_registered_model_ids(container_name)
    missing = [model_id for model_id in downloaded if model_id not in registered]
    if not missing:
        return 0, []

    register_models_in_openwebui(missing, container_name)
    return len(missing), missing


def sync_downloaded_models_from_fs_to_openwebui(models_dir: Path, container_name: str) -> tuple[int, list[str]]:
    downloaded = get_downloaded_model_ids_from_fs(models_dir)
    if not downloaded:
        return 0, []

    registered = get_registered_model_ids(container_name)
    missing = [model_id for model_id in downloaded if model_id not in registered]
    if not missing:
        return 0, []

    register_models_in_openwebui(missing, container_name)
    return len(missing), missing


def remove_downloaded_model(model_id: str, models_dir: Path) -> bool:
    target_dir = models_dir.joinpath(*model_id.split("/"))
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        return True
    return False


def _register_in_db(db_path: Path, model_ids: list[str]) -> tuple[int, int]:
    now_ts = int(time.time())
    added_model_rows = 0

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM user")
        user_ids = [row[0] for row in cursor.fetchall()]
        if not user_ids:
            raise RuntimeError("No OpenWebUI users found in database.")

        cursor.execute("PRAGMA table_info(model)")
        model_columns = [row[1] for row in cursor.fetchall()]
        if not model_columns:
            raise RuntimeError("OpenWebUI table 'model' not found.")

        for model_id in model_ids:
            for user_id in user_ids:
                cursor.execute("SELECT COUNT(1) FROM model WHERE id = ?", (model_id,))
                exists = cursor.fetchone()[0] > 0

                if exists:
                    cursor.execute(
                        "UPDATE model SET user_id = ?, name = ?, updated_at = ?, is_active = 1 WHERE id = ?",
                        (user_id, model_id, now_ts, model_id),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (model_id, user_id, None, model_id, "{}", "{}", now_ts, now_ts, 1),
                    )
                    added_model_rows += 1

        for user_id in user_ids:
            cursor.execute("SELECT settings FROM user WHERE id = ?", (user_id,))
            raw_settings = cursor.fetchone()[0]
            settings = json.loads(raw_settings) if raw_settings else {}

            ui_settings = settings.setdefault("ui", {})
            current_models = ui_settings.get("models", [])
            if not isinstance(current_models, list):
                current_models = []

            deduped = []
            for model_id in current_models + model_ids:
                if model_id not in deduped:
                    deduped.append(model_id)

            ui_settings["models"] = deduped
            cursor.execute("UPDATE user SET settings = ? WHERE id = ?", (json.dumps(settings), user_id))

        conn.commit()
        return added_model_rows, len(user_ids)
    finally:
        conn.close()


def register_models_in_openwebui(model_ids: list[str], container_name: str) -> tuple[int, int]:
    last_error = None
    for attempt in range(1, 4):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                local_db = Path(tmp_dir) / "webui.db"
                db_in_container = f"{container_name}:/app/backend/data/webui.db"

                subprocess.run(["docker", "cp", db_in_container, str(local_db)], check=True)
                added_model_rows, user_count = _register_in_db(local_db, model_ids)
                subprocess.run(["docker", "cp", str(local_db), db_in_container], check=True)

            registered = get_registered_model_ids(container_name)
            missing = [model_id for model_id in model_ids if model_id not in registered]
            if missing:
                raise RuntimeError(f"Post-register verification failed for: {missing}")

            return added_model_rows, user_count
        except Exception as error:
            last_error = error
            time.sleep(1.2 * attempt)

    raise RuntimeError(f"OpenWebUI register failed after retries: {last_error}")


def _unregister_in_db(db_path: Path, model_ids: list[str]) -> tuple[int, int]:
    removed_model_rows = 0

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        for model_id in model_ids:
            cursor.execute("SELECT COUNT(1) FROM model WHERE id = ?", (model_id,))
            existing = cursor.fetchone()[0]
            if existing:
                removed_model_rows += existing
            cursor.execute("DELETE FROM model WHERE id = ?", (model_id,))

        cursor.execute("SELECT id, settings FROM user")
        users = cursor.fetchall()
        touched_users = 0

        for user_id, raw_settings in users:
            if not raw_settings:
                continue
            try:
                settings = json.loads(raw_settings)
            except json.JSONDecodeError:
                continue

            ui_settings = settings.setdefault("ui", {})
            current_models = ui_settings.get("models", [])
            if not isinstance(current_models, list):
                continue

            filtered_models = [mid for mid in current_models if mid not in model_ids]
            if filtered_models != current_models:
                ui_settings["models"] = filtered_models
                cursor.execute("UPDATE user SET settings = ? WHERE id = ?", (json.dumps(settings), user_id))
                touched_users += 1

        conn.commit()
        return removed_model_rows, touched_users
    finally:
        conn.close()


def unregister_models_in_openwebui(model_ids: list[str], container_name: str) -> tuple[int, int]:
    last_error = None
    for attempt in range(1, 4):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                local_db = Path(tmp_dir) / "webui.db"
                db_in_container = f"{container_name}:/app/backend/data/webui.db"

                subprocess.run(["docker", "cp", db_in_container, str(local_db)], check=True)
                removed_rows, touched_users = _unregister_in_db(local_db, model_ids)
                subprocess.run(["docker", "cp", str(local_db), db_in_container], check=True)

            # Non-fatal verification — OpenWebUI may cache models from OVMS API
            # independently of the DB model table, so a mismatch is just a warning.
            try:
                registered = get_registered_model_ids(container_name)
                still_present = [mid for mid in model_ids if mid in registered]
                if still_present:
                    pass  # DB was updated; residual entries may be from OVMS discovery
            except Exception:
                pass

            return removed_rows, touched_users
        except Exception as error:
            last_error = error
            time.sleep(1.2 * attempt)

    raise RuntimeError(f"OpenWebUI unregister failed after retries: {last_error}")


def get_registered_model_ids(container_name: str) -> set[str]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_db = Path(tmp_dir) / "webui.db"
        db_in_container = f"{container_name}:/app/backend/data/webui.db"
        subprocess.run(["docker", "cp", db_in_container, str(local_db)], check=True)

        conn = sqlite3.connect(local_db)
        try:
            cursor = conn.cursor()
            registered = set()

            cursor.execute("SELECT id FROM model")
            registered.update(str(row[0]) for row in cursor.fetchall() if row and row[0])

            cursor.execute("SELECT settings FROM user")
            for (raw_settings,) in cursor.fetchall():
                if not raw_settings:
                    continue
                try:
                    settings = json.loads(raw_settings)
                    ui_models = settings.get("ui", {}).get("models", [])
                    if isinstance(ui_models, list):
                        registered.update(str(model_id) for model_id in ui_models if model_id)
                except json.JSONDecodeError:
                    continue

            return registered
        finally:
            conn.close()


def stop_ovms() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "ovms.exe"], check=False, capture_output=True, text=True)


OVMS_LOG_PATH = WORKSPACE_ROOT / "ovms_startup.log"


def start_ovms_multi_with_models(model_ids: list[str]) -> None:
    if not START_OVMS_MULTI_SCRIPT.exists():
        raise RuntimeError(f"start-ovms-multi.ps1 not found at {START_OVMS_MULTI_SCRIPT}")
    if not model_ids:
        raise RuntimeError("No models provided for OVMS multi start.")

    env = os.environ.copy()
    env["MODEL_IDS"] = ",".join(model_ids)

    # Use CREATE_NEW_PROCESS_GROUP only (not DETACHED_PROCESS) so that the
    # child PowerShell can inherit the console-free environment without failing,
    # and redirect output to a log file for diagnostics.
    create_new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)

    log_handle = open(OVMS_LOG_PATH, "w", encoding="utf-8", errors="replace")
    subprocess.Popen(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(START_OVMS_MULTI_SCRIPT)],
        cwd=str(WORKSPACE_ROOT),
        env=env,
        creationflags=create_new_group,
        stdout=log_handle,
        stderr=log_handle,
    )


def is_port_open(host: str, port: int, timeout_sec: float = 0.4) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_sec)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def get_ovms_process_count() -> int:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq ovms.exe", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return 0
    if len(lines) == 1 and lines[0].startswith("INFO:"):
        return 0
    return len(lines)


def get_ovms_loaded_models() -> list[str]:
    try:
        response = requests.get("http://localhost:8000/v3/models", timeout=1.5)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        model_ids = []
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
        return model_ids
    except Exception:
        return []


@st.cache_data(ttl=4)
def get_ovms_status() -> dict:
    process_count = get_ovms_process_count()
    port_open = is_port_open("127.0.0.1", 8000)
    loaded_models = get_ovms_loaded_models()
    api_ready = len(loaded_models) > 0
    running = process_count > 0

    if api_ready:
        state = "healthy"
    elif running or port_open:
        state = "starting"
    else:
        state = "stopped"

    return {
        "state": state,
        "process_count": process_count,
        "port_open": port_open,
        "loaded_models": loaded_models,
    }


def wait_for_ovms_ready(timeout_sec: int = 120) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            response = requests.get("http://localhost:8000/v3/models", timeout=5)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False


def _parse_ovms_log(log_path: Path) -> dict:
    """Parse ovms_startup.log and return structured startup milestones."""
    empty = {"graphs": [], "available": [], "server_listening": False, "last_line": ""}
    if not log_path.exists():
        return empty
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        graphs: list[str] = []
        for ln in lines:
            if "Graph: graph.pbtxt created in:" in ln:
                path_part = ln.split("Graph: graph.pbtxt created in:")[-1].strip()
                graphs.append(Path(path_part).name)
        available: list[str] = []
        for ln in lines:
            m = re.search(r"Mediapipe:\s+(\S+)\s+state changed to: AVAILABLE", ln)
            if m:
                available.append(m.group(1).split("/")[-1])
        server_listening = "REST server listening on port 8000" in text
        last_line = lines[-1] if lines else ""
        return {"graphs": graphs, "available": available,
                "server_listening": server_listening, "last_line": last_line}
    except Exception:
        return empty


def wait_for_ovms_ready_with_progress(
    expected_models: int,
    timeout_sec: int = 300,
) -> tuple[bool, int]:
    """Drive a progress bar by parsing ovms_startup.log milestones.

    Progress allocation
    ───────────────────
    0 – 2 %   launcher starting  (no log output yet)
    2 – 45 %  graph / pull phase (1 step per model × graphs_done/expected)
    45 – 50 % server booting     (REST server listening line seen)
    50 – 100% models AVAILABLE   (1 step per model × available/expected)

    Returns (success, loaded_count).
    """
    expected = max(expected_models, 1)
    status_text = st.empty()
    bar = st.progress(0.0)
    start = time.time()
    deadline = start + timeout_sec

    def _elapsed() -> str:
        secs = int(time.time() - start)
        return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"

    while time.time() < deadline:
        log = _parse_ovms_log(OVMS_LOG_PATH)
        graphs_done   = len(log["graphs"])
        avail_count   = len(log["available"])
        srv_listening = log["server_listening"]

        if avail_count >= expected:
            # All models AVAILABLE per log
            bar.progress(1.0)
            names = ", ".join(log["available"])
            status_text.markdown(
                f"✅ **All {avail_count} model(s) ready** ({_elapsed()})  \n`{names}`"
            )
            return True, avail_count

        if avail_count > 0:
            # Some models AVAILABLE — phase 4
            frac = 0.50 + 0.50 * min(avail_count / expected, 1.0)
            bar.progress(frac)
            names = ", ".join(log["available"])
            status_text.markdown(
                f"📦 **Loading models…** {avail_count}/{expected} ready ({_elapsed()})  \n"
                f"`{names}`"
            )

        elif srv_listening:
            # Server up, no model available yet — phase 3
            bar.progress(0.50)
            status_text.markdown(
                f"🚀 **Server started, initialising models…** ({_elapsed()})"
            )

        elif graphs_done > 0:
            # Graph prep in progress — phase 2
            frac = 0.02 + 0.43 * min(graphs_done / expected, 1.0)
            bar.progress(frac)
            last = log["graphs"][-1]
            status_text.markdown(
                f"🔧 **Preparing model graphs…** {graphs_done}/{expected} done ({_elapsed()})  \n"
                f"`{last}`"
            )

        else:
            # Phase 1 — launcher is spinning up, nothing in log yet
            proc_count = get_ovms_process_count()
            if proc_count == 0:
                bar.progress(0.01)
                status_text.markdown(f"⏳ **Launching OVMS process…** ({_elapsed()})")
            else:
                bar.progress(0.02)
                status_text.markdown(f"🔧 **Preparing model graphs…** ({_elapsed()})")

        time.sleep(2)

    # timeout: do a final API check for accurate loaded count
    log = _parse_ovms_log(OVMS_LOG_PATH)
    return False, len(log["available"])


def restart_openwebui(container_name: str, timeout_sec: int = 120) -> None:
    subprocess.run(["docker", "restart", container_name], check=True)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        inspect_result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if inspect_result.returncode == 0:
            status_text = inspect_result.stdout.strip()
            parts = status_text.split("|")
            runtime = parts[0] if parts else ""
            health = parts[1] if len(parts) > 1 else "none"
            if runtime == "running" and health in {"healthy", "starting", "none"}:
                return

        time.sleep(2)

    raise RuntimeError(f"Container '{container_name}' did not return to running state in time.")


def inject_adminlte_style() -> None:
    st.markdown(
        """
        <style>
        /* ── Top header bar ──────────────────────────────────────── */
        .top-navbar {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            background: #3c8dbc;
            color: white;
            border-radius: 0.4rem;
            padding: 0.6rem 0.9rem;
            margin-bottom: 0.9rem;
        }
        .top-navbar .logo-mark {
            width: 34px; height: 34px;
            border-radius: 6px;
            background: rgba(255,255,255,0.2);
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 0.8rem; letter-spacing: 0.5px;
        }
        .top-navbar .title   { font-weight: 700; font-size: 1.05rem; line-height: 1.15; }
        .top-navbar .subtitle { font-size: 0.78rem; opacity: 0.88; }

        /* ── Sidebar shell ───────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            background: #222d32 !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 0 !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
        }
        /* suppress any default nav links Streamlit injects */
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display: none; }
        section[data-testid="stSidebar"] * { color: #b8c7ce; }
        section[data-testid="stSidebar"] .stMarkdown p { margin: 0; }
        section[data-testid="stSidebar"] .element-container { margin-bottom: 0 !important; }
        section[data-testid="stSidebar"] .stButton { margin-bottom: 0 !important; }

        /* ── Sidebar brand block ─────────────────────────────────── */
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 11px;
            background: #1a2226;
            padding: 14px 16px 13px;
            border-bottom: 1px solid #1c2b30;
        }
        .sidebar-brand-logo {
            width: 38px; height: 38px;
            border-radius: 6px;
            background: #3c8dbc;
            color: #fff;
            font-weight: 800; font-size: 0.82rem; letter-spacing: 0.5px;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }
        .brand-title  { font-size: 1rem;  font-weight: 700; color: #fff; line-height: 1.2; }
        .brand-sub    { font-size: 0.7rem; color: #8aa4af; margin-top: 2px; }

        /* ── OVMS status pill ────────────────────────────────────── */
        .sidebar-status-pill {
            font-size: 0.73rem;
            color: #8aa4af;
            background: #1c2b30;
            padding: 5px 16px 6px;
            border-bottom: 1px solid #192228;
        }
        .sidebar-status-pill strong { color: #c2cfd6; }

        /* ── Section label ───────────────────────────────────────── */
        .nav-section-header {
            font-size: 0.66rem;
            font-weight: 700;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            color: #4b6877 !important;
            padding: 14px 16px 5px;
            margin: 0;
        }

        /* ── Active nav item (rendered as a div, not a button) ───── */
        .nav-link-active {
            display: flex;
            align-items: center;
            gap: 9px;
            background: #1e282c;
            color: #fff !important;
            padding: 10px 15px 10px 13px;
            font-size: 0.88rem;
            font-weight: 600;
            border-left: 3px solid #3c8dbc;
            margin: 1px 0;
            line-height: 1.3;
        }
        .nav-link-active .nav-arrow {
            margin-left: auto;
            color: #8aa4af;
            font-size: 0.82rem;
        }

        /* ── Inactive nav buttons ────────────────────────────────── */
        section[data-testid="stSidebar"] .stButton button {
            background: transparent !important;
            color: #b8c7ce !important;
            border: none !important;
            border-left: 3px solid transparent !important;
            border-radius: 0 !important;
            font-size: 0.88rem !important;
            font-weight: 400 !important;
            text-align: left !important;
            padding: 9px 15px 9px 13px !important;
            width: 100% !important;
            margin: 0 !important;
            box-shadow: none !important;
            transition: background 0.14s, color 0.14s, border-left-color 0.14s;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            background: #1e282c !important;
            color: #fff !important;
            border-left-color: #3c8dbc !important;
        }

        /* ── Sidebar footer ──────────────────────────────────────── */
        .sidebar-footer {
            font-size: 0.68rem;
            color: #4b6877;
            padding: 10px 16px 12px;
            border-top: 1px solid #1a2226;
            margin-top: 10px;
        }

        /* ── Small stat boxes (Dashboard) ────────────────────────── */
        .small-box {
            border-radius: 0.5rem;
            color: #fff;
            padding: 14px;
            margin-bottom: 0.75rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }
        .small-box .label { font-size: 0.9rem; opacity: 0.9; }
        .small-box .value { font-size: 1.5rem; font-weight: 700; line-height: 1.2; }
        .bg-info    { background: #17a2b8; }
        .bg-success { background: #28a745; }
        .bg-warning { background: #f39c12; }
        .bg-danger  { background: #dc3545; }

        /* ── Panel cards (Dashboard / Settings) ─────────────────── */
        .panel-card {
            border: 1px solid #d2d6de;
            border-radius: 0.5rem;
            padding: 0.6rem 0.9rem;
            margin-bottom: 0.8rem;
            background: #fff;
        }
        .panel-title {
            font-weight: 700;
            color: #3c8dbc;
            margin-bottom: 0.4rem;
        }

        /* ── Scrollable log panels (terminal style) ───────────────────── */
        .log-scroll-wrap {
            border: 1px solid #333;
            border-radius: 6px;
            overflow: hidden;
            font-family: 'Cascadia Code', 'Cascadia Mono', 'Fira Code',
                         'Consolas', 'Courier New', monospace;
        }
        .log-terminal-bar {
            background: #2d2d2d;
            padding: 4px 10px;
            display: flex;
            align-items: center;
            gap: 6px;
            border-bottom: 1px solid #444;
        }
        .log-terminal-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        .log-terminal-bar span.log-title {
            color: #aaa;
            font-size: 0.72rem;
            margin-left: 6px;
            font-family: inherit;
        }
        /* column-reverse keeps scroll anchor at bottom → newest line visible */
        .log-scroll-outer {
            display: flex;
            flex-direction: column-reverse;
            height: 220px;
            overflow-y: auto;
            overflow-x: auto;
            background: #0d0d0d;
            color: #c5f467;
            font-family: inherit;
            font-size: 0.74rem;
            line-height: 1.55;
            padding: 6px 10px;
        }
        .log-scroll-outer > div.log-lines {
            min-width: max-content;
            width: 100%;
        }
        .log-scroll-outer > div.log-lines > div {
            white-space: nowrap;
        }
        .log-scroll-outer > div.log-lines > div:hover {
            background: rgba(255,255,255,0.05);
        }
        .log-scroll-footer {
            background: #1a1a1a;
            border-top: 1px solid #333;
            font-size: 0.69rem;
            color: #555;
            padding: 2px 10px;
            font-family: inherit;
            text-align: right;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _log_scroll_html(lines: list[str], title: str = "log") -> str:
    """Render lines as a terminal-styled scrollable panel.

    Uses flex-direction:column-reverse so the scroll anchor is at the bottom —
    newest line visible by default, scroll up for history.
    Lines are inserted newest-first in the DOM; column-reverse flips the visual
    order to oldest-at-top / newest-at-bottom.
    """
    if not lines:
        rows = "<div style='color:#555'>— no output —</div>"
    else:
        rows = "".join(f"<div>{html.escape(ln)}</div>" for ln in reversed(lines))

    terminal_bar = (
        "<div class='log-terminal-bar'>"
        "<span class='log-terminal-dot' style='background:#ff5f57'></span>"
        "<span class='log-terminal-dot' style='background:#febc2e'></span>"
        "<span class='log-terminal-dot' style='background:#28c840'></span>"
        f"<span class='log-title'>{html.escape(title)}</span>"
        "</div>"
    )
    body = (
        f"<div class='log-scroll-outer'>"
        f"<div class='log-lines'>{rows}</div>"
        f"</div>"
    )
    footer = f"<div class='log-scroll-footer'>{len(lines)} lines</div>"
    return f"<div class='log-scroll-wrap'>{terminal_bar}{body}{footer}</div>"


def get_system_status(models_dir: Path) -> dict:
    ram_percent = None
    ram_total_gb = None
    ram_used_gb = None
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        ram_percent = float(vm.percent)
        ram_total_gb = vm.total / (1024**3)
        ram_used_gb = vm.used / (1024**3)
    except Exception:
        pass

    total, used, free = shutil.disk_usage(models_dir)
    storage_percent = (used / total * 100) if total else 0

    vram_status = "Unknown"

    # ── Method 1: NVIDIA GPU via nvidia-smi ───────────────────────────────
    try:
        probe = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            check=False, capture_output=True, text=True, timeout=5,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            first = probe.stdout.strip().splitlines()[0]
            used_mb, total_mb = [x.strip() for x in first.split(",")]
            used_mb_i, total_mb_i = float(used_mb), float(total_mb)
            pct = (used_mb_i / total_mb_i * 100) if total_mb_i > 0 else 0
            vram_status = f"{used_mb_i:.0f} / {total_mb_i:.0f} MB ({pct:.1f}%) [NVIDIA]"
    except Exception:
        pass

    # ── Method 2: Intel GPU via OpenVINO runtime API ──────────────────────
    if vram_status == "Unknown":
        try:
            from openvino import Core  # type: ignore
            core = Core()
            if "GPU" in core.available_devices:
                total_bytes = core.get_property("GPU", "GPU_DEVICE_TOTAL_MEM_SIZE")
                total_mb_ov = int(total_bytes) / (1024 ** 2)
                device_name = core.get_property("GPU", "FULL_DEVICE_NAME")
                # GPU_MEMORY_STATISTICS shows allocations per pool (non-zero when models loaded)
                mem_stats = core.get_property("GPU", "GPU_MEMORY_STATISTICS")
                used_bytes = sum(v for v in mem_stats.values() if isinstance(v, (int, float)) and v > 0)
                if used_bytes > 0:
                    used_mb_ov = used_bytes / (1024 ** 2)
                    pct_ov = (used_mb_ov / total_mb_ov * 100) if total_mb_ov > 0 else 0
                    vram_status = f"{used_mb_ov:.0f} / {total_mb_ov:.0f} MB ({pct_ov:.1f}%) — {device_name}"
                else:
                    vram_status = f"0 / {total_mb_ov:.0f} MB (idle) — {device_name}"
        except Exception:
            pass

    # ── Method 3: Windows PowerShell WMI fallback (any GPU) ──────────────
    if vram_status == "Unknown":
        try:
            wmi_result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-WmiObject Win32_VideoController | Select-Object -First 1 AdapterRAM, Caption)"
                 " | ConvertTo-Csv -NoTypeInformation | Select-Object -Skip 1"],
                check=False, capture_output=True, text=True, timeout=8,
            )
            if wmi_result.returncode == 0 and wmi_result.stdout.strip():
                # CSV row: "AdapterRAM","Caption"  →  "134217728","Intel(R) UHD Graphics 770"
                row = wmi_result.stdout.strip().splitlines()[0].replace('"', '')
                parts = row.split(",", 1)
                adapter_ram = int(parts[0].strip() or 0)
                caption = parts[1].strip() if len(parts) > 1 else "GPU"
                if adapter_ram > 0:
                    vram_mb = adapter_ram / (1024 ** 2)
                    vram_status = f"{vram_mb:.0f} MB — {caption}"
        except Exception:
            pass

    return {
        "ram_percent": ram_percent,
        "ram_total_gb": ram_total_gb,
        "ram_used_gb": ram_used_gb,
        "storage_used_gb": used / (1024**3),
        "storage_total_gb": total / (1024**3),
        "storage_percent": storage_percent,
        "vram_status": vram_status,
    }


OVMS_LOG_HISTORY = 100  # max lines kept in memory
DASHBOARD_LOG_VISIBLE = 10  # lines shown in the dashboard code block


def get_recent_logs(container_name: str) -> tuple[str, str]:
    """Return (ovms_log, webui_log) each capped at OVMS_LOG_HISTORY lines."""
    # ── OVMS: read tail of ovms_startup.log ────────────────────────
    ovms_log = ""
    try:
        if OVMS_LOG_PATH.exists():
            all_lines = OVMS_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            ovms_log = "\n".join(all_lines[-OVMS_LOG_HISTORY:])
        else:
            ovms_log = "No OVMS startup log found."
    except Exception:
        ovms_log = "Unable to read OVMS log."

    # ── OpenWebUI: docker logs --tail ──────────────────────────────
    webui_log = ""
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(OVMS_LOG_HISTORY), container_name],
            check=False,
            capture_output=True,
            text=True,
        )
        webui_log = (result.stdout or result.stderr or "").strip()
    except Exception:
        webui_log = "Unable to read OpenWebUI logs."

    return ovms_log, webui_log


st.set_page_config(page_title="OVMS Model Manager", page_icon="📦", layout="wide")
inject_adminlte_style()
st.markdown(
        """
        <div class="top-navbar">
            <div class="logo-mark">OV</div>
            <div>
                <div class="title">OVMS Manager</div>
                <div class="subtitle">AdminLTE-style local manager for OVMS + OpenWebUI</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
)

if "models_dir_input" not in st.session_state:
    st.session_state["models_dir_input"] = str(DEFAULT_MODELS_DIR)
if "container_name" not in st.session_state:
    st.session_state["container_name"] = DEFAULT_OPENWEBUI_CONTAINER
if "hf_token" not in st.session_state:
    st.session_state["hf_token"] = ""
if "limit" not in st.session_state:
    st.session_state["limit"] = 0
if "load_full_details" not in st.session_state:
    st.session_state["load_full_details"] = True
if "sync_downloaded_to_openwebui" not in st.session_state:
    st.session_state["sync_downloaded_to_openwebui"] = True
if "restart_openwebui_after_register" not in st.session_state:
    st.session_state["restart_openwebui_after_register"] = True
if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"
if "pipeline_tag_backfill_done" not in st.session_state:
    backfill_pipeline_tags()
    st.session_state["pipeline_tag_backfill_done"] = True

ovms_status = get_ovms_status()

_ovms_state = ovms_status["state"]
_state_icon = "🟢" if _ovms_state == "healthy" else ("🟡" if _ovms_state == "starting" else "🔴")
_loaded_count = len(ovms_status.get("loaded_models", []))

with st.sidebar:
    # ── Brand ──────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-brand-logo">OV</div>
            <div>
                <div class="brand-title">OVMS Manager</div>
                <div class="brand-sub">OpenVINO Model Server</div>
            </div>
        </div>
        <div class="sidebar-status-pill">
            {_state_icon}&nbsp; OVMS: <strong>{_ovms_state.upper()}</strong>
            &nbsp;·&nbsp; {_loaded_count} model(s) loaded
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Nav items ──────────────────────────────────────────────
    st.markdown('<p class="nav-section-header">Main Navigation</p>', unsafe_allow_html=True)

    _current_page = st.session_state.get("page", "Dashboard")
    _nav_items = [
        ("Dashboard",     "📊"),
        ("Model Manager", "📦"),
        ("Settings",      "⚙️"),
    ]
    for _pname, _icon in _nav_items:
        if _current_page == _pname:
            st.markdown(
                f'<div class="nav-link-active">'
                f'<span>{_icon}</span> {_pname}'
                f'<span class="nav-arrow">›</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(f"{_icon}  {_pname}", key=f"nav_{_pname}", use_container_width=True):
                st.session_state["page"] = _pname
                st.rerun()

    # ── Footer ─────────────────────────────────────────────────
    st.markdown(
        '<div class="sidebar-footer">AdminLTE-style · OVMS v2026.0</div>',
        unsafe_allow_html=True,
    )

page = st.session_state.get("page", "Dashboard")

models_dir_input = str(st.session_state["models_dir_input"]).strip() or str(DEFAULT_MODELS_DIR)
container_name = str(st.session_state["container_name"]).strip() or DEFAULT_OPENWEBUI_CONTAINER
hf_token = str(st.session_state["hf_token"])
limit = int(st.session_state["limit"])
load_full_details = bool(st.session_state["load_full_details"])
sync_downloaded_to_openwebui = bool(st.session_state["sync_downloaded_to_openwebui"])
restart_openwebui_after_register = bool(st.session_state["restart_openwebui_after_register"])

models_dir = Path(models_dir_input)

if "catalog" not in st.session_state:
    st.session_state.catalog = []

if "registered_model_ids" not in st.session_state:
    st.session_state.registered_model_ids = set()

if not st.session_state.catalog:
    try:
        st.session_state.catalog = load_cached_models(int(limit))

        if not st.session_state.catalog:
            with st.spinner("Syncing local cache from Hugging Face..."):
                sync_cache_from_hf(int(limit), include_details=load_full_details)
            st.session_state.catalog = load_cached_models(int(limit))
        try:
            with st.spinner("Checking OpenWebUI registration status..."):
                st.session_state.registered_model_ids = get_registered_model_ids(container_name)
        except Exception:
            st.session_state.registered_model_ids = set()

        if sync_downloaded_to_openwebui and st.session_state.catalog:
            synced_count, synced_models = sync_downloaded_models_from_fs_to_openwebui(
                models_dir,
                container_name,
            )
            if synced_count > 0:
                st.session_state.registered_model_ids = get_registered_model_ids(container_name)
                st.info(f"Auto-synced {synced_count} downloaded model(s) to OpenWebUI: {', '.join(synced_models)}")

        st.success(f"Loaded {len(st.session_state.catalog)} models from local cache.")
    except Exception as error:
        st.error(f"Failed to load catalog: {error}")

catalog = st.session_state.catalog
models_dir = Path(models_dir_input)

if page == "Dashboard":
    available_count = len(catalog)
    downloaded_models = get_downloaded_model_ids_from_fs(models_dir)
    downloaded_count = len(downloaded_models)
    registered_count = len(st.session_state.registered_model_ids)
    ovms_state = ovms_status["state"]

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.markdown(
            f"<div class='small-box bg-info'><div class='label'>Available Models</div><div class='value'>{available_count}</div></div>",
            unsafe_allow_html=True,
        )
    with b2:
        st.markdown(
            f"<div class='small-box bg-success'><div class='label'>Downloaded</div><div class='value'>{downloaded_count}</div></div>",
            unsafe_allow_html=True,
        )
    with b3:
        st.markdown(
            f"<div class='small-box bg-warning'><div class='label'>Registered</div><div class='value'>{registered_count}</div></div>",
            unsafe_allow_html=True,
        )
    with b4:
        color = "bg-success" if ovms_state == "healthy" else ("bg-warning" if ovms_state == "starting" else "bg-danger")
        st.markdown(
            f"<div class='small-box {color}'><div class='label'>OVMS Status</div><div class='value'>{ovms_state.upper()}</div></div>",
            unsafe_allow_html=True,
        )

    status = get_system_status(models_dir)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='panel-card'><div class='panel-title'>RAM</div></div>", unsafe_allow_html=True)
        if status["ram_percent"] is None:
            st.write("Unavailable (install `psutil` to enable detailed RAM metric).")
        else:
            st.write(
                f"{status['ram_used_gb']:.1f} / {status['ram_total_gb']:.1f} GB ({status['ram_percent']:.1f}%)"
            )
    with c2:
        st.markdown("<div class='panel-card'><div class='panel-title'>VRAM</div></div>", unsafe_allow_html=True)
        st.write(status["vram_status"])
    with c3:
        st.markdown("<div class='panel-card'><div class='panel-title'>Storage</div></div>", unsafe_allow_html=True)
        st.write(
            f"{status['storage_used_gb']:.1f} / {status['storage_total_gb']:.1f} GB ({status['storage_percent']:.1f}%)"
        )

    ovms_log, webui_log = get_recent_logs(container_name)
    l1, l2 = st.columns(2)
    with l1:
        st.markdown("<div class='panel-card'><div class='panel-title'>Event Logs (OVMS)</div></div>", unsafe_allow_html=True)
        st.markdown(_log_scroll_html((ovms_log or "").splitlines(), title="ovms_startup.log"), unsafe_allow_html=True)
    with l2:
        st.markdown("<div class='panel-card'><div class='panel-title'>Error / Event Logs (OpenWebUI)</div></div>", unsafe_allow_html=True)
        st.markdown(_log_scroll_html((webui_log or "").splitlines(), title="docker logs open-webui"), unsafe_allow_html=True)

elif page == "Model Manager" and catalog:
    # Build rows for DataTable — all catalog, filtering handled inside DataTables
    dt_rows = []
    for item in catalog:
        model_id = item["id"]
        dt_rows.append({
            "id": model_id,
            "downloaded": is_model_downloaded(model_id, models_dir),
            "registered": model_id in st.session_state.registered_model_ids,
            "category": item.get("pipeline_tag") or "Unknown",
            "downloads": item.get("downloads", 0),
            "parameters": item.get("parameters", "Unknown"),
            "file_size": item.get("file_size", "Unknown"),
            "max_context": item.get("max_context", "Unknown"),
            "license": item.get("license", "Unknown"),
            "private": item.get("private", False),
        })

    # Render table — data embedded directly in HTML, no component protocol
    st_components.html(_build_table_html(dt_rows), height=820, scrolling=False)
    st.caption("🟢 green = downloaded locally · 🔵 blue = registered in OpenWebUI · 🟡 yellow = both")
    st.divider()

    # ── Model selection via multiselects ──────────────────────────────────
    not_downloaded = [r["id"] for r in dt_rows if not r["downloaded"]]
    already_dl     = [r["id"] for r in dt_rows if r["downloaded"]]
    not_registered = [r["id"] for r in dt_rows if not r["registered"]]
    already_reg    = [r["id"] for r in dt_rows if r["registered"]]

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        to_download = st.multiselect("⬇ Download to `models/`", not_downloaded, key="sel_dl")
        to_remove   = st.multiselect("🗑 Remove downloaded",    already_dl,     key="sel_rm")
    with sel_col2:
        to_register   = st.multiselect("📋 Register in OpenWebUI", not_registered, key="sel_reg")
        to_unregister = st.multiselect("❌ Unregister",             already_reg,    key="sel_unreg")

    # ── Action bar ────────────────────────────────────────────────────────
    control_col_refresh, control_col_info, control_col_apply = st.columns([1.2, 2.2, 1.2])
    with control_col_refresh:
        refresh = st.button("Refresh OpenVINO Model List", width="stretch")
    with control_col_info:
        st.markdown(f"**Models in catalog:** {len(catalog)}")
    with control_col_apply:
        apply_actions = st.button("Apply Actions", width="stretch")

    if refresh:
        try:
            with st.spinner("Syncing local cache from Hugging Face..."):
                sync_cache_from_hf(int(limit), include_details=load_full_details)
            st.session_state.catalog = load_cached_models(int(limit))
            try:
                with st.spinner("Checking OpenWebUI registration status..."):
                    st.session_state.registered_model_ids = get_registered_model_ids(container_name)
            except Exception:
                st.session_state.registered_model_ids = set()

            if sync_downloaded_to_openwebui and st.session_state.catalog:
                synced_count, synced_models = sync_downloaded_models_from_fs_to_openwebui(
                    models_dir,
                    container_name,
                )
                if synced_count > 0:
                    st.session_state.registered_model_ids = get_registered_model_ids(container_name)
                    st.info(f"Auto-synced {synced_count} downloaded model(s) to OpenWebUI: {', '.join(synced_models)}")

            st.success(f"Synced and loaded {len(st.session_state.catalog)} models from local cache.")
            st.rerun()
        except Exception as error:
            st.error(f"Failed to load catalog: {error}")

    if apply_actions:
        download_ids        = list(to_download)
        remove_download_ids = list(to_remove)
        register_ids        = list(to_register)
        unregister_ids      = list(to_unregister)

        if not download_ids and not register_ids and not remove_download_ids and not unregister_ids:
            st.warning("Nothing selected — choose models in the dropdowns above first.")
        else:
            try:
                if remove_download_ids:
                    removed_count = 0
                    for model_id in remove_download_ids:
                        if remove_downloaded_model(model_id, models_dir):
                            removed_count += 1
                    st.success(f"Removed {removed_count} downloaded model folder(s).")

                if download_ids:
                    for model_id in download_ids:
                        if is_model_downloaded(model_id, models_dir):
                            st.info(f"Already downloaded: {model_id}")
                            continue
                        with st.spinner(f"Downloading {model_id}..."):
                            local_path = download_model(model_id, models_dir, hf_token)
                        st.success(f"Downloaded {model_id} to {local_path}")

                if register_ids:
                    with st.spinner("Updating OpenWebUI database..."):
                        added_rows, user_count = register_models_in_openwebui(register_ids, container_name)
                    st.success(
                        f"Registered {len(register_ids)} model(s) for {user_count} user(s). New model rows added: {added_rows}."
                    )

                if unregister_ids:
                    with st.spinner("Removing model registration from OpenWebUI..."):
                        removed_rows, touched_users = unregister_models_in_openwebui(unregister_ids, container_name)
                    st.success(
                        f"Unregistered {len(unregister_ids)} model(s). Removed model rows: {removed_rows}. Updated users: {touched_users}."
                    )

                if restart_openwebui_after_register and (register_ids or unregister_ids):
                    with st.spinner("Restarting OpenWebUI to apply model list changes..."):
                        restart_openwebui(container_name)
                    st.success("OpenWebUI restarted successfully.")

                try:
                    st.session_state.registered_model_ids = get_registered_model_ids(container_name)
                except Exception:
                    pass

                st.rerun()
            except Exception as error:
                st.error(f"Failed to apply actions: {error}")

elif page == "Model Manager":
    st.warning("No models loaded yet.")

elif page == "Settings":
    st.markdown("<div class='panel-card'><div class='panel-title'>Application Settings</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "Models folder",
            value=st.session_state.get("models_dir_input", str(DEFAULT_MODELS_DIR)),
            key="models_dir_input",
        )
        st.text_input(
            "OpenWebUI container",
            value=st.session_state.get("container_name", DEFAULT_OPENWEBUI_CONTAINER),
            key="container_name",
        )
        st.number_input(
            "Max models to list (0 = all)",
            min_value=0,
            max_value=500,
            step=10,
            value=st.session_state.get("limit", 0),
            key="limit",
        )
    with c2:
        st.text_input(
            "HF token (optional)",
            type="password",
            value=st.session_state.get("hf_token", ""),
            key="hf_token",
        )
        st.checkbox(
            "Sync full model details on refresh",
            value=st.session_state.get("load_full_details", True),
            key="load_full_details",
        )
        st.checkbox(
            "Auto-sync downloaded models to OpenWebUI",
            value=st.session_state.get("sync_downloaded_to_openwebui", True),
            key="sync_downloaded_to_openwebui",
        )
        st.checkbox(
            "Restart OpenWebUI after register/unregister",
            value=st.session_state.get("restart_openwebui_after_register", True),
            key="restart_openwebui_after_register",
        )

    if st.button("Apply Settings", width="stretch"):
        try:
            new_limit = int(st.session_state.get("limit", 0))
            new_details = st.session_state.get("load_full_details", True)

            sync_bar = st.progress(0.0)
            sync_status = st.empty()

            def _on_progress(current, total, model_id):
                frac = current / max(total, 1)
                sync_bar.progress(frac)
                short = model_id.split("/")[-1] if "/" in model_id else model_id
                sync_status.markdown(
                    f"🔄 **Syncing model {current} / {total}** &nbsp; `{short}`"
                )

            synced = sync_cache_from_hf(new_limit, include_details=new_details,
                                        progress_callback=_on_progress)
            sync_bar.progress(1.0)
            st.session_state.catalog = load_cached_models(new_limit)
            sync_status.markdown(
                f"✅ **Done** — synced {synced} model(s) from Hugging Face, "
                f"{len(st.session_state.catalog)} loaded into catalog."
            )
        except Exception as e:
            st.error(f"Sync failed: {e}")
        st.rerun()

    st.markdown("<div class='panel-card'><div class='panel-title'>OVMS Control</div></div>", unsafe_allow_html=True)
    st.write(f"Current state: {ovms_status['state']}")
    st.write(f"Loaded models: {', '.join(ovms_status['loaded_models']) if ovms_status['loaded_models'] else 'none'}")

    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        start_ovms_btn = st.button("Start OVMS", width="stretch")
    with s_col2:
        stop_ovms_btn = st.button("Stop OVMS", width="stretch")
    with s_col3:
        restart_ovms_btn = st.button("Restart OVMS", width="stretch")
    with s_col4:
        refresh_ovms_btn = st.button("Refresh OVMS", width="stretch")

    if start_ovms_btn:
        try:
            get_ovms_status.clear()
            if get_ovms_status()["state"] != "stopped":
                st.info("OVMS is already running or starting.")
            else:
                models_dir_path = Path(models_dir_input)
                try:
                    registered_for_multi = sorted(get_registered_model_ids(container_name))
                except Exception:
                    registered_for_multi = []
                if not registered_for_multi:
                    registered_for_multi = get_downloaded_model_ids_from_fs(models_dir_path)
                valid_models, invalid_models = split_valid_invalid_models(registered_for_multi, models_dir_path)
                if not valid_models:
                    invalid_details = ", ".join([f"{m} ({r})" for m, r in invalid_models])
                    raise RuntimeError(f"No valid models for OVMS multi start. Invalid: {invalid_details}")
                if invalid_models:
                    st.warning(
                        "Skipping invalid models: "
                        + ", ".join([f"{m} ({r})" for m, r in invalid_models])
                    )
                expected_models = len(valid_models)
                with st.spinner(f"Launching OVMS with {expected_models} model(s)…"):
                    start_ovms_multi_with_models(valid_models)
                st.markdown("**Waiting for models to load…**")
                ready, loaded = wait_for_ovms_ready_with_progress(expected_models, timeout_sec=300)
                if ready:
                    st.success(f"OVMS started — {loaded} model(s) serving.")
                else:
                    st.warning(f"OVMS start timed out ({loaded}/{expected_models} models loaded).")
            get_ovms_status.clear()
            st.rerun()
        except Exception as error:
            st.error(f"Failed to start OVMS: {error}")

    if stop_ovms_btn:
        try:
            with st.spinner("Stopping OVMS..."):
                stop_ovms()
                time.sleep(1)
            st.success("OVMS stop command sent.")
            get_ovms_status.clear()
            st.rerun()
        except Exception as error:
            st.error(f"Failed to stop OVMS: {error}")

    if restart_ovms_btn:
        try:
            with st.spinner("Stopping OVMS…"):
                stop_ovms()
                time.sleep(1)
            models_dir_path = Path(models_dir_input)
            try:
                registered_for_multi = sorted(get_registered_model_ids(container_name))
            except Exception:
                registered_for_multi = []
            if not registered_for_multi:
                registered_for_multi = get_downloaded_model_ids_from_fs(models_dir_path)
            valid_models, invalid_models = split_valid_invalid_models(registered_for_multi, models_dir_path)
            if not valid_models:
                invalid_details = ", ".join([f"{m} ({r})" for m, r in invalid_models])
                raise RuntimeError(f"No valid models for OVMS multi restart. Invalid: {invalid_details}")
            if invalid_models:
                st.warning(
                    "Skipping invalid models: "
                    + ", ".join([f"{m} ({r})" for m, r in invalid_models])
                )
            expected_models = len(valid_models)
            with st.spinner(f"Launching OVMS with {expected_models} model(s)…"):
                start_ovms_multi_with_models(valid_models)
            st.markdown("**Waiting for models to load…**")
            ready, loaded = wait_for_ovms_ready_with_progress(expected_models, timeout_sec=300)
            if ready:
                st.success(f"OVMS restarted — {loaded} model(s) serving.")
            else:
                st.warning(f"OVMS restart timed out ({loaded}/{expected_models} models loaded).")
            get_ovms_status.clear()
            st.rerun()
        except Exception as error:
            st.error(f"Failed to restart OVMS: {error}")

    if refresh_ovms_btn:
        get_ovms_status.clear()
        st.rerun()

    # ── OVMS last-startup status ───────────────────────────────────────────
    if OVMS_LOG_PATH.exists():
        log = _parse_ovms_log(OVMS_LOG_PATH)
        avail = log["available"]
        graphs = log["graphs"]
        if avail:
            st.success(
                f"Last startup: **{len(avail)}** model(s) reached AVAILABLE — "
                + ", ".join(f"`{n}`" for n in avail)
            )
        elif graphs:
            st.info(f"Last startup: graph prep completed for {len(graphs)} model(s) — server may have stopped.")
        else:
            st.info("Last startup log exists but no milestones recorded yet.")
        with st.expander("🔍 View raw startup log", expanded=False):
            lines = OVMS_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-100:]) if len(lines) > 100 else "\n".join(lines)
            st.code(tail, language="", wrap_lines=True)
