import csv
import tempfile
from pathlib import Path

import streamlit as st
from docx import Document
from docxcompose.composer import Composer

from csv_to_word_forms import (
    _detect_csv_encoding,
    build_column_map,
    convert_docx_to_pdf,
    fill_template,
    get_row_values,
)

TEMPLATE_PATH = (
    Path(__file__).parent
    / "Form Template"
    / "Rapid Rehousing Program Check Request Form - Template.docx"
)


def _check_credentials(username: str, password: str) -> bool:
    return username == st.secrets["USERNAME"] and password == st.secrets["PASSWORD"]


def _generate(csv_bytes: bytes) -> tuple[bytes, bytes | None]:
    """Return (docx_bytes, pdf_bytes). pdf_bytes is None if conversion fails."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        csv_path = tmp_path / "input.csv"
        csv_path.write_bytes(csv_bytes)

        encoding = _detect_csv_encoding(csv_path)
        with open(csv_path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            column_map = build_column_map(headers)
            docs = []
            for row in reader:
                values = get_row_values(row, column_map)
                doc = Document(TEMPLATE_PATH)
                fill_template(doc, values, row, column_map)
                docs.append(doc)

        if not docs:
            raise ValueError("The CSV has no data rows.")

        master = docs[0]
        composer = Composer(master)
        for doc in docs[1:]:
            composer.append(doc)

        docx_path = tmp_path / "Check_Requests_Combined.docx"
        composer.save(docx_path)
        docx_bytes = docx_path.read_bytes()

        pdf_path = tmp_path / "Check_Requests_Combined.pdf"
        pdf_bytes = (
            pdf_path.read_bytes()
            if convert_docx_to_pdf(docx_path, pdf_path)
            else None
        )

        return docx_bytes, pdf_bytes


def _login_page():
    st.title("UBH Check Request Generator")
    st.markdown("---")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In", use_container_width=True):
            if _check_credentials(username, password):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid username or password.")


def _main_page():
    col_title, col_signout = st.columns([5, 1])
    with col_title:
        st.title("Check Request Generator")
    with col_signout:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Sign Out"):
            st.session_state.clear()
            st.rerun()

    st.info(
        "Files are processed and deleted immediately. No data is stored on this server.",
        icon="🔒",
    )
    st.markdown("---")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded is not None:
        st.session_state.csv_bytes = uploaded.getvalue()

    if st.session_state.get("csv_bytes"):
        if st.button("Generate", type="primary", use_container_width=True):
            with st.spinner("Generating forms — this may take a moment..."):
                try:
                    docx_bytes, pdf_bytes = _generate(st.session_state.csv_bytes)
                    st.session_state.docx_bytes = docx_bytes
                    st.session_state.pdf_bytes = pdf_bytes
                    st.success("Done! Download your files below.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")

    if st.session_state.get("docx_bytes") or st.session_state.get("pdf_bytes"):
        st.markdown("### Downloads")
        col_pdf, col_docx = st.columns(2)
        with col_pdf:
            if st.session_state.get("pdf_bytes"):
                st.download_button(
                    label="⬇ Download PDF",
                    data=st.session_state.pdf_bytes,
                    file_name="Check_Requests_Combined.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.warning("PDF conversion unavailable on this server.")
        with col_docx:
            if st.session_state.get("docx_bytes"):
                st.download_button(
                    label="⬇ Download DOCX",
                    data=st.session_state.docx_bytes,
                    file_name="Check_Requests_Combined.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )


def main():
    st.set_page_config(
        page_title="UBH Check Request Generator",
        page_icon="📄",
        layout="centered",
    )

    if not st.session_state.get("logged_in"):
        _login_page()
    else:
        _main_page()


if __name__ == "__main__":
    main()
