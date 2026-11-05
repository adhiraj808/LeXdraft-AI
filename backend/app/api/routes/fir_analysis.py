"""Legal Assistant endpoints - general legal Q&A for laypeople."""
import asyncio
import json
import logging
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def get_nlp(request: Request):
    return request.app.state.nlp_pipeline


class LegalQuestionRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=5000, description="Legal question from user")
    # Empty string = auto-detect (Devanagari script -> Hindi, otherwise English).
    language: str = Field(default="", pattern="^(english|hindi|)$")
    context: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        # Remove potential prompt injection attempts
        dangerous_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+previous\s+instructions",
            r"forget\s+everything",
            r"system\s+prompt",
            r"you\s+are\s+now",
            r"act\s+as\s+",
            r"pretend\s+to\s+be",
            r"roleplay\s+as",
        ]
        import re
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Input contains potentially malicious content")
        # Sanitize: remove control characters, limit length
        v = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', v)
        return v.strip()[:5000]

    @field_validator("context")
    @classmethod
    def sanitize_context(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        import re
        v = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', v)
        return v.strip()[:2000]


class LegalAnswerResponse(BaseModel):
    answer: str
    category: str
    applicable_laws: List[str]
    key_points: List[str]
    next_steps: List[str]
    disclaimer: str
    model_used: str


# System prompt for general legal Q&A
LEGAL_QA_SYSTEM_PROMPT = """You are a legal aid assistant helping a common person understand their legal situation in India.

The user has NO legal background. They may ask about:
- FIRs, arrests, bail, court procedures
- Property disputes, family matters, contracts
- "Will I go to jail?", "What happens next?", "What are my rights?"
- Previous similar cases/precedents
- Any legal confusion they have

Your task: Give CLEAR, SIMPLE, PRACTICAL answers in everyday language.

Guidelines:
1. Use SIMPLE words, short sentences, everyday language (Hindi/English as requested)
2. Explain legal terms in brackets if you must use them
3. Be empathetic but factual - no false hope, no unnecessary fear
4. Structure: Direct answer → Key points → Practical steps → Disclaimer
4. NEVER give definitive legal advice - always say "consult a lawyer"
5. If you don't know, say "I don't have enough info - consult a lawyer"

Language: {{language}} (respond in this language)

Output format (JSON):
{
  "answer": "Direct, plain-language answer to their question",
  "category": "Criminal / Civil / Family / Property / Other",
  "applicable_laws": ["IPC 302", "CrPC 167", "Hindu Marriage Act 13", etc.],
  "key_points": ["Key point 1", "Key point 2", ...],
  "next_steps": ["Step 1", "Step 2", "Step 3"],
  "disclaimer": "This is information only, not legal advice. Consult a qualified lawyer.",
  "model_used": "template"
}"""

LEGAL_QA_PROMPT_TEMPLATE = """Answer this legal question in simple {{language}} for a person with NO legal background.

QUESTION: {{question}}

{% if context %}CONTEXT: {{context}}{% endif %}

Respond ONLY with valid JSON matching the specified format. Do not include any extra text."""


def build_legal_qa_prompt(question: str, language: str, context: Optional[str] = None) -> str:
    prompt = LEGAL_QA_PROMPT_TEMPLATE.replace("{{language}}", language).replace("{{question}}", question)
    if context:
        prompt = prompt.replace("{% if context %}CONTEXT: {{context}}{% endif %}", f"CONTEXT: {context}")
    else:
        prompt = prompt.replace("{% if context %}CONTEXT: {{context}}{% endif %}", "")
    return prompt


# Common legal categories and fallback responses
LEGAL_CATEGORIES = {
    "criminal": ["arrest", "fir", "arrest", "police", "jail", "bail", "charge", "crime", "accused", "accused", "murder", "theft", "assault", "fraud", "cheating", "dowry", "498a", "302", "307", "376", "354", "323", "324", "420", "406", "498a"],
    "family": ["divorce", "marriage", "maintenance", "alimony", "custody", "child", "husband", "wife", "domestic violence", "dowry", "separation", "mutual consent"],
    "property": ["property", "land", "house", "rent", "tenant", "landlord", "eviction", "possession", "title", "sale deed", "partition", "inheritance", "will", "succession"],
    "contract": ["contract", "agreement", "breach", "cheque", "bounce", "payment", "recovery", "damages", "specific performance", "notice"],
    "consumer": ["consumer", "defective", "service", "warranty", "refund", "complaint", "forum"],
    "employment": ["employment", "termination", "salary", "wages", "pf", "gratuity", "resignation", "appointment"],
}


def categorize_question(question: str) -> str:
    q_lower = question.lower()
    scores = {}
    for cat, keywords in LEGAL_CATEGORIES.items():
        scores[cat] = sum(1 for kw in keywords if kw in q_lower)
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "general"


def detect_language(text: str) -> str:
    """Simple heuristic - if contains Devanagari, treat as Hindi"""
    if re.search(r'[\u0900-\u097F]', text):
        return "hindi"
    return "english"


# Fallback templates for when AI is unavailable
FALLBACK_RESPONSES = {
    "criminal": {
        "answer": "Based on what you've described, this sounds like a criminal matter. The police have registered an FIR and are investigating. Whether jail happens depends on: (1) whether the offence is bailable or non-bailable, (2) whether you get anticipatory bail, (3) the evidence against you. For serious offences like murder (302), attempt to murder (307), rape (376) - these are non-bailable and serious. For minor offences, bail is usually granted.",
        "category": "Criminal",
        "applicable_laws": ["IPC (Indian Penal Code)", "CrPC (Criminal Procedure Code)"],
        "key_points": [
            "FIR is just the start of investigation, not proof of guilt",
            "You have the right to remain silent and get a lawyer",
            "Anticipatory bail (Section 438 CrPC) can prevent arrest",
            "Bail depends on offence being bailable/non-bailable"
        ],
        "next_steps": [
            "Contact a criminal lawyer immediately",
            "Apply for anticipatory bail if arrest is likely",
            "Do not tamper with evidence or threaten witnesses",
            "Exercise right to silence - anything you say can be used against you"
        ],
        "disclaimer": "This is general information only, not legal advice. Consult a qualified criminal lawyer immediately.",
        "model_used": "template"
    },
    "family": {
        "answer": "Family matters like divorce, maintenance, or child custody are governed by personal laws (Hindu Marriage Act, Special Marriage Act, etc.) and the CrPC. The process and outcome depend on whether it's mutual consent or contested. Maintenance (Section 125 CrPC) is a right for wives/children/parents who cannot maintain themselves.",
        "category": "Family",
        "applicable_laws": ["Hindu Marriage Act", "Special Marriage Act", "CrPC 125", "Guardians and Wards Act"],
        "key_points": [
            "Mutual consent divorce is faster (6-18 months)",
            "Contested divorce takes longer (2-5 years)",
            "Maintenance is a legal right, not charity",
            "Child welfare is paramount in custody decisions"
        ],
        "next_steps": [
            "Consult a family lawyer",
            "Gather marriage certificate, income proofs, expense details",
            "Consider mediation before litigation",
            "Document all relevant facts"
        ],
        "disclaimer": "This is general information only, not legal advice. Consult a qualified family lawyer.",
        "model_used": "template"
    },
    "property": {
        "answer": "Property disputes involve title, possession, tenancy, or inheritance. Key laws: Transfer of Property Act, Registration Act, Rent Control Acts, Hindu Succession Act. Whether you can be evicted or lose property depends on documents, possession, and applicable law.",
        "category": "Property",
        "applicable_laws": ["Transfer of Property Act", "Registration Act", "Rent Control Act", "Hindu Succession Act"],
        "key_points": [
            "Registration of sale deed is mandatory for immovable property",
            "Possession is strong evidence of ownership",
            "Tenants have protection under Rent Control Acts",
            "Inheritance follows personal law (Hindu/Muslim/Christian)"
        ],
        "next_steps": [
            "Gather all title documents, sale deeds, tax receipts",
            "Check if property is registered",
            "Consult a property lawyer",
            "Consider title search/verification"
        ],
        "disclaimer": "This is general information only, not legal advice. Consult a qualified property lawyer.",
        "model_used": "template"
    },
    "contract": {
        "answer": "Contract disputes (cheque bounce, breach, recovery) are governed by Contract Act, Negotiable Instruments Act. Cheque bounce (Section 138 NI Act) is criminal offence with up to 2 years jail. Recovery suits are civil. Key: limitation period (3 years for contracts, 30 days for cheque bounce notice).",
        "category": "Contract/Commercial",
        "applicable_laws": ["Indian Contract Act", "Negotiable Instruments Act (Section 138)", "Specific Relief Act"],
        "key_points": [
            "Written contract is stronger evidence than oral",
            "Cheque bounce: 30-day notice, then 30 days to file complaint",
            "Limitation: 3 years for contract breach",
            "Specific performance only for unique goods/property"
        ],
        "next_steps": [
            "Gather contract, correspondence, payment proofs",
            "For cheque bounce: send legal notice within 30 days",
            "File recovery suit within limitation period",
            "Consult a commercial lawyer"
        ],
        "disclaimer": "This is general information only, not legal advice. Consult a qualified commercial lawyer.",
        "model_used": "template"
    },
}


# Used when the question fits none of the specific templates above (consumer, employment,
# general questions...) - showing the *criminal* template for those would be misleading.
FALLBACK_RESPONSES["general"] = {
    "answer": "The AI assistant is not available right now, so this is general guidance only. Legal outcomes depend on the exact facts, the documents you hold and the law that applies to your situation. Write down the key facts and dates, keep every document, notice and message, and do not sign or admit anything before taking advice.",
    "category": "Other",
    "applicable_laws": [],
    "key_points": [
        "Keep copies of all documents, notices, receipts and messages",
        "Note down dates, names and amounts while memory is fresh",
        "Time limits (limitation periods) apply to most legal remedies",
        "Free legal aid is available through the District Legal Services Authority (DLSA) if you cannot afford a lawyer"
    ],
    "next_steps": [
        "Consult a qualified lawyer for your specific situation",
        "Contact your District Legal Services Authority (NALSA helpline 15100) if you need free legal aid",
        "Collect and organise all relevant documents before the meeting"
    ],
    "disclaimer": "This is general information only, not legal advice. Consult a qualified lawyer.",
    "model_used": "template"
}


def get_fallback_response(question: str, language: str) -> dict:
    """Generate fallback response when AI is unavailable."""
    category = categorize_question(question)
    template = FALLBACK_RESPONSES.get(category, FALLBACK_RESPONSES["general"])

    return {
        "answer": template["answer"],
        "category": template["category"],
        "applicable_laws": template["applicable_laws"],
        "key_points": template["key_points"],
        "next_steps": template["next_steps"],
        "disclaimer": template["disclaimer"],
        "model_used": "template"
    }


def _parse_model_json(text: str) -> Optional[dict]:
    """Parse a JSON object from model output, tolerating ```json fences and surrounding prose."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _as_str_list(value) -> List[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return []


def _build_answer(data: dict, model_used: str) -> LegalAnswerResponse:
    """Coerce model output (which varies a lot between models) into the response schema."""
    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise ValueError("model answer is empty")
    return LegalAnswerResponse(
        answer=answer,
        category=str(data.get("category") or "Other"),
        applicable_laws=_as_str_list(data.get("applicable_laws")),
        key_points=_as_str_list(data.get("key_points")),
        next_steps=_as_str_list(data.get("next_steps")),
        disclaimer=str(data.get("disclaimer") or FALLBACK_RESPONSES["general"]["disclaimer"]),
        model_used=model_used,
    )


async def _answer_question(request: Request, payload: LegalQuestionRequest) -> LegalAnswerResponse:
    """Shared implementation of the Q&A endpoints (the endpoints only add auth + rate limits)."""
    nlp = get_nlp(request)
    if not nlp._loaded:
        raise HTTPException(status_code=503, detail="AI service not ready")

    language = payload.language or detect_language(payload.question)
    generator = nlp.generator

    if generator and generator.client and generator.client.available:
        try:
            messages = [
                {"role": "system", "content": LEGAL_QA_SYSTEM_PROMPT.replace("{{language}}", language)},
                {"role": "user", "content": build_legal_qa_prompt(payload.question, language, payload.context)},
            ]
            # chat() is a blocking HTTP call: run it in a worker thread, not on the event loop.
            response_text = await asyncio.to_thread(
                generator.client.chat, messages, temperature=0.3, max_tokens=settings.LLM_MAX_TOKENS
            )
            data = _parse_model_json(response_text) if response_text else None
            if data is not None:
                return _build_answer(data, f"{generator._provider}:{generator.client.model}")
            logger.warning("AI returned no usable JSON for legal Q&A, using fallback")
        except Exception as e:
            logger.warning(f"Cloud LLM failed for legal Q&A: {type(e).__name__}: {e}")

    return LegalAnswerResponse(**get_fallback_response(payload.question, language))


@router.post("/ask", response_model=LegalAnswerResponse)
@limiter.limit(settings.RATE_LIMIT_QA)
async def ask_legal_question(
    request: Request,
    payload: LegalQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Ask a legal question - get plain-language answer.
    Separate from draft generation - higher rate limit.
    """
    return await _answer_question(request, payload)


@router.post("/ask-stream")
@limiter.limit(settings.RATE_LIMIT_QA)
async def ask_legal_question_stream(
    request: Request,
    payload: LegalQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream legal Q&A response."""
    nlp = get_nlp(request)

    if not nlp or not nlp._loaded:
        raise HTTPException(status_code=503, detail="AI service not ready")

    question = payload.question.strip()
    if not question or len(question) < 5:
        raise HTTPException(status_code=400, detail="Question too short")

  # executes correctly but mypy/ruff flag the unused variable because the
  # stream handler builds SSE phases here and the actual answer is delegated
  # to _answer_question (which re-detects the language). Keep the assignment
  # explicit so we do not call detect_language twice by accident.
    _ = payload.language or detect_language(payload.question)

    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'message': 'Analyzing your question...'})}\n\n"

        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Understanding your question...'})}\n\n"
            await asyncio.sleep(0.3)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Finding applicable laws...'})}\n\n"
            await asyncio.sleep(0.5)

            yield f"data: {json.dumps({'type': 'progress', 'message': 'Preparing answer...'})}\n\n"
            await asyncio.sleep(0.5)

            # Get answer (non-streaming for now): use the shared implementation
            # directly. (Calling the ask_legal_question endpoint function with
            # current_user=Depends(...) would pass a Depends object, not a user.)
            result = await _answer_question(request, payload)

            yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        except Exception as e:
            # Never echo exception text to the client: it can contain internal
            # endpoint URLs, provider details or stack fragments.
            logger.error(f"Legal Q&A stream error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong while preparing your answer. Please try again.'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Anonymous legal Q&A spends LLM credits for anyone who can reach the server.
# It is disabled unless PUBLIC_QA_ENABLED=true (see app.core.config).
@router.post("/ask-public")
@limiter.limit(settings.RATE_LIMIT_PUBLIC_QA)
async def ask_legal_question_public(
    request: Request,
    payload: LegalQuestionRequest,
):
    """Public legal Q&A - no auth, off by default."""
    if not settings.PUBLIC_QA_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    return await _answer_question(request, payload)


# Rate limit status endpoint
@router.get("/rate-limit-status")
async def rate_limit_status(request: Request):
    """Check current rate limit status for legal Q&A."""
    return {
        "legal_qa": {
            "limit": "100 per 15 minutes",
            "separate_from_draft_generation": True
        },
        "draft_generation": {
            "limit": "25 per 15 minutes",
            "endpoint": "/api/v1/cases/prompt"
        }
    }
