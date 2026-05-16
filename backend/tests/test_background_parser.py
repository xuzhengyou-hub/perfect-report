from __future__ import annotations

import base64
from pathlib import Path

import fitz

from report_backend.parsers.background_parser import (
    _extract_block_images,
    parse_background_files,
    render_parsed_background_markdown,
)


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6VqeoAAAAASUVORK5CYII="
)


def test_parse_background_files_extracts_pdf_images_and_renders_markdown(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _write_pdf_with_image(pdf_path, duplicate_on_second_page=False)

    bundle = parse_background_files([pdf_path], tmp_path / "images")

    assert len(bundle.documents) == 1
    document = bundle.documents[0]
    assert document.kind == "pdf"
    assert document.sections[0].text
    assert document.sections[0].images
    image_path = Path(document.sections[0].images[0].path)
    assert image_path.exists()
    assert image_path.suffix == ".png"

    markdown = render_parsed_background_markdown(
        bundle,
        {document.sections[0].identifier: "Detected a small embedded diagram."},
    )

    assert "# PDF Material: sample" in markdown
    assert "## Page 1" in markdown
    assert "Detected a small embedded diagram." in markdown
    assert image_path.as_posix() in markdown


def test_parse_background_files_deduplicates_reused_pdf_images(tmp_path: Path) -> None:
    pdf_path = tmp_path / "reused.pdf"
    _write_pdf_with_image(pdf_path, duplicate_on_second_page=True)

    bundle = parse_background_files([pdf_path], tmp_path / "images")

    assert len(bundle.documents[0].sections) == 2
    assert bundle.documents[0].sections[0].images
    assert bundle.documents[0].sections[1].images
    assert len(bundle.image_refs) == 1


def test_extract_block_images_saves_inline_like_blocks(tmp_path: Path) -> None:
    class FakePage:
        def get_text(self, mode: str) -> dict[str, object]:
            assert mode == "dict"
            return {
                "blocks": [
                    {"type": 1, "ext": "png", "image": PNG_BYTES},
                    {"type": 0, "text": "ignored"},
                ]
            }

    assets = _extract_block_images(
        page=FakePage(),
        pdf_path=tmp_path / "inline.pdf",
        image_dir=tmp_path / "images",
        page_number=1,
        saved_block_hashes={},
        existing_paths=set(),
        existing_digests=set(),
    )

    assert len(assets) == 1
    assert Path(assets[0].path).exists()
    assert assets[0].source_kind == "block"


def _write_pdf_with_image(pdf_path: Path, *, duplicate_on_second_page: bool) -> None:
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "Measured output from the embedded chart.")
    first_xref = first_page.insert_image(fitz.Rect(72, 120, 180, 220), stream=PNG_BYTES)

    if duplicate_on_second_page:
        second_page = document.new_page()
        second_page.insert_text((72, 72), "The same visual appears again.")
        second_page.insert_image(fitz.Rect(72, 120, 180, 220), xref=first_xref)

    document.save(pdf_path)
    document.close()
