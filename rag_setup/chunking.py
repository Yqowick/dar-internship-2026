from __future__ import annotations

import hashlib
import re
from statistics import median

import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from clean_pdf import PDF_PATH, load_or_parse_pdf

TARGET_CHUNK_TOKENS = 320
MAX_CHUNK_TOKENS = 420
MIN_CHUNK_TOKENS = 180
CHUNK_OVERLAP = 50
DEFAULT_SECTION_TITLE = "Document Introduction"

SKIPPED_CATEGORIES = {"Image", "Header", "Footer"}
SKIPPED_EXACT_TEXT = {
    "CIS Critical Security Controls",
    "CIS Controls v8",
}
CONTROL_NUMBER_PATTERN = re.compile(r"^(0[1-9]|1[0-8])$")
CONTROL_CONTEXT_END_PATTERN = re.compile(
    r"^(appendix\b|glossary\b|resources and references\b|controls and safeguards index\b)",
    flags=re.IGNORECASE,
)
TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(TOKEN_ENCODER.encode(text))


def unique_values(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def detect_control_starts(
    elements: list[Document],
) -> tuple[dict[int, tuple[str, str]], set[int]]:
    """Map each real CIS control-title element to its control number."""
    control_starts: dict[int, tuple[str, str]] = {}
    number_indices: set[int] = set()

    for index, element in enumerate(elements):
        number_text = element.page_content.strip()
        if not CONTROL_NUMBER_PATTERN.fullmatch(number_text):
            continue

        for title_index in range(index + 1, min(index + 5, len(elements))):
            candidate = elements[title_index]
            candidate_text = candidate.page_content.strip()
            candidate_category = candidate.metadata.get("category", "Unknown")

            if not candidate_text or candidate_category in SKIPPED_CATEGORIES:
                continue
            if candidate_text in SKIPPED_EXACT_TEXT:
                continue

            if candidate_category == "Title":
                control_starts[title_index] = (number_text, candidate_text)
                number_indices.add(index)
                break

            # A meaningful element before a title means this number is not
            # acting as a control marker.
            break

    return control_starts, number_indices


def build_section_title(
    title_parts: list[str],
    control_number: str | None,
    control_title: str | None,
) -> str:
    local_title = " > ".join(unique_values(title_parts))

    if control_number and control_title:
        control_heading = f"Control {control_number}: {control_title}"
        if not local_title or local_title == control_heading:
            return control_heading
        if local_title.startswith(control_heading):
            return local_title
        return f"{control_heading} > {local_title}"

    return local_title or DEFAULT_SECTION_TITLE


def create_section(
    title_parts: list[str],
    body_parts: list[str],
    page_numbers: list[int],
    source_document: str,
    control_number: str | None,
    control_title: str | None,
) -> Document:
    section_title = build_section_title(
        title_parts,
        control_number,
        control_title,
    )
    section_text = "\n\n".join(
        part.strip()
        for part in [section_title, *body_parts]
        if part and part.strip()
    )
    valid_pages = sorted(set(page_numbers))

    return Document(
        page_content=section_text,
        metadata={
            "source_document": source_document,
            "section_title": section_title,
            "section_titles": section_title,
            "control_number": control_number,
            "control_title": control_title,
            "page_number": valid_pages[0] if valid_pages else None,
            "end_page_number": valid_pages[-1] if valid_pages else None,
        },
    )


def group_elements_into_sections(elements: list[Document]) -> list[Document]:
    """Group elements while preserving boundaries between CIS Controls."""
    if not elements:
        return []

    source_document = elements[0].metadata.get(
        "source_document",
        "unknown_document",
    )
    control_starts, number_indices = detect_control_starts(elements)

    sections: list[Document] = []
    title_parts: list[str] = []
    body_parts: list[str] = []
    page_numbers: list[int] = []
    current_control_number: str | None = None
    current_control_title: str | None = None

    def flush_section() -> None:
        nonlocal title_parts, body_parts, page_numbers
        if not title_parts and not body_parts:
            return
        sections.append(
            create_section(
                title_parts=title_parts,
                body_parts=body_parts,
                page_numbers=page_numbers,
                source_document=source_document,
                control_number=current_control_number,
                control_title=current_control_title,
            )
        )
        title_parts = []
        body_parts = []
        page_numbers = []

    for index, element in enumerate(elements):
        text = element.page_content.strip()
        category = element.metadata.get("category", "Unknown")
        page_number = element.metadata.get("page_number")

        if (
            not text
            or category in SKIPPED_CATEGORIES
            or text in SKIPPED_EXACT_TEXT
        ):
            continue

        if index in number_indices:
            continue

        if index in control_starts:
            flush_section()
            current_control_number, current_control_title = control_starts[index]
            title_parts = [
                f"Control {current_control_number}: {current_control_title}"
            ]
            if isinstance(page_number, int):
                page_numbers.append(page_number)
            continue

        if category == "Title" and CONTROL_CONTEXT_END_PATTERN.match(text):
            flush_section()
            current_control_number = None
            current_control_title = None
            title_parts = [text]
            if isinstance(page_number, int):
                page_numbers.append(page_number)
            continue

        if category == "Title":
            if body_parts:
                flush_section()
            title_parts.append(text)
        elif category == "Table":
            body_parts.append(f"Table:\n{text}")
        else:
            body_parts.append(text)

        if isinstance(page_number, int):
            page_numbers.append(page_number)

    flush_section()
    return sections


def split_long_section(section: Document) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=MAX_CHUNK_TOKENS,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    split_parts = splitter.split_documents([section])

    for part in split_parts:
        section_title = section.metadata["section_title"]
        if not part.page_content.startswith(section_title):
            part.page_content = f"{section_title}\n\n{part.page_content}"
        part.metadata = dict(section.metadata)

    return split_parts


def control_key(document: Document) -> tuple[str | None, str | None]:
    return (
        document.metadata.get("control_number"),
        document.metadata.get("control_title"),
    )


def create_combined_chunk(units: list[Document]) -> Document:
    text = "\n\n".join(
        unit.page_content.strip()
        for unit in units
        if unit.page_content.strip()
    )
    titles = unique_values(
        [str(unit.metadata.get("section_title", "")) for unit in units]
    )
    all_pages: list[int] = []

    for unit in units:
        for field_name in ("page_number", "end_page_number"):
            value = unit.metadata.get(field_name)
            if isinstance(value, int):
                all_pages.append(value)

    first_unit = units[0]
    return Document(
        page_content=text,
        metadata={
            "source_document": first_unit.metadata.get(
                "source_document",
                "unknown_document",
            ),
            "section_title": titles[0] if titles else DEFAULT_SECTION_TITLE,
            "section_titles": " | ".join(titles),
            "control_number": first_unit.metadata.get("control_number"),
            "control_title": first_unit.metadata.get("control_title"),
            "page_number": min(all_pages) if all_pages else None,
            "end_page_number": max(all_pages) if all_pages else None,
        },
    )


def merge_short_sections(sections: list[Document]) -> list[Document]:
    units: list[Document] = []
    for section in sections:
        if count_tokens(section.page_content) > MAX_CHUNK_TOKENS:
            units.extend(split_long_section(section))
        else:
            units.append(section)

    chunks: list[Document] = []
    current_units: list[Document] = []
    current_token_count = 0
    current_key: tuple[str | None, str | None] | None = None

    def flush_current_units() -> None:
        nonlocal current_units, current_token_count, current_key
        if current_units:
            chunks.append(create_combined_chunk(current_units))
        current_units = []
        current_token_count = 0
        current_key = None

    for unit in units:
        unit_tokens = count_tokens(unit.page_content)
        unit_key = control_key(unit)

        if current_units and unit_key != current_key:
            flush_current_units()

        if unit_tokens >= TARGET_CHUNK_TOKENS:
            flush_current_units()
            chunks.append(unit)
            continue

        if current_units and current_token_count + unit_tokens > MAX_CHUNK_TOKENS:
            flush_current_units()

        if not current_units:
            current_key = unit_key

        current_units.append(unit)
        current_token_count += unit_tokens

        if current_token_count >= TARGET_CHUNK_TOKENS:
            flush_current_units()

    flush_current_units()

    if len(chunks) >= 2:
        final_chunk = chunks[-1]
        previous_chunk = chunks[-2]
        final_tokens = count_tokens(final_chunk.page_content)
        previous_tokens = count_tokens(previous_chunk.page_content)

        if (
            final_tokens < MIN_CHUNK_TOKENS
            and control_key(final_chunk) == control_key(previous_chunk)
            and previous_tokens + final_tokens <= MAX_CHUNK_TOKENS
        ):
            chunks = [
                *chunks[:-2],
                create_combined_chunk([previous_chunk, final_chunk]),
            ]

    return chunks


def finalize_chunk_metadata(chunks: list[Document]) -> list[Document]:
    for position, chunk in enumerate(chunks):
        token_count = count_tokens(chunk.page_content)
        identity = (
            f"{chunk.metadata.get('source_document')}:"
            f"{chunk.metadata.get('page_number')}:"
            f"{chunk.metadata.get('end_page_number')}:"
            f"{chunk.metadata.get('control_number')}:"
            f"{chunk.metadata.get('control_title')}:"
            f"{chunk.metadata.get('section_titles')}:"
            f"{position}:{chunk.page_content}"
        )
        chunk.metadata["chunk_id"] = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]
        chunk.metadata["chunk_position"] = position
        chunk.metadata["category"] = "SectionChunk"
        chunk.metadata["token_count"] = token_count

    return chunks


