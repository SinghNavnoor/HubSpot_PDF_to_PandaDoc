# Plan: Streamlit Web App for Check Request Form Generator

## What this is

A Streamlit web app that wraps the existing Python DOCX generator. Team members log in, upload the monthly CSV, click Generate, and download the combined DOCX. When the browser tab closes, all data is gone — nothing is stored on the server.

---

## What already exists (unchanged)

| File | Role |
|---|---|
| `csv_to_word_forms.py` | Full engine: reads CSV, fills Word template, merges forms |
| `csv_to_pdf_forms.py` | CLI wrapper — kept as-is, not used by the web app |
| `Form Template/...docx` | Word template — untouched |

---

## What was built

### Files created / updated

| File | Status | Notes |
|---|---|---|
| `app.py` | Done | Full Streamlit app — login, upload, generate, download |
| `requirements.txt` | Done | `python-docx`, `docxcompose`, `streamlit>=1.35.0` |
| `packages.txt` | Done | `libreoffice` — installed by Streamlit Cloud via apt |
| `.streamlit/config.toml` | Done | White background, 10 MB upload limit |
| `.streamlit/secrets.toml` | Done | Local only — gitignored, never committed |
| `.gitignore` | Done | Excludes `secrets.toml`, `Data/`, `Output/`, pycache, etc. |
| `plan.md` | Done | This file |

### What `app.py` does

**Login page:**
- Centered form with username + password
- Credentials checked against `st.secrets["USERNAME"]` and `st.secrets["PASSWORD"]`
- On success: `st.session_state.logged_in = True`

**Main page (three-column layout):**
- **Left panel** — bordered box with CSV file uploader. On upload, bytes stored in `st.session_state.csv_bytes`
- **Middle** — Generate button (disabled until a file is uploaded). On click: writes CSV to a `tempfile.TemporaryDirectory`, runs the engine, stores DOCX bytes in `st.session_state.docx_bytes`, temp dir deleted automatically
- **Right panel** — bordered box. Shows Download DOCX button once generated. Click downloads straight to browser Downloads folder — no Word app interaction

**Sign Out** — clears all session state (data, generated file)

### Output format
- **DOCX only** — PDF removed entirely. `docx2pdf` removed from dependencies.

### Auth
- Single shared credential: `USERNAME = "ubhteam"`, `PASSWORD = "ubh2026"`
- Stored in `.streamlit/secrets.toml` locally and in Streamlit Cloud secrets manager in production
- Never committed to the repo

---

## GitHub

- Repo: `https://github.com/SinghNavnoor/bulk_check_request_ubh`
- Branch: `main`
- Pushed: initial commit + gitignore conflict resolution commit
- `Data/`, `Output/`, `.streamlit/secrets.toml` are all gitignored — no client data in repo

---

## Remaining steps

| Step | Task | Status |
|---|---|---|
| 7 | Test locally (`python3 -m streamlit run app.py`) | In progress |
| 8 | Push updated `app.py` + `requirements.txt` to GitHub | Pending |
| 9 | Deploy to Streamlit Community Cloud | Pending |
| 10 | Smoke test on live URL with real CSV | Pending |

---

## Deployment (when ready)

1. Go to [share.streamlit.io](https://share.streamlit.io) — sign in with GitHub
2. Click **Create app** → **Deploy a public app from GitHub**
3. Set repository: `SinghNavnoor/bulk_check_request_ubh`, branch: `main`, file: `app.py`
4. Click **Advanced settings** → paste into Secrets:
   ```toml
   USERNAME = "ubhteam"
   PASSWORD = "ubh2026"
   ```
5. Click **Deploy** — first deploy takes 3–5 min (LibreOffice install)
6. Share the generated URL with the team

To change the password later: update the secret in Streamlit Cloud dashboard → Reboot app. No code change needed.

---

## Privacy / compliance

- No client data ever written to disk beyond the lifespan of one Generate request (temp dir)
- No database, no persistent storage
- `.gitignore` ensures CSV files in `Data/` are never committed
- HTTPS enforced by Streamlit Community Cloud by default
- Privacy notice shown on main page: *"Files are processed and deleted immediately. No data is stored on this server."*

---

## Design spec

Full design doc: `docs/superpowers/specs/2026-06-07-streamlit-pdf-webapp-design.md`
