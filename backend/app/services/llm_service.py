import logging
from typing import List, Dict, Any, Optional
import requests

from app.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.api_url = settings.LLM_API_URL
        self.model = settings.LLM_MODEL

    def generate_evidence_summary(
        self,
        modification_alert_id: str,
        category: str,
        detection_date: str,
        change_score: float,
        evidence_list: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a concise, factual summary of uploaded evidence documents and photographs.
        Strictly adheres to documented facts without inventing inferences or approving decisions.
        """
        if not evidence_list:
            return (
                f"No supporting evidence has been uploaded for case {modification_alert_id} yet. "
                "The potential modification remains flagged based solely on the satellite difference signal."
            )

        # If live LLM API key provided
        if self.api_key and self.api_key != "demo":
            try:
                system_prompt = (
                    "You are an evidence summarizer assistant for property modification verification. "
                    "Summarize the provided evidence items factually. Do not approve or reject any modification. "
                    "Do not make claims not supported by the evidence descriptions. Keep it under 150 words."
                )
                user_msg = (
                    f"Alert ID: {modification_alert_id}\n"
                    f"Suspected Category: {category}\n"
                    f"Detection Date: {detection_date}\n"
                    f"Change Score: {change_score}%\n"
                    f"Evidence Count: {len(evidence_list)}\n"
                    f"Items:\n" + "\n".join([
                        f"- [{item.get('category')}] {item.get('original_filename')}: {item.get('description', 'No description')} (Uploaded: {item.get('uploaded_at')})"
                        for item in evidence_list
                    ])
                )
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ],
                    "max_tokens": 250,
                    "temperature": 0.2
                }
                resp = requests.post(self.api_url, json=payload, headers=headers, timeout=12.0)
                if resp.status_code == 200:
                    summary = resp.json()["choices"][0]["message"]["content"].strip()
                    return summary
            except Exception as e:
                logger.warning(f"LLM API summarizer call failed: {e}")

        # Local deterministic evidence summarizer
        categories = {}
        for ev in evidence_list:
            cat = ev.get("category", "Document")
            categories[cat] = categories.get(cat, 0) + 1

        summary_parts = [
            f"Case {modification_alert_id} ({category}) includes {len(evidence_list)} submitted supporting item(s)."
        ]
        
        breakdown = ", ".join([f"{count} {cat.lower()}(s)" for cat, count in categories.items()])
        summary_parts.append(f"Evidence inventory comprises: {breakdown}.")

        # Check for specific evidence categories
        has_permit = any(ev.get("category") == "Building Permit" for ev in evidence_list)
        has_photo = any(ev.get("category") == "Photograph" for ev in evidence_list)
        has_invoice = any(ev.get("category") == "Contractor Invoice" for ev in evidence_list)

        if has_permit and has_photo:
            summary_parts.append(
                "Submissions include both formal municipal permit documentation and ground-level photographs, "
                "providing corroboration between planned structural work and physical execution."
            )
        elif has_photo and not has_permit:
            summary_parts.append(
                "Ground-level photographs have been submitted. Official municipal permits or contractor invoices "
                "have not yet been attached to the case."
            )
        elif has_permit and not has_photo:
            summary_parts.append(
                "Building permits have been provided. Additional post-construction photographs may be required "
                "to confirm final physical completion."
            )

        summary_parts.append(
            f"The optical change score is {change_score}%. Ready for human reviewer evaluation."
        )

        return " ".join(summary_parts)

llm_service = LLMService()
