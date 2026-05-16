from __future__ import annotations

import hashlib
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(slots=True)
class ParsedImageAsset:
    path: str
    source_kind: str
    label: str
    page_number: int | None = None


@dataclass(slots=True)
class ParsedBackgroundSection:
    identifier: str
    title: str
    text: str
    images: list[ParsedImageAsset]


@dataclass(slots=True)
class ParsedBackgroundDocument:
    title: str
    kind: str
    source_path: str
    sections: list[ParsedBackgroundSection]


@dataclass(slots=True)
class ParsedBackgroundBundle:
    documents: list[ParsedBackgroundDocument]
    image_refs: list[str]
    warnings: list[str]


def classify_background_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "image"
    if suffix == ".txt":
        return "text"
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime and mime.startswith("image/"):
        return "image"
    return "unknown"


def parse_background_files(file_paths: list[Path], image_dir: Path) -> ParsedBackgroundBundle:
    image_dir.mkdir(parents=True, exist_ok=True)
    documents: list[ParsedBackgroundDocument] = []
    warnings: list[str] = []

    for file_path in file_paths:
        kind = classify_background_file(file_path)
        if kind == "pdf":
            document, pdf_warnings = _parse_pdf(file_path, image_dir)
            documents.append(document)
            warnings.extend(pdf_warnings)
        elif kind == "image":
            documents.append(_parse_image_file(file_path, image_dir))
        elif kind == "text":
            documents.append(_parse_text_file(file_path))
        else:
            warnings.append(f"Unsupported background file type: {file_path.name}")

    return ParsedBackgroundBundle(
        documents=documents,
        image_refs=_collect_image_refs(documents),
        warnings=warnings,
    )


def render_parsed_background_markdown(
    bundle: ParsedBackgroundBundle,
    section_descriptions: dict[str, str] | None = None,
) -> str:
    descriptions = section_descriptions or {}
    markdown_parts: list[str] = []

    for document in bundle.documents:
        markdown_parts.append(f"# {document.title}")
        for section in document.sections:
            markdown_parts.append(f"## {section.title}")
            if section.text:
                markdown_parts.append(section.text)
            description = descriptions.get(section.identifier, "").strip()
            if description:
                markdown_parts.append("### Visual Notes")
                markdown_parts.append(description)
            for image in section.images:
                markdown_parts.append(f"![{image.label}]({Path(image.path).as_posix()})")

    return "\n\n".join(part for part in markdown_parts if part).strip()


def _parse_text_file(file_path: Path) -> ParsedBackgroundDocument:
    content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    section = ParsedBackgroundSection(
        identifier=f"text-{file_path.stem}",
        title=f"Background Text: {file_path.stem}",
        text=content,
        images=[],
    )
    return ParsedBackgroundDocument(
        title=f"Background Text: {file_path.stem}",
        kind="text",
        source_path=str(file_path),
        sections=[section],
    )


def _parse_image_file(file_path: Path, image_dir: Path) -> ParsedBackgroundDocument:
    target = image_dir / file_path.name
    if target.resolve() != file_path.resolve():
        shutil.copy2(file_path, target)

    image_asset = ParsedImageAsset(
        path=str(target),
        source_kind="standalone",
        label=file_path.stem,
    )
    section = ParsedBackgroundSection(
        identifier=f"image-{file_path.stem}",
        title=f"Background Image: {file_path.stem}",
        text="",
        images=[image_asset],
    )
    return ParsedBackgroundDocument(
        title=f"Background Image: {file_path.stem}",
        kind="image",
        source_path=str(file_path),
        sections=[section],
    )


