"""Conservative display repair; never guess an encoding for an entire document."""

# Recognizable UTF-8 punctuation/currency decoded as Western single-byte text.
# Mapping only these sequences preserves Hindi, emoji, accents and real 'Â'.
_REPAIRS = {}
for _character in ("\u2013", "\u2014", "\u2018", "\u2019", "\u201c", "\u201d", "\u2026", "\u00a0", "\u00b7", "\u20b9", "\u20ac"):
    for _encoding in ("cp1252", "latin1"):
        try:
            _broken = _character.encode("utf-8").decode(_encoding)
            _REPAIRS[_broken] = _character
        except UnicodeDecodeError:
            pass


def repair_text(value: str) -> str:
    for _ in range(2):
        previous = value
        for broken, character in _REPAIRS.items():
            value = value.replace(broken, character)
        if value == previous:
            break
    return value
