from pathlib import Path
from unittest.mock import Mock, patch

from run_batch import run


SAMPLE_ROWS = [{"Client Name": "Client X"}]


def _fake_generate(rows, template_path, output_path, include_signature_tag=False):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(b"fake docx")
    return Path(output_path)


@patch("run_batch.push_and_send")
@patch("run_batch.generate_combined_docx", side_effect=_fake_generate)
@patch("run_batch.pull_batch", return_value=(SAMPLE_ROWS, "Check Request - July - 2026-07-13"))
@patch("run_batch.HubSpotClient")
def test_dry_run_skips_pandadoc(mock_client, mock_pull, mock_generate, mock_push, tmp_path, monkeypatch):
    monkeypatch.setenv("HUBSPOT_API_KEY", "hs-key")
    out = tmp_path / "combined.docx"

    exit_code = run(dry_run=True, output_path=out)

    assert exit_code == 0
    assert out.is_file()
    mock_generate.assert_called_once()
    assert mock_generate.call_args[1]["include_signature_tag"] is False
    mock_push.assert_not_called()


@patch("run_batch.push_and_send", return_value="DOC123")
@patch("run_batch.generate_combined_docx", side_effect=_fake_generate)
@patch("run_batch.pull_batch", return_value=(SAMPLE_ROWS, "Check Request - July - 2026-07-13"))
@patch("run_batch.HubSpotClient")
def test_full_run_pushes_to_pandadoc(mock_client, mock_pull, mock_generate, mock_push, tmp_path, monkeypatch):
    monkeypatch.setenv("HUBSPOT_API_KEY", "hs-key")
    monkeypatch.setenv("PANDADOC_API_KEY", "pd-key")
    monkeypatch.setenv("SENIOR_HOUSING_PROGRAM_MANAGER_NAME", "Emily Manager")
    monkeypatch.setenv("SENIOR_HOUSING_PROGRAM_MANAGER_EMAIL", "emily@example.com")
    monkeypatch.setenv("PROGRAM_DIRECTOR_NAME", "Jane Director")
    monkeypatch.setenv("PROGRAM_DIRECTOR_EMAIL", "jane@example.com")
    out = tmp_path / "combined.docx"

    exit_code = run(dry_run=False, output_path=out)

    assert exit_code == 0
    mock_push.assert_called_once()
    kwargs = mock_push.call_args[1]
    assert kwargs["api_key"] == "pd-key"
    assert kwargs["shpm_name"] == "Emily Manager"
    assert kwargs["shpm_email"] == "emily@example.com"
    assert kwargs["director_name"] == "Jane Director"
    assert kwargs["director_email"] == "jane@example.com"
    assert kwargs["document_name"] == "Check Request - July - 2026-07-13"
    assert kwargs["page_count"] == 1  # one form per row, no cover page


@patch("run_batch.push_and_send")
@patch("run_batch.generate_combined_docx")
@patch("run_batch.pull_batch", return_value=([], ""))
@patch("run_batch.HubSpotClient")
def test_zero_rows_exits_cleanly_without_pandadoc(mock_client, mock_pull, mock_generate, mock_push, tmp_path, monkeypatch):
    monkeypatch.setenv("HUBSPOT_API_KEY", "hs-key")

    exit_code = run(dry_run=False, output_path=tmp_path / "combined.docx")

    assert exit_code == 0
    mock_generate.assert_not_called()
    mock_push.assert_not_called()
