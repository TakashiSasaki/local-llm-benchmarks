"""Narrow, advisory checks for a few explicit question/source mismatches.

These checks do not judge whether a claim is true, relevant, or wrong.  In
particular, a document can mention a contrasting category without asserting it
as the answer.  The caller should preserve the original text and let the model
or a reviewer inspect the relevant passage.
"""
import re


_RULES = (
    {
        'kind': 'possible_natural_only_narrowing',
        'question': re.compile(r'\b(?:largest|biggest)\s+lake\b|最大の湖', re.I),
        'already_requested': re.compile(r'\b(?:largest|biggest)\s+natural\s+lake\b|最大の自然湖', re.I),
        'candidate': re.compile(r'\b(?:largest|biggest)\s+natural\s+(?:lake|body\s+of\s+water)\b|最大の自然湖', re.I),
        'notice': ('The question asks about the largest lake, while this text mentions a largest natural lake or '
                   'natural body of water. Check whether the requested scope includes artificial lakes or reservoirs; '
                   'this mention alone does not establish the overall largest lake.'),
    },
    {
        'kind': 'possible_live_action_for_animation',
        'question': re.compile(r'\b(?:animated|animation)\s+(?:movie|film)\b|アニメ(?:ーション)?映画', re.I),
        'already_requested': re.compile(r'\blive[\s-]+action\b|実写', re.I),
        'candidate': re.compile(r'\blive[\s-]+action\b|実写', re.I),
        'notice': ('The question asks about an animated film and this text mentions live-action. Verify which version '
                   'the claim or event concerns; a source may discuss both versions.'),
    },
)


def inspect_constraints(question, candidate_text):
    """Return bounded, non-conclusive warnings with offsets in candidate_text."""
    if not isinstance(question, str) or not isinstance(candidate_text, str):
        raise TypeError('question and candidate_text must be strings')
    warnings = []
    for rule in _RULES:
        requested = rule['question'].search(question)
        if not requested or rule['already_requested'].search(question):
            continue
        found = rule['candidate'].search(candidate_text)
        if found:
            warnings.append({'kind': rule['kind'],
                             'question_phrase': requested.group(0),
                             'candidate_phrase': found.group(0),
                             'candidate_offset': found.start(),
                             'candidate_end': found.end(),
                             'notice': rule['notice'],
                             'scope': 'Advisory text-pattern match only; does not establish factual correctness.'})
    return warnings
