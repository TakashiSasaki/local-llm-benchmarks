"""Extract explicit temporal phrases; never infer the historical answer."""
import re

PATTERNS = [
    re.compile(r'\b(?:as\s+of|up\s+to|by)\s+(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+)?(?:\d{1,2},?\s+)?(?:19|20)\d{2}\b', re.I),
    re.compile(r'(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?(?:時点|現在|まで|以前)'),
]

def explicit_temporal_phrases(question):
    if not isinstance(question,str):raise TypeError('question must be text')
    matches=sorted((m.start(),m.group(0)) for pattern in PATTERNS for m in pattern.finditer(question))
    return list(dict.fromkeys(text for _,text in matches))[:8]

def temporal_instruction(question):
    phrases=explicit_temporal_phrases(question)
    if not phrases:return ''
    return ('\nThe user explicitly specifies these time limits: '+repr(phrases)+'. '
            'For each relevant claim, check evidence for the requested time rather than assuming a current role applied then. '
            'A later publication may describe the past; its publication date alone neither proves nor disproves the historical claim. '
            'If the time-specific evidence is insufficient, say so.')
