# Engagement Checks

Nav/footer/aside chrome is excluded from paragraph and anchor analysis.

| ID | Check |
|---|---|
| ENG-001 | No heading ids |
| ENG-002 | Missing h1 |
| ENG-003 | Fact-bearing headings lack ids |
| ENG-004 | No quotable answer paragraph (40-90 words, entity+quantity) |
| ENG-005 | Above-fold fact-density deficit |
| ENG-006 | No AI-referrer context handling |
| ENG-007 | No next-action affordance |
| ENG-008 | Sections do not open with direct answers |
| ENG-009 | Low citation density (< 2.0 per 1000 body words) |

## NER backend

ENG-004/005/008/009 use spaCy's `en_core_web_sm` when available, else a
capital-letter + stop-word regex fallback. Diagnostics array records which ran.