# DocuMind AI 🧠

A production-grade AI research assistant with RAG (Retrieval-Augmented Generation).
Upload documents, ask questions, get answers grounded in your content.

## Features
- 📄 Multi-format support: PDF, DOCX, PPTX, Excel, CSV
- 🔗 Web URL scraping and indexing
- 🧠 RAG pipeline: ChromaDB + FastEmbed + Groq LLaMA 3.3 70B
- 🌐 Web search fallback (DuckDuckGo + Wikipedia)
- 💬 Persistent conversation history
- 🎨 Dark mode ChatGPT-style UI

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite |
| Backend | FastAPI + Python |
| LLM | Groq (LLaMA 3.3 70B) |
| Embeddings | FastEmbed (BAAI/bge-small-en-v1.5) |
| Vector DB | ChromaDB |
| Database | SQLite + SQLAlchemy |
| File Parsing | PyMuPDF, python-docx, python-pptx, pandas |

## Setup

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
# Add your keys to .env
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
GROQ_API_KEY=your_groq_key_here
GOOGLE_API_KEY=your_google_key_here

## Architecture
User → React UI → FastAPI → RAG Pipeline → Groq LLM
                          ↓
                    ChromaDB (vectors)
                    SQLite (history)
                    Web Search (fallback)
