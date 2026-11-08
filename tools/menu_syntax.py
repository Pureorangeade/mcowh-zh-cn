"""Protect database menu rows: translated label, integer action identifier."""
import re

MENU_LINE = re.compile(r'(?P<label>[^,\r\n]+)(?P<suffix>,[ \t]*[+-]?[0-9]+[ \t]*(?:\r\r?\n|\r|\n)?)')


def menu_entries(text):
    """Return rows only when the entire string is a label/action menu list."""
    rows=[]
    lines=re.findall(r'[^\r\n]*(?:\r\r?\n|\r|\n|$)',text)
    if lines and lines[-1]=='':lines.pop()
    for line in lines:
        match=MENU_LINE.fullmatch(line)
        if not match:return None
        rows.append((match['label'],match['suffix']))
    return rows or None


def validate_menu_commands(source,target):
    expected=menu_entries(source)
    if expected is None:return
    actual=menu_entries(target)
    if actual is None or [s for _,s in expected]!=[s for _,s in actual]:
        raise ValueError('Menu action separator, identifier, or row ending changed; preserve the original ASCII comma and action suffix')
