"""Extract explicit temporal phrases; never infer the historical answer."""
import re
from datetime import date
from urllib.parse import unquote, urlsplit

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

def temporal_url_advisory(question, url):
    """Flag date-shaped path segments after the requested year, never validate a claim.

    Query parameters and fragments are deliberately excluded. A valid date in
    a URL path can be a document ID or unrelated date, and is not necessarily
    a publication date. A later source may describe a prior period correctly.
    """
    if not isinstance(url, str):raise TypeError('url must be text')
    phrases=explicit_temporal_phrases(question)
    targets=[int(m.group(0)) for phrase in phrases
             for m in re.finditer(r'(?<!\d)(?:19|20)\d{2}(?!\d)',phrase)]
    if not targets:return None
    try:
        parts=urlsplit(url)
        if parts.scheme.lower() not in ('http','https') or not parts.hostname:return None
        path=unquote(parts.path)
    except ValueError:
        return None
    target=max(targets);hits=[];total=0
    # Boundaries exclude an eight-digit prefix hidden inside a longer article ID.
    for match in re.finditer(r'(?<![A-Za-z0-9])((?:19|20)\d{6})(?![A-Za-z0-9])',path):
        value=match.group(1);year,month,day=int(value[:4]),int(value[4:6]),int(value[6:])
        try:
            parsed=date(year,month,day)
        except ValueError:
            continue
        if year<=target:continue
        total+=1
        if len(hits)<3:hits.append({'path_date':parsed.isoformat(),'path_offset':match.start(1)})
    if not hits:return None
    return {'question_phrases':phrases,'latest_question_year':target,
            'later_path_dates':hits,'later_path_date_occurrences':total,
            'scope':('The URL path contains a valid date later than the question year. '
                     'It may be an unrelated identifier and is not necessarily a publication date. '
                     'A later source can report historical facts. Check the specific claim and '
                     'requested date; do not infer contradiction or correctness.')}
