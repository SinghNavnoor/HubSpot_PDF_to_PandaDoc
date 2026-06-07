# Design: Streamlit PDF Web App for Check Request Forms

**Date:** 2026-06-07
**Status:** Approved

---

## Summary

A Streamlit web app that lets the UBH team upload a CSV, generate a combined check request PDF and DOCX, and download both — with no data ever stored on the server.

---

## Architecture

Single Streamlit app (`app.py`) with two states:

1. **Logged out** — centered login form. Credentials checked against Streamlit secrets. On success sets `st.session_state.logged_in = True`.
2. **Logged in** — CSV file uploader, Generate button, PDF and DOCX download buttons that appear after generation.

All data lives in `st.session_state` as bytes. When the browser tab closes, Streamlit's session expires and everything is wiped — no database, no persistent disk writes.

---

## File Structure

```
Web version - New Monthly Rent/
├── app.py                          # Streamlit app (new)
├── csv_to_word_forms.py            # Engine — unchanged
├── csv_to_pdf_forms.py             # CLI wrapper — unchanged
├── Form Template/
│   └── Rapid Rehousing Program Check Request Form - Template.docx
├── requirements.txt                # Add: streamlit
├── packages.txt                    # apt: libreoffice
├── .streamlit/
│   ├── config.toml                 # App theme/title
│   └── secrets.toml                # Local only — gitignored
└── .gitignore                      # Excludes: secrets.toml, Data/, Output/
```

---

## Auth

- Credentials stored in `.streamlit/secrets.toml` (local) and Streamlit Cloud secrets manager (production)
- `USERNAME = "ubhteam"`, `PASSWORD = "ubh2026"`
- Simple equality check in `app.py` — no library, no JWT, no bcrypt
- `st.session_state.logged_in` gates the upload UI

---

## Data Flow

1. User uploads `.csv` → bytes held in `st.session_state.csv_bytes`
2. User clicks **Generate**:
   - Open `tempfile.TemporaryDirectory()`
   - Write CSV bytes to `temp_dir/input.csv`
   - Import and call engine functions from `csv_to_word_forms.py`:
     - `build_column_map` + `fill_template` loop + `Composer` merge → `combined.docx`
   - Call `convert_docx_to_pdf` (LibreOffice headless) → `combined.pdf`
   - Read both files into `st.session_state.docx_bytes` and `st.session_state.pdf_bytes`
   - Temp dir deleted automatically (context manager exits)
3. Two `st.download_button` widgets appear: **Download PDF** and **Download DOCX**

---

## Privacy

- `.gitignore` excludes `Data/`, `Output/`, `.streamlit/secrets.toml`
- No client data committed to the repo
- Notice displayed on upload page: *"Files are processed and deleted immediately. No data is stored on this server."*

---

## Hosting

- **Streamlit Community Cloud** (free)
- Requires a public GitHub repo
- Credentials stored in Streamlit's secrets manager (not in repo)
- `packages.txt` with `libreoffice` — installed via apt on deploy
- URL: `https://share.streamlit.io/...` (or custom domain if added later)

---

## What Is Not Changing

- `csv_to_word_forms.py` — untouched, imported directly by `app.py`
- `csv_to_pdf_forms.py` — untouched, kept for CLI use
- The Word template — untouched
- All form-filling logic, currency formatting, date formatting, assistance type branching — all unchanged