def _parse_pdf(pdf_path: Path, image_dir: Path) -> tuple[ParsedBackgroundDocument, list[str]]:
    document = fitz.open(pdf_path)
    sections: list[ParsedBackgroundSection] = []
    warnings: list[str] = []
    saved_xrefs: dict[int, Path] = {}
    saved_block_hashes: dict[str, Path] = {}

    try:
        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()
            images = _extract_pdf_images(
                document=document,
                page=page,
                pdf_path=pdf_path,
                image_dir=image_dir,
                page_number=page_number,
                saved_xrefs=saved_xrefs,
                saved_block_hashes=saved_block_hashes,
            )

            if not page_text and not images:
                warnings.append(f"No extractable text or images found in {pdf_path.name} page {page_number}.")

            sections.append(
                ParsedBackgroundSection(
                    identifier=f"{pdf_path.stem}-page-{page_number:03d}",
                    title=f"Page {page_number}",
                    text=page_text,
                    images=images,
                )
            )
    finally:
        document.close()

    return (
        ParsedBackgroundDocument(
            title=f"PDF Material: {pdf_path.stem}",
            kind="pdf",
            source_path=str(pdf_path),
            sections=sections,
        ),
        warnings,
    )


def _extract_pdf_images(
    *,
    document: fitz.Document,
    page: fitz.Page,
    pdf_path: Path,
    image_dir: Path,
    page_number: int,
    saved_xrefs: dict[int, Path],
    saved_block_hashes: dict[str, Path],
) -> list[ParsedImageAsset]:
    images: list[ParsedImageAsset] = []
    seen_digests: set[str] = set()

    for ordinal, image_info in enumerate(page.get_images(full=True), start=1):
        xref = int(image_info[0])
        target = saved_xrefs.get(xref)
        if target is None:
            extracted = document.extract_image(xref)
            ext = extracted.get("ext", "bin")
            target = image_dir / f"{pdf_path.stem}-page-{page_number:03d}-xref-{xref}.{ext}"
            image_bytes = extracted["image"]
            target.write_bytes(image_bytes)
            saved_xrefs[xref] = target
        else:
            image_bytes = target.read_bytes()
        seen_digests.add(hashlib.sha1(image_bytes).hexdigest())
        images.append(
            ParsedImageAsset(
                path=str(target),
                source_kind="embedded",
                label=f"{pdf_path.stem} page {page_number} image {ordinal}",
                page_number=page_number,
            )
        )

    images.extend(
        _extract_block_images(
            page=page,
            pdf_path=pdf_path,
            image_dir=image_dir,
            page_number=page_number,
            saved_block_hashes=saved_block_hashes,
            existing_paths={image.path for image in images},
            existing_digests=seen_digests,
        )
    )
    return images


def _extract_block_images(
    *,
    page: fitz.Page,
    pdf_path: Path,
    image_dir: Path,
    page_number: int,
    saved_block_hashes: dict[str, Path],
    existing_paths: set[str],
    existing_digests: set[str],
) -> list[ParsedImageAsset]:
    assets: list[ParsedImageAsset] = []
    text_dict = page.get_text("dict")
    image_dir.mkdir(parents=True, exist_ok=True)

    for ordinal, block in enumerate(text_dict.get("blocks", []), start=1):
        if block.get("type") != 1:
            continue
        image_bytes = block.get("image")
        if not image_bytes:
            continue

        digest = hashlib.sha1(image_bytes).hexdigest()
        if digest in existing_digests:
            continue
        target = saved_block_hashes.get(digest)
        if target is None:
            ext = block.get("ext", "png")
            target = image_dir / f"{pdf_path.stem}-page-{page_number:03d}-block-{ordinal}.{ext}"
            target.write_bytes(image_bytes)
            saved_block_hashes[digest] = target

        if str(target) in existing_paths:
            continue

        existing_paths.add(str(target))
        existing_digests.add(digest)
        assets.append(
            ParsedImageAsset(
                path=str(target),
                source_kind="block",
                label=f"{pdf_path.stem} page {page_number} block image {ordinal}",
                page_number=page_number,
            )
        )

    return assets


def _collect_image_refs(documents: list[ParsedBackgroundDocument]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for document in documents:
        for section in document.sections:
            for image in section.images:
                if image.path in seen:
                    continue
                seen.add(image.path)
                refs.append(image.path)
    return refs
