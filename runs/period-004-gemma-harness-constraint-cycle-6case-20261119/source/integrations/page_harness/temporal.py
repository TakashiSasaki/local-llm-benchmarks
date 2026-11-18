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

def temporal_evidence_advisory(question, text, base_offset=None):
    """Flag explicit later years in shown text, without judging a claim.

    A year can refer to an update, another person, or a later source reporting
    the requested historical fact. The caller must not treat it as a verdict or
    alter a benchmark score. With several target dates, use the latest target
    year only as a conservative signal and retain all original phrases.
    """
    if not isinstance(text, str):raise TypeError('text must be a string')
    if base_offset is not None and (type(base_offset) is not int or base_offset<0):
        raise ValueError('invalid base offset')
    phrases=explicit_temporal_phrases(question)
    targets=[int(m.group(0)) for phrase in phrases for m in re.finditer(r'(?<!\d)(?:19|20)\d{2}(?!\d)',phrase)]
    if not targets:return None
    target=max(targets);later=[];total=0
    for match in re.finditer(r'(?<!\d)(?:19|20)\d{2}(?!\d)',text):
        year=int(match.group(0))
        if year<=target:continue
        total+=1
        if len(later)>=3:continue
        row={'year':year,'relative_offset':match.start(),
             'context':text[max(0,match.start()-55):min(len(text),match.end()+55)]}
        if base_offset is not None:row['page_offset']=base_offset+match.start()
        later.append(row)
    if not later:return None
    return {'question_phrases':phrases,'latest_question_year':target,
            'later_years':later,'later_year_occurrences':total,
            'scope':('A later year occurs in the shown text. It may describe publication, '
                     'an unrelated event, or a source reporting past facts. Check the specific '
                     'claim and requested date; do not infer contradiction or correctness.')}
