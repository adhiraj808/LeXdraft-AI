# AI-Powered Legal Case Drafting System

An intelligent full-stack platform that accepts unstructured case facts, classifies the case type, extracts legal entities via NER, and generates professionally formatted legal drafts using transformer-based language models.

## Features

- **Automated Case Classification**: Automatically identifies the type of legal case (e.g., Civil, Criminal, Divorce) from raw facts.
- **Named Entity Recognition (NER)**: Extracts critical entities like Plaintiffs, Defendants, Court Name, and Dates.
- **Dynamic Draft Generation**: Uses Large Language Models (LLMs) to generate structured legal drafts based on extracted entities and case facts.
- **PDF Export**: Generates professional PDF versions of the legal drafts.
- **Modern Dashboard**: Clean and intuitive UI for managing cases and reviewing drafts.

## Tech Stack

- **Backend**: FastAPI (Python), SQLAlchemy, PostgreSQL, Redis, Pydantic.
- **Frontend**: React.js, TailwindCSS, Vite.
- **NLP/ML**: Transformers (Hugging Face), Spacy, LangChain/ChromaDB for RAG.
- **Infrastructure**: Docker, Docker Compose.

## Project Structure

```
legal_draft_system/
├── backend/                  # FastAPI backend + ML/NLP
│   ├── app/
│   │   ├── api/routes/       # API route handlers
│   │   ├── core/             # Config, security, logging
│   │   ├── db/               # Database connections
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── nlp/              # NLP pipeline
│   │   └── utils/            # PDF export, helpers
│   ├── tests/
│   ├── main.py
│   └── requirements.txt
├── frontend/                 # React.js frontend
│   └── src/
├── docker-compose.yml
└── .env.example
```

## Setup & Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ (for local development)
- Node.js 18+ (for local development)

### Quick Start with Docker

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/legal-draft-system.git
   cd legal-draft-system
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```

3. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

- Frontend: [http://localhost:5173](http://localhost:5173)
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### Local Development Setup

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## License

MIT License — see [LICENSE.md](./LICENSE.md).
Source: [adhiraj808/LeXdraft-AI](https://github.com/adhiraj808/LeXdraft-AI)
