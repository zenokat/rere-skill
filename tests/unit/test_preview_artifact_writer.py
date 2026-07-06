"""Unit tests for preview artifact file writing."""

from __future__ import annotations

from pathlib import Path

from core.preview.preview_artifact_writer import PreviewArtifactWriter


def test_preview_artifact_writer_uses_explicit_result_file(tmp_path: Path) -> None:
    """Writer should save preview output to the requested file path.

    Args:
        tmp_path: Temporary directory used to hold generated artifacts.

    Returns:
        None. Assertions verify the returned metadata and readable workbook.
    """

    output_root = tmp_path / "default-output"
    requested_file = tmp_path / "custom-output" / "preview.xlsx"
    writer = PreviewArtifactWriter(output_root=output_root)

    artifact = writer.write(
        recog_id="demo_recog",
        period="202605",
        records=[{"period": "202605", "amount": 12.5}],
        group_fields=["period"],
        result_file=requested_file,
    )

    records, metadata = writer.read(requested_file)

    assert artifact.result_file == requested_file
    assert requested_file.exists()
    assert records == [{"period": "202605", "amount": 12.5}]
    assert metadata["recog_id"] == "demo_recog"
    assert metadata["period"] == "202605"
