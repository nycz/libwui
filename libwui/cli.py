from itertools import zip_longest
from pathlib import Path
import shlex
import shutil
import sys
import textwrap
from typing import (Any, Callable, Collection, Dict, FrozenSet, Iterable,
                    List, NamedTuple, NoReturn, Optional, Set,
                    Tuple, Union)

from .colors import BOLD, CYAN, RED, RESET, YELLOW, strlen


# == Helper functions ==

def error(message: str) -> NoReturn:
    sys.exit(f'{RED}Error:{RESET} {message}')


def warn(message: str) -> None:
    print(f'{YELLOW}Warning:{RESET} {message}')


# == Table ==

class TooNarrowColumn(Exception):
    pass


def format_table(items: Iterable[Union[str, Iterable[str]]],
                 column_spacing: int = 2,
                 wrap_columns: Optional[Collection[int]] = None,
                 titles: Optional[Iterable[str]] = None,
                 surround_rows: Optional[Dict[int, Tuple[str, str]]] = None,
                 end_spacing: int = 2,
                 require_min_widths: FrozenSet[Tuple[int, int]] = frozenset(),
                 ) -> Iterable[str]:
    term_size = shutil.get_terminal_size()
    surround_rows = surround_rows or dict()
    rows: List[Union[str, List[str]]] = []
    if titles:
        rows.append(list(titles))
    for row in items:
        rows.append(row if isinstance(row, str) else list(row))
    if not rows:
        return
    max_row_length = max(strlen(row) for row in rows
                         if not isinstance(row, str))
    rows = [row if isinstance(row, str)
            else row + ([''] * (max_row_length - strlen(row)))
            for row in rows]
    max_widths = [max(strlen(row[col]) for row in rows
                      if not isinstance(row, str))
                  for col in range(max_row_length)]
    wrap_columns = {w if w >= 0 else len(max_widths) + w
                    for w in wrap_columns or []}
    total_spacing = (strlen(max_widths) - 1) * column_spacing + end_spacing
    if sum(max_widths) + total_spacing > term_size.columns and wrap_columns:
        unwrappable_space = sum(w for n, w in enumerate(max_widths)
                                if n not in wrap_columns)
        wrappable_space = (term_size.columns - total_spacing
                           - unwrappable_space) // strlen(wrap_columns)
        for n in wrap_columns:
            max_widths[n] = wrappable_space
    else:
        wrappable_space = -1
    for pos, min_width in require_min_widths:
        if max_widths[pos] < min_width:
            raise TooNarrowColumn
    if titles:
        rows.insert(1, '-' * (sum(max_widths) + total_spacing))
        surround_rows[-2] = (BOLD, RESET)
        surround_rows[-1] = (CYAN, RESET)
    for row_num, row in enumerate(rows, -2 if titles else 0):
        prefix, suffix = surround_rows.get(row_num, ('', ''))
        if isinstance(row, str):
            yield prefix + row + suffix
        else:
            cells = [textwrap.wrap(cell, width=wrappable_space)
                     if wrappable_space > 0 and n in wrap_columns
                     else [cell]
                     for n, cell in enumerate(row)]
            for subrow in zip_longest(*cells):
                subcells = ((c or '') + (' ' * (max_widths[n] - strlen(c or '')))
                            for n, c in enumerate(subrow))
                line = (' ' * column_spacing).join(subcells).rstrip()
                yield prefix + line + suffix


# == Command parsing ==

def arg_tags(args: List[str], option_name: str) -> Set[str]:
    tags = set()
    while args and not args[0].startswith('-'):
        tags.add(args.pop(0))
    if not tags:
        error(f'no tags specified for {option_name}')
    return tags


def arg_positional(args: List[str], option_name: str,
                   position: int = 0, allow_empty: bool = False) -> str:
    if not args:
        error(f'no {option_name} provided')
    arg = args.pop(position).strip()
    if not allow_empty and not arg:
        error(f'empty {option_name} isn\'t allowed')
    return arg


def arg_disallow_trailing(args: List[str]) -> None:
    if args:
        error(f'unknown trailing arguments: {", ".join(map(repr, args))}')


def arg_disallow_positional(arg: str) -> None:
    if not arg.startswith('-'):
        error(f'unknown positional argument: {arg}')


def arg_unknown_optional(arg: str) -> None:
    error(f'unknown argument: {arg}')


class OptionHelp(NamedTuple):
    spec: str
    description: str


class CommandHelp(NamedTuple):
    description: str
    usage: str
    options: List[OptionHelp]


_RunFunc = Callable[[Any, List[str]], None]


class CommandDef(NamedTuple):
    abbrevs: List[str]
    run: _RunFunc
    help_: CommandHelp


def expand_aliases(args: Iterable[str], aliases: Dict[str, str]
                   ) -> Iterable[str]:
    for arg in args:
        if arg.startswith('@'):
            alias = arg[1:]
            if alias not in aliases:
                error(f'unknown alias: {alias}')
            yield from shlex.split(aliases[alias])
        else:
            yield arg


def parse_cmds(commands: Dict[str, CommandDef],
               callback: Callable[[_RunFunc, List[str]], None],
               aliases: Optional[Dict[str, str]] = None) -> None:
    help_aliases = {'-h', '--help', 'help'}
    sys_cmd = Path(sys.argv[0]).name
    show_help = False
    args = list(expand_aliases(sys.argv[1:], aliases or {}))
    if not args or len(args) == 1 and args[0] in help_aliases:
        print(f'{BOLD}Usage:{RESET} {sys_cmd} '
              f'[-h | --help] <command> [<arguments>]')
        print(f'\n{BOLD}Commands:{RESET}')
        command_table = [
            (CYAN + '  help' + RESET, 'show help for a command')
        ]
        command_table.extend((CYAN + '  ' + ', '.join([cmd] + cmd_def.abbrevs)
                              + RESET, cmd_def.help_.description)
                             for cmd, cmd_def
                             in commands.items())
        print('\n'.join(format_table(command_table, column_spacing=2,
                                     wrap_columns={1})))
        return
    if args[0] in help_aliases.union({'help'}):
        show_help = True
        args.pop(0)
    abbrevs = {abbr: key for key, cmd in commands.items()
               for abbr in cmd.abbrevs}
    cmd_text = args.pop(0)
    if cmd_text in abbrevs:
        cmd_text = abbrevs[cmd_text]
    if cmd_text not in commands:
        error(f'unknown command: {cmd_text}')
    else:
        cmd = commands[cmd_text]
        func = cmd.run
        help_desc = cmd.help_.description
        help_usage = cmd.help_.usage
        help_lines = cmd.help_.options
        if show_help or (args and args[0] in help_aliases):
            print(f'{BOLD}Usage:{RESET} {sys_cmd} '
                  f'{cmd_text} {help_usage}'.rstrip())
            print()
            print('\n'.join(format_table([(f'{BOLD}Description:{RESET}',
                                           help_desc)],
                                         column_spacing=1, wrap_columns={1})))
            if help_lines:
                print(f'\n{BOLD}Options:{RESET}')
                print('\n'.join(format_table((('  ' + h.spec, h.description)
                                              for h in help_lines),
                                             column_spacing=3,
                                             wrap_columns={1})))
        else:
            callback(func, args)
