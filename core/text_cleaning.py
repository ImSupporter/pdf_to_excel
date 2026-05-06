IGNORED_TEXT_CHARS = str.maketrans("", "", ">=")


def remove_ignored_chars(value) -> str:
    return str(value).translate(IGNORED_TEXT_CHARS).strip()
