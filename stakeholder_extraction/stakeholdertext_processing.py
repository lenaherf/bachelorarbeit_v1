from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

llm = ChatOpenAI(
    model="gpt-5.2",
    temperature=0,
)

LANGUAGE_CORRECTION_PROMPT = """
You prepare a stakeholder's process description for further analysis.

Correct only:
- spelling errors
- grammatical errors
- punctuation errors
- clearly malformed sentence structure

Strict rules:
- Preserve all process information.
- Do not add, remove, infer, or reinterpret information.
- Preserve the stakeholder's terminology.
- Preserve first-person statements.
- Preserve uncertainty, ambiguity, and missing information.
- Do not replace role names with synonyms.
- Do not resolve unclear responsibilities.
- Return only the corrected text.

Stakeholder:
{stakeholder}

Original text:
{source_text}
"""

ACTIVE_SENTENCE_PROMPT = """
You prepare a stakeholder's process description for
subject-oriented process modeling.

Rewrite the text into clear active sentences whenever the acting
subject is explicitly stated or can be determined unambiguously from
the stakeholder's first-person perspective.

Rules:
- Preserve all process information and the original meaning.
- Do not add, remove, or infer process steps.
- Do not invent subjects, messages, activities, responsibilities,
  decisions, or ordering.
- Interpret "I", "me", "we", and "us" as the submitting stakeholder:
  "{stakeholder}".
- Replace pronouns such as "it", "this", "they", and "them" with the process
  element to which they clearly refer.
- Replace first-person references with the stakeholder's role name
  where this is unambiguous.
- Prefer one process-relevant action or interaction per sentence.
- Keep the original order of events.
- Preserve the stakeholder's terminology.
- Convert passive sentences into active sentences only when the actor
  is known.
- Express each distinct process action or message exchange as a separate sentence.
- If the actor is not known, preserve the passive construction.
- Do not turn processed business objects into messages unless an
  exchange between two subjects is described.
- Return only the rewritten process description.
- Repeat the process element instead of using a pronoun when the reference is
  unambiguous.
- Do not replace a pronoun if its referent is ambiguous.
- Preserve explicit sequence markers such as "after", "before",
  "then", and "only after" when rewriting sentences.
- Preserve explicit statements that identify the beginning or ending
  of a stakeholder's behaviour. Do not reduce them to sentence order.

Stakeholder:
{stakeholder}

Corrected text:
{corrected_text}
"""

def correct_language(
        stakeholder: str,
        source_text: str,
) -> str:
    prompt = LANGUAGE_CORRECTION_PROMPT.format(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    response = llm.invoke(prompt)

    return response.content.strip()

def normalize_process_text(
        stakeholder: str,
        corrected_text: str,
) -> str:
    prompt = ACTIVE_SENTENCE_PROMPT.format(
        stakeholder=stakeholder,
        corrected_text=corrected_text,
    )

    response = llm.invoke(prompt)

    return response.content.strip()

def prepare_stakeholder_text(
        stakeholder: str,
        source_text: str,
) -> tuple[str, str]:
    corrected_text = correct_language(
        stakeholder=stakeholder,
        source_text=source_text,
    )

    prepared_text = normalize_process_text(
        stakeholder=stakeholder,
        corrected_text=corrected_text,
    )

    return corrected_text, prepared_text
