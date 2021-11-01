import logging
import sys

import pygount

log = logging.getLogger(__name__)

from typing import (Dict, Generator, List, Optional, Pattern, Sequence, Set,
                    Tuple, Union)

import pygments
from pygount.analysis import (_delined_tokens, _pythonized_comments,
                              white_characters, white_code_words)


def _line_parts_patched(
    lexer: pygments.lexer.Lexer, text: str
) -> Generator[Set[str], None, None]:
    line_marks = set()
    tokens = _delined_tokens(lexer.get_tokens(text))
    # print(list(tokens))
    if lexer.name == "Python":
        tokens = _pythonized_comments(tokens)
    language_id = lexer.name.lower()
    white_text = " \f\n\r\t" + white_characters(language_id)
    white_words = white_code_words(language_id)

    line_tokens = []
    for token_type, token_text in tokens:
        # NOTE: Pygments treats preprocessor statements as special comments.
        is_actual_comment = token_type in pygments.token.Comment and token_type not in (
            pygments.token.Comment.Preproc,
            pygments.token.Comment.PreprocFile,
        )
        if is_actual_comment:
            line_marks.add("d")  # 'documentation'
        elif token_type in pygments.token.String:
            line_marks.add("s")  # 'string'
        else:
            is_white_text = (token_text.strip() in white_words) or (
                token_text.rstrip(white_text) == ""
            )
            if not is_white_text:
                line_marks.add("c")  # 'code'
        if token_text.endswith("\n"):
            # UR: patched
            yield line_marks, [*line_tokens, (token_type, token_text)]
            line_marks = set()
            line_tokens = []
        else:
            line_tokens.append((token_type, token_text))
    if len(line_marks) >= 1:
        # UR: patched
        yield line_marks, [*line_tokens, (token_type, token_text)]


pygount.analysis._line_parts = _line_parts_patched


def get_content(repo, hexsha, path):
    return repo.git.show("{}:{}".format(hexsha, path))


def is_binary(repo, hexsha, path):
    # Based on https://stackoverflow.com/questions/6119956/how-to-determine-if-git-handles-a-file-as-binary-or-as-text
    numstat = repo.git.execute(
        [
            "git",
            "diff-tree",
            "--numstat",
            "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
            hexsha,
            "--",
            path,
        ]
    )
    return numstat.startswith("-")


def get_lines(
    source_path,
    source_code,
    encoding: str = "automatic",
):
    fallback_encoding = (sys.getdefaultencoding(),)

    if encoding in ("automatic", "chardet"):
        encoding = pygount.analysis.encoding_for(
            source_path, encoding, fallback_encoding
        )
    lexer = pygount.analysis.guess_lexer(source_path, source_code)

    if lexer is None:
        log.debug(f"No lexer for {source_path}")
        return None

    language = lexer.name
    if ("xml" in language.lower()) or (language == "Genshi"):
        dialect = pygount.xmldialect.xml_dialect(source_path, source_code)
        if dialect is not None:
            language = dialect

    log.debug("%s: analyze as %s using encoding %s", source_path, language, encoding)
    mark_to_count_map = {"c": 0, "d": 0, "e": 0, "s": 0}

    for line_parts, line_tokens in pygount.analysis._line_parts(lexer, source_code):
        # if line_tokens and re.match(r"^[\s\t]+", line_tokens[0][1]):
        #     print(f"{source_path} {len(line_tokens[0][1])} {line_parts}: {line_tokens}")

        mark_to_increment = "e"
        for mark_to_check in ("d", "s", "c"):
            if mark_to_check in line_parts:
                mark_to_increment = mark_to_check
        mark_to_count_map[mark_to_increment] += 1

    return dict(
        language=language,
        code=mark_to_count_map["c"],
        documentation=mark_to_count_map["d"],
        empty=mark_to_count_map["e"],
        string=mark_to_count_map["s"],
    )
