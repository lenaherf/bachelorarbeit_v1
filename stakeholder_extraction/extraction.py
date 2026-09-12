from langchain_core.prompts.structured import StructuredPrompt
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import ChatOpenAI

from stakeholder_extraction.models import StakeholderView
from stakeholder_extraction.prompts import STAKEHOLDER_EXTRACTION_PROMPT

load_dotenv()

def extract_stakeholder_view(
        stakeholder: str,
        source_text: str,
) -> StakeholderView:
    llm = ChatOpenAI(
        model="gpt-5.2",
        temperature=0,
    )

    structured_llm = llm.with_structured_output(StakeholderView)

    user_prompt = f"""
Stakeholder:
{stakeholder}

Process description:
{source_text}
""".strip()

    result = structured_llm.invoke(
        [
            ("system", STAKEHOLDER_EXTRACTION_PROMPT),
            ("user", user_prompt),
        ]
    )

    return result