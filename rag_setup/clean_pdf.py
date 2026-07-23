from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_unstructured import UnstructuredLoader


PROJECT_DIR = Path(__file__).resolve().parent

PDF_PATH = (
    PROJECT_DIR
    / "data"
    / "CIS_Controls__v8__Critical_Security_Controls__2023_08.pdf"
)

CACHE_DIR = PROJECT_DIR / ".cache"
PARSED_CACHE_PATH = CACHE_DIR / "cis_parsed_elements.json"
CACHE_VERSION = 1


def clean_text(text: str) -> str:
    """Clean extracted PDF text without removing useful content."""
    text = text.replace("\u00ad", "")

    # Join words broken across lines with a hyphen.
    text = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        text,
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_source_signature(pdf_path: Path) -> dict[str, int]:
    """Return values used to detect whether the PDF changed."""
    file_stats = pdf_path.stat()

    return {
        "size": file_stats.st_size,
        "modified_time": file_stats.st_mtime_ns,
    }


def document_to_cache_record(document: Document) -> dict:
    """Convert a LangChain document into JSON-safe data."""
    return {
        "page_content": document.page_content,
        "metadata": {
            "source_document": document.metadata.get(
                "source_document"
            ),
            "page_number": document.metadata.get("page_number"),
            "category": document.metadata.get("category"),
            "element_id": document.metadata.get("element_id"),
        },
    }


def cache_record_to_document(record: dict) -> Document:
    """Convert cached JSON data back into a LangChain document."""
    return Document(
        page_content=record["page_content"],
        metadata=record["metadata"],
    )


def save_parsed_cache(
    pdf_path: Path,
    documents: list[Document],
) -> None:
    """Save parsed PDF elements for fast reuse."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "cache_version": CACHE_VERSION,
        "source_signature": get_source_signature(pdf_path),
        "documents": [
            document_to_cache_record(document)
            for document in documents
        ],
    }

    PARSED_CACHE_PATH.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_parsed_cache(
    pdf_path: Path,
) -> list[Document] | None:
    """Load cached elements when the cache is still valid."""
    if not PARSED_CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            PARSED_CACHE_PATH.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return None

    if payload.get("cache_version") != CACHE_VERSION:
        return None

    if payload.get("source_signature") != get_source_signature(
        pdf_path
    ):
        return None

    records = payload.get("documents")

    if not isinstance(records, list) or not records:
        return None

    return [
        cache_record_to_document(record)
        for record in records
    ]


def parse_pdf(pdf_path: Path) -> list[Document]:
    """Run the heavy hi-res PDF parsing process."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    loader = UnstructuredLoader(
        file_path=pdf_path,
        mode="elements",
        strategy="hi_res",
        infer_table_structure=True,
        languages=["eng"],
        extract_images_in_pdf=False,
    )

    parsed_documents = loader.load()
    cleaned_documents: list[Document] = []

    for document in parsed_documents:
        text = clean_text(document.page_content)

        if not text:
            continue

        original_metadata = dict(document.metadata)

        page_number = original_metadata.get("page_number")

        if page_number is not None:
            page_number = int(page_number)

        cleaned_documents.append(
            Document(
                page_content=text,
                metadata={
                    "source_document": pdf_path.name,
                    "page_number": page_number,
                    "category": original_metadata.get(
                        "category",
                        "Unknown",
                    ),
                    "element_id": original_metadata.get(
                        "element_id"
                    ),
                },
            )
        )

    if not cleaned_documents:
        raise RuntimeError(
            "The parser did not extract content from the PDF."
        )

    return cleaned_documents


def load_or_parse_pdf(
    pdf_path: Path,
    force_reparse: bool = False,
) -> list[Document]:
    """
    Load cached parsed elements, or parse and cache the PDF.

    The expensive hi-res parser runs only when necessary.
    """
    if not force_reparse:
        cached_documents = load_parsed_cache(pdf_path)

        if cached_documents is not None:
            print(
                f"Loaded {len(cached_documents)} parsed "
                "elements from cache."
            )
            return cached_documents

    print("No valid cache found. Parsing the PDF...")

    documents = parse_pdf(pdf_path)
    save_parsed_cache(pdf_path, documents)

    print(
        f"Saved {len(documents)} parsed elements to: "
        f"{PARSED_CACHE_PATH}"
    )

    return documents


def print_parsing_summary(documents: list[Document]) -> None:
    """Print a short validation summary."""
    categories = Counter(
        document.metadata.get("category", "Unknown")
        for document in documents
    )

    pages = {
        document.metadata.get("page_number")
        for document in documents
        if document.metadata.get("page_number") is not None
    }

    print(f"Parsed elements: {len(documents)}")
    print(f"Pages detected: {len(pages)}")
    print(f"Categories: {dict(categories)}")

    first_document = documents[0]

    print("\nFirst element metadata:")
    print(first_document.metadata)

    print("\nFirst element preview:")
    print(first_document.page_content[:500])


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description="Parse and cache the CIS PDF."
    )

    argument_parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the cache and parse the PDF again.",
    )

    arguments = argument_parser.parse_args()

    documents = load_or_parse_pdf(
        PDF_PATH,
        force_reparse=arguments.force,
    )

    print_parsing_summary(documents)


if __name__ == "__main__":
    main()