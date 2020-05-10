import re
from typing import Sized


def _a(num: str) -> str:
    """Internal helper to make ansi escape code CSI sequences"""
    return f'\x1b[{num}m'


BOLD = _a('1')
BLACK = _a('30')
RED = _a('31')
GREEN = _a('32')
YELLOW = _a('33')
BLUE = _a('34')
MAGENTA = _a('35')
CYAN = _a('36')
WHITE = _a('37')
RESET = _a('0')
NO_BOLD = _a('22')
DEF_FG = _a('39')
DEF_BG = _a('49')


def clean_esc(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def strlen(val: Sized) -> int:
    """Get length of a string without including ANSI escape codes"""
    if isinstance(val, str):
        return len(clean_esc(val))
    else:
        return len(val)


def rgb_fg(r: int, g: int, b: int) -> str:
    return _a(f'38;2;{r};{g};{b}')


def rgb_bg(r: int, g: int, b: int) -> str:
    return _a(f'48;2;{r};{g};{b}')
