import json
import logging
import datetime
from typing import Dict
from utils.ai_helper import ai_text

log = logging.getLogger(__name__)

def run_editorial_board(topic: str, language: str = "pt") -> Dict[str, str]:
    """
    Runs a multi-agent simulation to generate a high-quality video script.
    Agents: Director, Fact-Checker, and Copywriter.
    """
    log.info(f"Starting Multi-Agent Editorial Board for topic: {topic} in language: {language}")
    
    current_month = datetime.datetime.now().strftime("%B")
    
    import random
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[1]
    hooks_file = ROOT / "_data" / "hook_formulas.json"
    hook_injection = ""
    if hooks_file.exists():
        try:
            with open(hooks_file, "r", encoding="utf-8") as f:
                hooks = json.load(f)
            if hooks:
                selected_hook = random.choice(hooks).get("formula", "")
                if selected_hook:
                    hook_injection = f"\n    COMPETITOR VIRAL DNA FOUND! You MUST structure the hook using this psychological template: '{selected_hook}'\n"
        except Exception:
            pass

    
    # 1. Director Agent
    director_prompt = f"""
    You are the Creative Director of an award-winning nature documentary channel.
    The next topic is: {topic}.
    
    WORLD STATE CONTEXT: We are currently in the month of {current_month}.
    If possible, subtly tailor the hook to relate to phenomena, weather, or animal behaviors typical for this time of year globally.
    
    Provide exactly ONE brilliant, highly engaging angle/hook to explore this topic.
    The angle should be surprising, avoiding common clichés.
    Return ONLY a JSON object with this schema:
    {{"angle": "The core surprising concept", "rationale": "Why this works for retention"}}
    """
    director_pitch_str = ai_text(director_prompt, timeout=25, json_mode=True)
    
    try:
        if director_pitch_str.startswith("```json"): director_pitch_str = director_pitch_str.strip("`").replace("json\n", "", 1)
        director_pitch = json.loads(director_pitch_str)
        angle = director_pitch.get("angle", topic)
    except Exception as e:
        log.warning(f"Director agent failed to output JSON. Fallback to topic. Error: {e}")
        angle = topic

    log.info(f"Director selected angle: {angle}")
    
    # 2. Fact-Checker Agent
    fact_prompt = f"""
    You are a meticulous Biologist and Fact-Checker.
    The Director proposed this angle: "{angle}" for the topic "{topic}".
    Validate this angle. If it's scientifically inaccurate or exaggerated, correct it.
    If it's true, add one fascinating biological detail that proves it.
    Return ONLY a JSON object with this schema:
    {{"validated_angle": "The biologically accurate angle", "fascinating_fact": "One amazing true detail"}}
    """
    fact_str = ai_text(fact_prompt, timeout=25, json_mode=True)
    
    try:
        if fact_str.startswith("```json"): fact_str = fact_str.strip("`").replace("json\n", "", 1)
        fact_data = json.loads(fact_str)
        validated = fact_data.get("validated_angle", angle)
        fact = fact_data.get("fascinating_fact", "")
    except Exception as e:
        log.warning(f"Fact-Checker failed to output JSON. Error: {e}")
        validated = angle
        fact = ""

    log.info(f"Fact-Checker validated: {validated} with fact: {fact}")

    # 3. Copywriter Agent (Final Script)
    copywriter_prompt = f"""
    You are a master scriptwriter and SEO expert for a viral YouTube Shorts channel.
    Topic: {topic}
    Scientifically Validated Angle: {validated}
    Biological Fact: {fact}
    Target Language: {language}
    {hook_injection}
    
    Write a brilliant, short script that perfectly synchronizes with a fast-paced video clip.
    RULES FOR ALGORITHMIC VIRALITY (MANDATORY):
    - The script MUST be in the Target Language ({language}).
    - Exactly 3 sentences. No more, no less.
    - Keep sentences short and rhythmic (maximum 8-12 words per sentence).
    - CONTROVERSIAL HOOK: Sentence 1 must be highly controversial, mysterious, or challenge a common belief to spark comments (e.g. "Forget everything you knew about...").
    - INFINITE LOOP TRAP: The LAST word of Sentence 3 must perfectly connect grammatically with the FIRST word of Sentence 1, so when the video loops, it sounds like a continuous sentence.
    
    Example of Infinite Loop:
    (Sentence 3 ends with): "...and that is the exact reason why"
    (Sentence 1 starts with): "the great white shark never stops swimming."
    
    Sentence 1: The controversial hook (Start of the loop).
    Sentence 2: The explanation (using the biological fact).
    Sentence 3: The payoff/conclusion (End of the loop, leading directly into Sentence 1).
    
    Return ONLY a JSON object with this schema:
    {{
        "title": "A short, highly clickbaity SEO title (under 50 chars)",
        "script": "The full 3-sentence loopable script in {language}",
        "hook": "The hook (sentence 1)"
    }}
    """
    final_script_str = ai_text(copywriter_prompt, timeout=30, json_mode=True)
    
    try:
        if final_script_str.startswith("```json"): final_script_str = final_script_str.strip("`").replace("json\n", "", 1)
        final_script = json.loads(final_script_str)
        # Ensure we have the required fields
        if not all(k in final_script for k in ["title", "script", "hook"]):
            raise ValueError("Missing required fields in final script")
        log.info(f"Copywriter finished script: {final_script['title']}")
        return final_script
    except Exception as e:
        log.warning(f"Copywriter failed completely. Error: {e}")
        raise ValueError(f"Failed to generate a valid script for {topic}") from e
