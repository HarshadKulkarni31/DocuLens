---
title: DocuLens - AI Document Intelligence Platform
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# DocuLens 🔍
> **End-to-End AI Document Intelligence Platform**  
> Context-grounded Retrieval-Augmented Generation (RAG) with page-level citations & Gemini summarization.

---

## 🌟 Overview
**DocuLens** is a production-grade document intelligence platform that allows users to upload text-based PDFs, generate structured executive summaries, and ask questions with **strict context grounding** and **auditable page-number citations**.

Rather than naively piping entire documents into an LLM context window, DocuLens implements a true **Retrieval-Augmented Generation (RAG)** pipeline:
1. **Extraction**: Fast, page-by-page text extraction preserving 1-based page numbers.
2. **Chunking**: Sentence & paragraph-boundary chunking with overlap and page metadata.
3. **Embeddings & Vector Index**: Dense vector embeddings with Sentence Transformers (`all-MiniLM-L6-v2`) and FAISS inner-product cosine similarity search.
4. **Grounded Generation**: Google Gemini models generate answers strictly confined to retrieved passages, mapping source IDs back to verified chunk metadata to eliminate citation hallucinations.

---

## 🏗️ Architecture & RAG Pipeline

```
┌─────────────────┐       Multipart PDF       ┌────────────────────────┐
│  React + Vite   │ ────────────────────────> │    FastAPI Backend     │
│    Frontend     │ <──────────────────────── │                        │
└─────────────────┘      Ready / Results      └───────────┬────────────┘
                                                          │
                       ┌──────────────────────────────────┴──────────────────┐
                       │                                                     │
                       ▼                                                     ▼
              ┌─────────────────┐                                   ┌─────────────────┐
              │ PyMuPDF (fitz)  │                                   │ Sentence        │
              │ Page-by-page    │ ───> Overlapping Chunks ────────> │ Transformers    │
              │ Text Extraction │      (700-1000 chars)             │ Dense Vectors   │
              └─────────────────┘                                   └────────┬────────┘
                                                                             │
                                                                             ▼
                                                                    ┌─────────────────┐
                                                                    │   FAISS Index   │
                                                                    │ Cosine Match IP │
                                                                    └────────┬────────┘
                                                                             │ Top 3-5 Chunks
                                                                             ▼
                                                                    ┌─────────────────┐
                                                                    │  Google Gemini  │
                                                                    │ Grounded Answer │
                                                                    │  & Summaries    │
                                                                    └─────────────────┘
```

---

## ⚡ Tech Stack

| Area | Technology |
|---|---|
| **AI / Embeddings** | Sentence Transformers (`all-MiniLM-L6-v2`) |
| **Vector Search** | FAISS (`faiss-cpu`) with normalized inner-product cosine search |
| **LLM Generation** | Google Gen AI SDK (`gemini-2.5-flash` or configurable) |
| **PDF Extraction** | PyMuPDF (`fitz`) |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn |
| **Frontend UI** | React 19, Vite, Lucide Icons, Responsive CSS |
| **Packaging & CI** | Docker multi-stage build, Pytest, Git |

---

## 📁 Repository Structure

```
DocuLens/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app & static file serving
│   │   ├── config.py                   # Environment settings & thresholds
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py               # Health, upload, extract, summary, ask
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_service.py          # PDF validation & page extraction
│   │   │   ├── chunking_service.py     # Overlapping chunk creation
│   │   │   ├── embedding_service.py    # Sentence Transformers embeddings
│   │   │   ├── retrieval_service.py    # FAISS vector indexing & search
│   │   │   └── gemini_service.py       # Grounded Q&A and summary prompts
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── document.py             # Pydantic request & response models
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_pdf_service.py
│   │   ├── test_chunking_service.py
│   │   └── test_api.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadPanel.jsx         # Drag-and-drop ingestion & file status
│   │   │   ├── SummaryPanel.jsx        # Executive summary & key takeaways
│   │   │   ├── ChatPanel.jsx           # Grounded Q&A composer & history
│   │   │   └── SourceList.jsx          # Verified page citations & excerpts
│   │   ├── pages/
│   │   │   └── Home.jsx                # Main application page
│   │   ├── services/
│   │   │   └── api.js                  # Frontend API client
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css                   # Custom responsive styling
│   ├── package.json
│   └── vite.config.js
├── Dockerfile                          # Multi-stage production container
├── .dockerignore
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- A free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/)

### 1. Clone the Repository
```bash
git clone https://github.com/HarshadKulkarni31/DocuLens.git
cd DocuLens
```

### 2. Configure Environment
Create `backend/.env` from the example:
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env` and insert your Gemini API Key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
MAX_FILE_SIZE_MB=15
TOP_K=4
CHUNK_SIZE=900
CHUNK_OVERLAP=120
```

### 3. Backend Setup
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Backend API will be running at `http://127.0.0.1:8000` (Interactive docs: `http://127.0.0.1:8000/docs`).

### 4. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Running Tests
Execute the automated test suite covering PDF validation, chunking, retrieval, and API endpoints:
```bash
cd backend
pytest tests -v
```

---

## 📡 API Contract

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health status and version check |
| `POST` | `/api/documents/extract` | Validates PDF and returns page-by-page text extracts |
| `POST` | `/api/documents` | Ingests PDF: extracts, chunks, generates embeddings, builds FAISS index |
| `POST` | `/api/documents/{id}/summary` | Generates executive summary and bulleted key points with Gemini |
| `POST` | `/api/documents/{id}/ask` | Performs vector search and generates grounded answer with verified citations |
| `DELETE` | `/api/documents/{id}` | Deletes document and frees index from memory |

---

## 🐳 Docker & Hugging Face Spaces Deployment

The included multi-stage `Dockerfile` compiles the React frontend and packages it inside the lightweight FastAPI container on port `7860`.

### Build & Run Locally with Docker:
```bash
docker build -t doculens .
docker run -p 7860:7860 -e GEMINI_API_KEY="your_api_key" doculens
```
Navigate to `http://localhost:7860`.

### Deploying to Hugging Face Spaces:
1. Create a new Space on [Hugging Face Spaces](https://huggingface.co/spaces) with **Docker** SDK.
2. In the Space settings, add a Secret named `GEMINI_API_KEY`.
3. Push this repository to your Space repository.

---

## ⚠️ Limitations & Scope
- **Scanned / Image PDFs**: DocuLens processes text-based PDFs. Image-only or scanned PDFs without an OCR text layer will return a clear message indicating selectable text is required.
- **In-Memory Storage**: Documents are indexed in-memory for the active session. Restarting the server resets the index.
- **API Keys**: Keys remain secure on the backend and are never exposed to the client or browser bundle.

---

## 📄 License
MIT License. Created for portfolio and hands-on document intelligence demonstration.
