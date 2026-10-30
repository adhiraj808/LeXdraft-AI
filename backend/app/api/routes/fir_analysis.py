"""Legal Assistant endpoints - general legal Q&A for laypeople."""
import asyncio
import json
import logging
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.models.user import User
from app.core.rate_limit import public_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


def get_nlp(request: Request):
    return request.app.state.nlp_pipeline


class LegalQuestionRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=5000, description="Legal question from user")
    language: str = Field(default="english", pattern="^(english|hindi)$")
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


def get_fallback_response(question: str, language: str) -> dict:
    """Generate fallback response when AI is unavailable."""
    category = categorize_question(question)
    template = FALLBACK_RESPONSES.get(category, FALLBACK_RESPONSES["criminal"])
    
    # Simple IPC section extraction
    ipc_sections = re.findall(r'(?:Section|Sec\.?)\s*(\d+[A-Z]?)', question, re.IGNORECASE)
    
    return {
        "answer": template["answer"],
        "category": template["category"],
        "applicable_laws": template["applicable_laws"],
        "key_points": template["key_points"],
        "next_steps": template["next_steps"],
        "disclaimer": template["disclaimer"],
        "model_used": "template"
    }


def get_legal_qa_prompt(question: str, language: str, context: Optional[str] = None) -> str:
    return LEGAL_QA_PROMPT_TEMPLATE.replace("{{language}}", language).replace("{{question}}", question)


@router.post("/ask", response_model=LegalAnswerResponse)
async def ask_legal_question(
    request: Request,
    payload: LegalQuestionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Ask a legal question - get plain-language answer.
    Separate from draft generation - higher rate limit.
    """
    nlp = get_nlp(request)
    
    if not nlp or not nlp._loaded:
        raise HTTPException(status_code=503, detail="AI service not ready")
    
    question = payload.question.strip()
    if not question or len(question) < 5:
        raise HTTPException(status_code=400, detail="Question too short")
    
    language = payload.language or detect_language(payload.question)
    
    # Build context from user's cases if available
    context = payload.context
    
    # Try cloud LLM first
    generator = nlp.generator
    
    if generator.client and generator.client.available:
        try:
            prompt = build_legal_qa_prompt(payload.question, language, payload.context)
            response_text = generator.client.chat(
                messages=[
                    {"role": "system", "content": LEGAL_QA_SYSTEM_PROMPT.replace("{{language}}", language)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            if response_text:
                try:
                    result = json.loads(response_text)
                    result["model_used"] = f"{generator._provider}:{generator.client.model}"
                    return LegalAnswerResponse(**result)
                except json.JSONDecodeError:
                    logger.warning("AI returned invalid JSON, using fallback")
        except Exception as e:
            logger.warning(f"Cloud LLM failed for legal Q&A: {e}")
    
    # Fallback
    fallback = get_fallback_response(payload.question, payload.language)
    return LegalAnswerResponse(**fallback)


@router.post("/ask-stream")
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
    
    language = payload.language or detect_language(payload.question)
    
    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'message': 'Analyzing your question...'})}\n\n"
        
        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Understanding your question...'})}\n\n"
            await asyncio.sleep(0.3)
            
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Finding applicable laws...'})}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Preparing answer...'})}\n\n"
            await asyncio.sleep(0.5)
            
            # Get answer (non-streaming for now)
            result = await ask_legal_question(request, payload, current_user=Depends(get_current_user))
            
            yield f"data: {json.dumps({'type': 'result', 'data': result.model_dump()})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
            
        except Exception as e:
            logger.error(f"Legal Q&A stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Public endpoint (no auth) - with generous rate limit
@router.post("/ask-public")
@public_limiter.limit("20/minute")
async def ask_legal_question_public(
    request: Request,
    payload: LegalQuestionRequest,
):
    """Public legal Q&A - no auth, generous rate limit."""
    # Reuse logic but with mock user
    class MockUser:
        id = "public"
        username = "public"
        role = "public"
    
    return await ask_legal_question(request, payload, current_user=MockUser())


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