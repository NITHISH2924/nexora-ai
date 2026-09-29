import re
import logging
from typing import Optional, Dict, Any

from backend.app.models import WritingAssistRequest, WritingAssistResponse
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("services.writing")

class WritingService:
    """Service providing AI writing assistance, translation, grammar correction, email, resume, and cover letter generation."""

    def _count_words(self, text: Optional[str]) -> int:
        if not text:
            return 0
        return len(re.findall(r'\b\w+\b', text))

    async def assist_writing(self, req: WritingAssistRequest) -> WritingAssistResponse:
        """
        Execute AI Writing Assistance:
        - rewrite: Paraphrase, improve tone, flow, and vocabulary
        - grammar: Fix grammar, spelling, punctuation with diff
        - summarize: Condense into executive summary
        - expand: Flesh out notes into structured, comprehensive text
        - shorten: Condense text while keeping core impact
        - professional: Polish for executive/business standards
        - email: Draft tailored professional emails
        - resume: Craft high-impact resume experience bullets (action verbs + metrics)
        - cover_letter: Tailor persuasive cover letter for role/company
        - translate: Translate text accurately to target language
        """
        action = req.action
        text_input = (req.text or "").strip()
        tone = req.tone or "professional"
        target_lang = req.targetLanguage or "English"
        recipient = req.recipient or "Colleague / Client"
        job_title = req.jobTitle or "Software Engineer"
        company_name = req.companyName or "Target Company"

        action_instructions = {
            "rewrite": (
                f"You are a master editor. Rewrite the following text to maximize clarity, elegance, engagement, and flow.\n"
                f"Tone: {tone.capitalize()}\n\n"
                f"Original Text:\n\"{text_input}\"\n\n"
                f"Provide:\n"
                f"1. **Polished Version**: The rewritten text.\n"
                f"2. **Alternative Variations**: (e.g. Concise, Persuasive, Academic).\n"
                f"3. **Key Improvements Made**: Brief summary of stylistic adjustments."
            ),
            "grammar": (
                f"You are an expert copyeditor. Perform comprehensive proofreading and grammar correction on the text:\n\n"
                f"Input Text:\n\"{text_input}\"\n\n"
                f"Format as:\n"
                f"1. **Corrected Text**: The clean, error-free version.\n"
                f"2. **Corrections Breakdown Table**: (Original Segment | Corrected | Reason for Change).\n"
                f"3. **Grammar & Readability Score**: Overall rating."
            ),
            "summarize": (
                f"You are an executive communications specialist. Summarize the following text concisely in a {tone} tone:\n\n"
                f"Text:\n\"{text_input}\"\n\n"
                f"Format as:\n"
                f"1. **Executive TL;DR**: 1-2 sentence core message.\n"
                f"2. **Key Takeaways**: High-impact bullet points.\n"
                f"3. **Action Items / Conclusions**."
            ),
            "expand": (
                f"You are a skilled content strategist. Expand the following outline / draft into a comprehensive, well-structured piece in a {tone} tone:\n\n"
                f"Draft / Notes:\n\"{text_input}\"\n\n"
                f"Flesh out each point with detailed explanations, supporting arguments, practical examples, and clean transitions."
            ),
            "shorten": (
                f"You are a concise communications editor. Shorten the following text by approximately 50%, removing fluff and redundancy while keeping all vital facts and meaning in a {tone} tone:\n\n"
                f"Original Text:\n\"{text_input}\"\n\n"
                f"Provide the condensed, punchy version."
            ),
            "professional": (
                f"You are a C-suite corporate communications advisor. Transform the following text into polished, high-caliber professional business writing:\n\n"
                f"Input:\n\"{text_input}\"\n\n"
                f"Ensure authoritative tone, clear executive messaging, confident diction, and impeccable etiquette."
            ),
            "email": (
                f"You are an expert business communicator. Draft an effective, polished professional email.\n"
                f"Recipient: {recipient}\n"
                f"Tone: {tone.capitalize()}\n"
                f"Context / Goal:\n\"{text_input or 'Follow up on technical proposal and schedule next steps'}\"\n\n"
                f"Provide:\n"
                f"1. **Subject Line Options**: (3 compelling, high open-rate options).\n"
                f"2. **Email Body**: Complete email with greeting, structured message, call to action (CTA), and professional sign-off."
            ),
            "resume": (
                f"You are an elite tech career coach. Transform the following experience notes into high-impact, ATS-optimized resume bullet points for the role of '{job_title}':\n\n"
                f"Experience Details:\n\"{text_input or 'Led backend development, built APIs, reduced database latency, worked with team'}\"\n\n"
                f"Guidelines:\n"
                f"- Use Google XYZ formula: 'Accomplished [X], as measured by [Y], by doing [Z]'.\n"
                f"- Start every bullet with strong action verbs (Architected, Engineered, Optimized, Spearheaded).\n"
                f"- Include quantifiable metrics and industry keywords."
            ),
            "cover_letter": (
                f"You are a career consultant. Write a compelling, tailored cover letter for the role of '{job_title}' at '{company_name}'.\n"
                f"Candidate Background & Highlights:\n\"{text_input or 'Experienced full-stack developer with expertise in scalable systems and AI integrations'}\"\n\n"
                f"Format as a complete professional cover letter with opening hook, value proposition, relevant achievements, and confident closing."
            ),
            "translate": (
                f"You are a master literary and technical translator. Translate the following text into **{target_lang}** preserving tone ({tone}), cultural nuances, and technical accuracy:\n\n"
                f"Source Text:\n\"{text_input}\"\n\n"
                f"Provide:\n"
                f"1. **Accurate Translation**: Natural, high-fluency translation in {target_lang}.\n"
                f"2. **Pronunciation / Transliteration** (if applicable).\n"
                f"3. **Contextual & Cultural Notes**."
            )
        }

        chosen_prompt = action_instructions.get(action, action_instructions["rewrite"])
        system_prompt = f"You are NEXORA AI Advanced Writing & Communications Studio, providing impeccable editorial and multilingual intelligence."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chosen_prompt}
        ]

        ai_result, model_used = await ai_manager.generate_response(
            messages=messages,
            model=req.model,
            system_prompt=system_prompt
        )

        orig_count = self._count_words(text_input)
        res_count = self._count_words(ai_result)

        return WritingAssistResponse(
            action=action,
            result=ai_result,
            originalWordCount=orig_count,
            resultWordCount=res_count,
            inputWords=orig_count,
            outputWords=res_count,
            model=model_used
        )

writing_service = WritingService()
