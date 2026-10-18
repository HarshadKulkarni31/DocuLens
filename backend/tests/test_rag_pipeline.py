from pathlib import Path
import pytest
from app.services.pdf_service import PDFService
from app.services.chunking_service import ChunkingService
from app.services.retrieval_service import DocumentIndex

SAMPLE_PDF = Path(__file__).resolve().parent.parent.parent / "sample_documents" / "solarpulse_technical_report.pdf"

# Evaluation test benchmark: 8 questions covering factual lookup, multi-page retrieval, and unanswerable questions
EVALUATION_SET = [
    {
        "id": "eval_1",
        "question": "What is the peak round-trip efficiency of SolarPulse?",
        "expected_page": 1,
        "expected_token": "94.2%",
        "type": "factual_lookup",
    },
    {
        "id": "eval_2",
        "question": "What battery chemistry is used in SolarPulse?",
        "expected_page": 1,
        "expected_token": "Lithium Iron Phosphate",
        "type": "factual_lookup",
    },
    {
        "id": "eval_3",
        "question": "What type of cooling system is used for battery thermal regulation?",
        "expected_page": 2,
        "expected_token": "Glycol",
        "type": "factual_lookup",
    },
    {
        "id": "eval_4",
        "question": "What is the ambient operating temperature range?",
        "expected_page": 2,
        "expected_token": "-20°C",
        "type": "factual_lookup",
    },
    {
        "id": "eval_5",
        "question": "What is the estimated payback period in years?",
        "expected_page": 3,
        "expected_token": "3.8 years",
        "type": "financial_lookup",
    },
    {
        "id": "eval_6",
        "question": "What is the initial capital expenditure (CapEx)?",
        "expected_page": 3,
        "expected_token": "14.8 million",
        "type": "financial_lookup",
    },
    {
        "id": "eval_7",
        "question": "Which IEEE standard does SolarPulse comply with for grid interconnection?",
        "expected_page": 4,
        "expected_token": "IEEE 1547-2018",
        "type": "compliance_lookup",
    },
    {
        "id": "eval_8",
        "question": "What was the population of Ancient Rome during the reign of Augustus?",
        "expected_page": None,
        "expected_token": None,
        "type": "out_of_domain",
    },
]

@pytest.fixture(scope="module")
def indexed_document():
    assert SAMPLE_PDF.exists(), f"Sample PDF not found at {SAMPLE_PDF}"
    pdf_bytes = SAMPLE_PDF.read_bytes()
    pages, total_chars = PDFService.extract_text_by_pages(pdf_bytes)
    assert len(pages) == 4
    assert total_chars > 0

    chunks = ChunkingService.chunk_document(
        document_id="solarpulse_doc",
        pages=pages,
    )
    assert len(chunks) > 0

    index = DocumentIndex(document_id="solarpulse_doc", chunks=chunks)
    return index

@pytest.mark.parametrize("item", EVALUATION_SET)
def test_evaluation_question_retrieval(indexed_document, item):
    """
    Evaluates top-k retrieval accuracy for each question in the benchmark set.
    Verifies that the target chunk and correct source page are in top-k results.
    """
    results = indexed_document.search(item["question"], top_k=3)
    assert len(results) > 0

    if item["expected_page"] is not None:
        # Check if expected page is present among retrieved chunks
        retrieved_pages = [chunk.page_number for chunk, _ in results]
        assert item["expected_page"] in retrieved_pages, (
            f"Question: '{item['question']}' expected page {item['expected_page']}, "
            f"but got pages {retrieved_pages}"
        )

        # Check if the expected key token appears in the top retrieved chunk texts
        combined_text = " ".join([chunk.text for chunk, _ in results])
        assert item["expected_token"].lower() in combined_text.lower(), (
            f"Expected token '{item['expected_token']}' not found in retrieved text for question '{item['question']}'"
        )

