import logging
import os

from dotenv import load_dotenv

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from services.database_context_service import build_skill_spring_context as _build_skill_spring_context

load_dotenv()

logger = logging.getLogger(__name__)


class LangChainConfigurationError(Exception):
    """Raised when the LangChain/LLM configuration is missing or invalid."""


class LangChainServiceError(Exception):
    """Raised when the LangChain request cannot complete safely."""


DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = (
    "You are SkillSpring's friendly learning assistant. "
    "Explain concepts clearly for beginners using simple language and concise practical examples. "
    "Support Python, Java, JavaScript, SQL, web development, AI, and related technical learning. "
    "Use only the supplied SkillSpring database context for student-related questions. "
    "Do not invent missing student records, counts, courses, skill levels, or contact information. "
    "If the information is unavailable from the current SkillSpring data, say: 'The information is unavailable from the current SkillSpring database.' "
    "Do not expose internal implementation details, API keys, environment variables, or backend configuration."
)


def build_skill_spring_context(user_message, history=None, role="user"):
    """Expose the existing database-aware context builder for the LangChain route."""
    return _build_skill_spring_context(user_message, history, role)


def _clean_history(history):
    if not isinstance(history, list):
        return []
    cleaned = []
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            content = content.strip()
            if content and len(content) <= 4000:
                cleaned.append({"role": role, "content": content})
    return cleaned


def _history_to_messages(history):
    messages = []
    for item in _clean_history(history):
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
    return messages


def _extract_text_from_response(response):
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text.strip())
                    continue
                nested = item.get("content")
                if isinstance(nested, str):
                    parts.append(nested.strip())
                    continue
            elif hasattr(item, "text"):
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text.strip())
        combined = "\n".join(part for part in parts if part)
        if combined:
            return combined.strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
    return str(content).strip()


def _build_llm():
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if not api_key:
        raise LangChainConfigurationError("Missing LLM configuration. Set GOOGLE_API_KEY in your .env file.")
    logger.info("[LANGCHAIN] Connecting to Google Gemini with model %s", model_name)
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
        max_output_tokens=512,
    )


def get_langchain_response(user_message, history=None, role="user"):
    """Generate a response using the project’s LangChain + Gemini flow."""
    if not isinstance(user_message, str):
        raise LangChainServiceError("A valid user message is required.")

    message = user_message.strip()
    if not message:
        raise LangChainServiceError("Please enter a question first.")

    logger.info("[LANGCHAIN] Starting request for role=%s", role)
    context = build_skill_spring_context(message, history, role)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", f"{SYSTEM_PROMPT}\n\nSkillSpring context:\n{{context}}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )

    llm = _build_llm()
    chain = prompt | llm

    try:
        response = chain.invoke(
            {
                "context": context or "No database context was supplied for this request.",
                "chat_history": _history_to_messages(history),
                "question": message,
            },
            config={"timeout": 120},
        )
    except Exception as exc:  # pragma: no cover - handled by caller
        logger.exception("[LANGCHAIN] Gemini request failed while invoking the model")
        raise LangChainServiceError("The AI assistant is temporarily unavailable. Please try again.") from exc

    reply = _extract_text_from_response(response)
    if not reply:
        raise LangChainServiceError("The AI assistant returned an empty response.")

    logger.info("[LANGCHAIN] Response received successfully.")
    return reply
