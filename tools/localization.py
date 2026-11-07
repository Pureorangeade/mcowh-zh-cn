"""Display-text selection and exact spans for the broad Chinese draft.

Offsets are Unicode character offsets in the original UTF-8 script, never line
numbers. Machine output cannot edit commands, filenames or numeric data.
"""
import hashlib
import re

PATH = re.compile(r"(?:[A-Za-z_]+/){1,}|\.(?:png|jpg|jpeg|dds|phyre|at9|ogg|wav|mid|txt|dat|bin|csv|mps)\b", re.I)
LATIN = re.compile(r"[A-Za-z]")


def digest(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def runtime_placeholders(text):
    return re.findall(r'(?<![A-Za-z0-9_])(?:Lvnum|num)(?![A-Za-z0-9_])',text)


def controls(text):
    """Find balanced WOLF escapes, substitutions and explicit line endings."""
    result = []
    i = 0
    while i < len(text):
        match = re.match(r"(?:\r\r?\n|\r|\n)|<[^<>\r\n]+>|\[[A-Z][A-Z_0-9]*\]|\$[A-Za-z][A-Za-z0-9]*", text[i:])
        if (i == 0 or text[i - 1] in '\r\n'):
            directive = re.match(r'[ \t]*(?:[@#][^\r\n]*|//[^\r\n]*|\[/?[A-Za-z][A-Za-z0-9_]*\](?=\r|\n|$)|(?:BGM|SE|Y|X|WAIT|BG|VOICE):[^\r\n]*)', text[i:])
            if directive:
                match = directive
        if match:
            end = i + len(match[0])
        elif text[i] == '\\':
            match = re.match(r"\\(?:[A-Za-z_]+|.)", text[i:])
            if not match:
                i += 1
                continue
            end = i + len(match[0])
            if end < len(text) and text[end] == '[':
                depth = 0
                for end in range(end, len(text)):
                    depth += (text[end] == '[') - (text[end] == ']')
                    if depth == 0:
                        end += 1
                        break
                else:
                    raise ValueError('Unbalanced control token')
        else:
            i += 1
            continue
        result.append((i, end, text[i:end]))
        i = end
    return result


def validate(source, target, *, single_argument=False, preserve_linebreaks=True):
    if '\0' in target:
        raise ValueError('NUL inside translated text')
    if runtime_placeholders(source)!=runtime_placeholders(target):
        raise ValueError('Runtime num/Lvnum placeholder changed')
    a, b = [t for _, _, t in controls(source)], [t for _, _, t in controls(target)]
    is_break = lambda t: not t.strip('\r\n')
    if [t for t in a if not is_break(t)] != [t for t in b if not is_break(t)]:
        raise ValueError('Control token order/content changed')
    if preserve_linebreaks and [t for t in a if is_break(t)] != [t for t in b if is_break(t)]:
        raise ValueError('Original line endings changed')
    # Never allow translated dialogue to introduce an event command or comment.
    directives = lambda text: [line for line in text.splitlines() if line.lstrip().startswith(('@', '#'))]
    if directives(source) != directives(target):
        raise ValueError('Translation introduces a script directive')
    if single_argument and re.search(r'\s', target):
        raise ValueError('A script label must remain a single argument')


def display_candidate(text):
    plain = text
    try:
        spans = controls(text)
    except ValueError:
        return False  # Preserve malformed legacy strings for separate review.
    for a, b, _ in reversed(spans):
        plain = plain[:a] + ' ' + plain[b:]
    return bool(LATIN.search(plain)) and not PATH.search(plain) and not re.search('[\u3040-\u30ff]', plain)


def database_display(table, column, field):
    if table == 28 and field.startswith('短縮'):
        return False  # Class abbreviations such as SW/KN/AR are identifiers.
    if table == 0:
        return column == 69
    if 53 <= table <= 56:
        return column == 0
    if 58 <= table <= 63:
        return column == 1
    if table in {2, 7, 12, 14, 15, 16, 18, 19, 20, 27, 29, 31, 36, 39, 41,
                  44, 45, 47, 48, 49, 50, 51, 52, 57, 64, 65, 66, 67, 68, 74, 75, 76, 77}:
        return False
    if table == 70:
        return column in {2, 3}
    if table == 71:
        return column == 1
    if table == 72:
        return field in {'タイトル', '説明（エクストラ用）'}
    return bool(re.search('名前|名$|説明|メッセ|ﾒｯｾ|文章|二つ名|パーツ名|コメント|死因|強化名', field)) and not re.search('ファイル|BGM|コード|フラグ|アイコン|メモ', field)


def script_spans(text):
    """Extract message bodies, @putselect labels and final Button labels."""
    offset = 0
    active = None
    block_start = None
    block_index = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        directive = stripped.startswith(('@', '#'))
        if directive:
            if block_start is not None:
                source = text[block_start:offset].rstrip('\r\n')
                if source:
                    yield ('message', block_index, block_start, block_start + len(source), source)
                block_index += 1
                block_start = None
            active = bool(re.match(r'@(?:[LR]_)?mes(?:\s|$)', stripped))
            match = re.match(r'(@+putselect[ \t]+)(\S+)', line)
            if match:
                a, b = match.span(2)
                yield ('choice', offset, offset + a, offset + b, match[2])
        elif active and block_start is None:
            block_start = offset
        button = re.match(r'Button:[^\r\n]*,[ \t]*([^,\r\n]+?)[ \t]*(?:\r*\n)?$', line)
        if button:
            a, b = button.span(1)
            yield ('button', offset, offset + a, offset + b, button[1])
        offset += len(line)
    if block_start is not None:
        source = text[block_start:].rstrip('\r\n')
        if source:
            yield ('message', block_index, block_start, block_start + len(source), source)


def apply_spans(text, entries):
    previous = len(text) + 1
    for entry in sorted(entries, key=lambda e: e['start'], reverse=True):
        a, b = entry['start'], entry['end']
        if not 0 <= a < b <= len(text) or b > previous:
            raise ValueError('Overlapping or invalid script spans')
        if text[a:b] != entry['source'] or digest(entry['source']) != entry['source_sha256']:
            raise ValueError('Script source has changed')
        validate(entry['source'], entry['translation'], single_argument=entry['kind'] == 'choice',
                 preserve_linebreaks=entry.get('status') != 'curated')
        text = text[:a] + entry['translation'] + text[b:]
        previous = a
    return text
