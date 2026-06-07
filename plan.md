# Plan: Streamlit Web App for Check Request Form Generator

## What this is

A simple Streamlit web app that wraps the existing Python PDF/DOCX generator. Team members log in, upload the monthly CSV, click Generate, and download the combined PDF and DOCX. When the browser tab closes, all data is gone — nothing is stored on the server.

---

## What already exists (keep unchanged)

| File | Role |
|---|---|
| `csv_to_word_forms.py` | Full engine: reads CSV, fills Word template, merges forms, converts to PDF |
| `csv_to_pdf_forms.py` | CLI wrapper — kept as-is |
| `Form Template/...docx` | Word template — untouched |

---

## What to build

### 1. `app.py` — the Streamlit app

Two UI states:

**Logged out:**
- Centered card with username + password fields and a Sign In button
- Credentials checked against `st.secrets["USERNAME"]` and `st.secrets["PASSWORD"]`
- On success: `st.session_state.logged_in = True`

**Logged in:**
- Privacy notice: *"Files are processed and deleted immediately. No data is stored on this server."*
- `st.file_uploader` for `.csv` files → bytes stored in `st.session_state.csv_bytes`
- **Generate** button → runs the engine in a `tempfile.TemporaryDirectory`:
  1. Write CSV bytes to `temp/input.csv`
  2. Import and call `build_column_map`, `fill_template`, `Composer` merge from `csv_to_word_forms.py` → save `combined.docx`
  3. Call `convert_docx_to_pdf` (LibreOffice headless) → save `combined.pdf`
  4. Read both into `st.session_state.docx_bytes` and `st.session_state.pdf_bytes`
  5. Temp dir auto-deleted
- **Download PDF** button (`st.download_button`)
- **Download DOCX** button (`st.download_button`)
- Sign Out button → clears session state

---

### 2. `requirements.txt` — update

Add `streamlit` to the existing deps:

```
python-docx>=1.1.0
docxcompose>=1.4.0
docx2pdf>=0.1.8
streamlit>=1.35.0
```

---

### 3. `packages.txt` — new file

Tells Streamlit Community Cloud to install LibreOffice (needed for PDF conversion on Linux):

```
libreoffice
```

---

### 4. `.streamlit/config.toml` — new file

```toml
[general]
name = "UBH Check Request Generator"

[server]
maxUploadSize = 10
```

---

### 5. `.streamlit/secrets.toml` — new file (local only, gitignored)

```toml
USERNAME = "ubhteam"
PASSWORD = "ubh2026"
```

This file is never committed. On Streamlit Cloud, these are entered in the Secrets dashboard.

---

### 6. `.gitignore` — new file

```
.streamlit/secrets.toml
Data/
Output/
__pycache__/
*.pyc
.DS_Store
```

---

## Deployment steps

1. Create a **private or public GitHub repo** and push this project
   - Must be public for Streamlit Community Cloud free tier
   - `Data/` and `.streamlit/secrets.toml` are gitignored — no client data in repo
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → connect repo → set main file to `app.py`
3. In the Streamlit Cloud **Secrets** tab, add:
   ```toml
   USERNAME = "ubhteam"
   PASSWORD = "ubh2026"
   ```
4. Click Deploy — Streamlit installs `libreoffice` from `packages.txt` and the Python deps from `requirements.txt`
5. Share the generated URL with the team

To change the password later: update the secret in the Streamlit Cloud dashboard → click Reboot app. No code change needed.

---

## Privacy / compliance

- No client data is ever written to disk beyond the lifespan of one Generate request (temp dir)
- No database, no persistent storage
- `.gitignore` ensures CSV files in `Data/` are never committed
- HTTPS enforced by Streamlit Community Cloud by default

---

## Implementation order

| Step | Task | Notes |
|---|---|---|
| 1 | Create `.gitignore` | Prevent accidental data commits |
| 2 | Create `packages.txt` | Single line: `libreoffice` |
| 3 | Create `.streamlit/config.toml` | App title, upload size limit |
| 4 | Create `.streamlit/secrets.toml` | Local credentials (gitignored) |
| 5 | Update `requirements.txt` | Add `streamlit` |
| 6 | Write `app.py` | Login UI + upload UI + generate + download |
| 7 | Test locally (`streamlit run app.py`) | Verify login, generate, download both formats |
| 8 | Push to GitHub | Confirm gitignore works |
| 9 | Deploy to Streamlit Community Cloud | Add secrets in dashboard |
| 10 | Smoke test on live URL | Full end-to-end with real CSV |

---

## Design spec

Full design doc: `docs/superpowers/specs/2026-06-07-streamlit-pdf-webapp-design.md`
