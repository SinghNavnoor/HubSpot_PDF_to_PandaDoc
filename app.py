import csv
import io
import tempfile
from pathlib import Path

import streamlit as st
from docx import Document
from docxcompose.composer import Composer

from csv_to_word_forms import (
    _detect_csv_encoding,
    build_column_map,
    fill_template,
    get_row_values,
)

TEMPLATE_PATH = (
    Path(__file__).parent
    / "Form Template"
    / "Rapid Rehousing Program Check Request Form - Template.docx"
)

CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""


def _check_credentials(username: str, password: str) -> bool:
    return username == st.secrets["USERNAME"] and password == st.secrets["PASSWORD"]


def _count_rows(csv_bytes: bytes) -> int:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = csv_bytes.decode(enc)
            reader = csv.DictReader(io.StringIO(text))
            return sum(1 for _ in reader)
        except Exception:
            continue
    return 0


def _generate(csv_bytes: bytes) -> bytes:
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
        return docx_path.read_bytes()


def _login_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("## UBH Check Request Generator")
            st.caption(
                "Upload the monthly CSV and generate combined check request forms in one step."
            )
            st.markdown("---")
            with st.form("login"):
                st.markdown("**Sign In**")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    if _check_credentials(username, password):
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
            st.caption("Authorized UBH team members only.")


def _sidebar():
    with st.sidebar:
        st.markdown("### UBH Generator")
        st.markdown("---")
        st.markdown("Signed in")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        st.markdown("---")
        st.caption(
            "Secure processing: files are deleted immediately after generation. "
            "No data is stored on this server."
        )


def _main_page():
    _sidebar()

    st.markdown("## UBH Check Request Generator")
    st.caption(
        "Upload the monthly CSV and generate combined check request forms in one step."
    )
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("**Step 1 — Upload CSV**")
            st.caption("Select the monthly CSV file to process.")
            uploaded = st.file_uploader("", type=["csv"], label_visibility="collapsed")
            if uploaded is not None:
                st.session_state.csv_bytes = uploaded.getvalue()
                row_count = _count_rows(st.session_state.csv_bytes)
                st.success(f"{uploaded.name} — {row_count} rows detected")

    with col2:
        with st.container(border=True):
            st.markdown("**Step 2 — Generate**")
            st.caption("Create the combined check request document.")
            has_file = bool(st.session_state.get("csv_bytes"))
            if st.button(
                "Generate",
                type="primary",
                use_container_width=True,
                disabled=not has_file,
            ):
                with st.spinner("Generating document..."):
                    try:
                        st.session_state.docx_bytes = _generate(
                            st.session_state.csv_bytes
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(
                            "Could not generate the document. Please check that "
                            "the CSV has the expected columns and try again."
                        )
                        with st.expander("Error details"):
                            st.code(str(exc))

    with col3:
        with st.container(border=True):
            st.markdown("**Step 3 — Download**")
            if st.session_state.get("docx_bytes"):
                st.caption("Your combined check request file has been generated.")
                st.success("Document ready")
                st.download_button(
                    label="Download DOCX",
                    data=st.session_state.docx_bytes,
                    file_name="Check_Requests_Combined.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            else:
                st.caption(
                    "Upload a CSV and click Generate to create your DOCX."
                )
                st.markdown("No document yet")


def main():
    st.set_page_config(
        page_title="UBH Check Request Generator",
        page_icon="📄",
        layout="wide",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    if not st.session_state.get("logged_in"):
        _login_page()
    else:
        _main_page()


if __name__ == "__main__":
    main()