def is_noise_chunk(chunk: Document) -> bool:
    """Return True when a chunk contains only a heading or an empty table marker."""
    text = chunk.page_content.strip()
    section_title = str(chunk.metadata.get("section_title", "")).strip()

    if not text:
        return True

    if text == section_title:
        return True

    body = text
    if section_title and body.startswith(section_title):
        body = body[len(section_title):].strip()

    body = re.sub(r"^Table:\s*$", "", body, flags=re.IGNORECASE).strip()
    return not body


def create_chunks(sections: list[Document]) -> list[Document]:
    merged_chunks = merge_short_sections(sections)
    meaningful_chunks = [
        chunk for chunk in merged_chunks if not is_noise_chunk(chunk)
    ]
    return finalize_chunk_metadata(meaningful_chunks)


def print_chunk_validation(chunks: list[Document]) -> None:
    if not chunks:
        print("No chunks were generated.")
        return

    token_counts = [chunk.metadata["token_count"] for chunk in chunks]
    chunk_ids = [chunk.metadata["chunk_id"] for chunk in chunks]

    print("\nChunk size validation:")
    print(f"Minimum tokens: {min(token_counts)}")
    print(f"Median tokens: {median(token_counts)}")
    print(f"Maximum tokens: {max(token_counts)}")
    print(f"Chunks below 50 tokens: {sum(c < 50 for c in token_counts)}")
    print(f"Chunks below 128 tokens: {sum(c < 128 for c in token_counts)}")
    print(
        "Chunks between 256 and 512 tokens: "
        f"{sum(256 <= c <= 512 for c in token_counts)}"
    )
    print(
        f"Chunks above {MAX_CHUNK_TOKENS} tokens: "
        f"{sum(c > MAX_CHUNK_TOKENS for c in token_counts)}"
    )
    print(
        "Empty chunks: "
        f"{sum(not chunk.page_content.strip() for chunk in chunks)}"
    )
    print(f"Duplicate chunk IDs: {len(chunk_ids) - len(set(chunk_ids))}")


def print_control_sample(
    chunks: list[Document],
    control_number: str = "01",
) -> None:
    matches = [
        chunk
        for chunk in chunks
        if chunk.metadata.get("control_number") == control_number
    ]
    print(f"\nControl {control_number} chunks: {len(matches)}")

    for index, chunk in enumerate(matches[:3], start=1):
        print(f"\n--- Control sample {index} ---")
        print(f"Metadata: {chunk.metadata}")
        print(f"Preview:\n{chunk.page_content[:900]}")


def main() -> None:
    parsed_elements = load_or_parse_pdf(PDF_PATH)
    sections = group_elements_into_sections(parsed_elements)
    chunks = create_chunks(sections)

    print(f"Parsed elements: {len(parsed_elements)}")
    print(f"Grouped sections: {len(sections)}")
    print(f"Final chunks: {len(chunks)}")
    print_chunk_validation(chunks)
    print_control_sample(chunks)


if __name__ == "__main__":
    main()