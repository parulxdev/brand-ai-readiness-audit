#!/usr/bin/env python3
"""
Optional spaCy NER with regex fallback.
Currency patterns require a digit. Capital-letter pre-filter short-circuits
on lowercase-only text.
"""

import re
import sys

_SPACY_NLP = None
_SPACY_ATTEMPTED = False
_SPACY_ERROR = None


def _load_spacy():
    global _SPACY_NLP, _SPACY_ATTEMPTED, _SPACY_ERROR
    if _SPACY_ATTEMPTED:
        return _SPACY_NLP
    _SPACY_ATTEMPTED = True
    try:
        import spacy  # noqa
    except ImportError:
        _SPACY_ERROR = "spacy not installed"
        return None
    try:
        import logging
        logging.getLogger("spacy").setLevel(logging.ERROR)
    except Exception:
        pass
    try:
        _SPACY_NLP = spacy.load("en_core_web_sm")
    except OSError as e:
        _SPACY_ERROR = f"en_core_web_sm not installed ({e})"
        _SPACY_NLP = None
    except Exception as e:
        _SPACY_ERROR = f"spaCy load failed: {e}"
        _SPACY_NLP = None
    return _SPACY_NLP


def is_loaded():
    return _load_spacy() is not None


def get_backend():
    return "spacy" if is_loaded() else "regex"


def diagnostic_info():
    return {"backend": get_backend(), "loaded": is_loaded(), "load_error": _SPACY_ERROR}


_FALSE_ENTITY_WORDS = {
    "the", "a", "an", "and", "but", "or", "so", "yet", "for", "nor",
    "however", "therefore", "thus", "moreover", "furthermore", "meanwhile",
    "welcome", "introducing", "discover", "explore", "learn", "read",
    "our", "we", "this", "that", "these", "those", "it", "they", "you",
    "if", "when", "while", "where", "why", "how", "what", "who", "which",
    "today", "tomorrow", "yesterday", "now", "then",
    "please", "thank", "thanks", "here", "there", "above", "below",
    "new", "old", "next", "last", "first", "second", "third",
    "one", "two", "three", "many", "few", "several", "some", "most",
    "all", "any", "each", "every", "no", "not", "yes", "okay", "ok",
    "from", "to", "in", "on", "at", "by", "with", "without", "as",
    "about", "into", "over", "under", "through", "between",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april",
    "may", "june", "july", "august", "september", "october",
    "november", "december",
}

_WORD_PATTERN = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_CAPS_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")
_CAPITAL_LETTER = re.compile(r"[A-Z]")

QUANTITY_PATTERN = re.compile(
    r"(?:"
        r"(?:₹|\$|€|£)\s*\d[\d,]*(?:\.\d+)?"
        r"|"
        r"\b\d[\d,]*(?:\.\d+)?\s*"
        r"(?:%|kg|cm|mm|km|mb|gb|tb|ms|users?|years?|days?|"
        r"hrs?|min|million|billion|thousand)\b"
    r")",
    re.IGNORECASE,
)


def _regex_entities(text):
    if not text:
        return []
    hits = []
    for m in _WORD_PATTERN.finditer(text):
        if m.group(0).lower() in _FALSE_ENTITY_WORDS:
            continue
        hits.append({"text": m.group(0), "label": "MISC"})
    for m in _CAPS_PATTERN.finditer(text):
        hits.append({"text": m.group(0), "label": "MISC"})
    return hits


_MAX_TEXT_CHARS = 20000
_MAX_SHORT_CHARS = 4000


def extract_entities(text):
    if not text:
        return []
    nlp = _load_spacy()
    if nlp is None:
        return _regex_entities(text)
    try:
        doc = nlp(text[:_MAX_TEXT_CHARS])
        return [{"text": e.text, "label": e.label_} for e in doc.ents]
    except Exception as e:
        sys.stderr.write(f"Warning: spaCy NER failed: {e}\n")
        return _regex_entities(text)


def has_named_entity(text):
    if not text:
        return False
    nlp = _load_spacy()
    if nlp is None:
        return bool(_regex_entities(text))
    if not _CAPITAL_LETTER.search(text):
        return False
    try:
        doc = nlp(text[:_MAX_SHORT_CHARS])
        labels = {"ORG", "PERSON", "PRODUCT", "GPE", "LOC",
                  "EVENT", "WORK_OF_ART", "NORP", "FAC", "LAW"}
        return any(e.label_ in labels for e in doc.ents)
    except Exception:
        return bool(_regex_entities(text))


def has_quantity(text):
    return bool(QUANTITY_PATTERN.search(text or ""))