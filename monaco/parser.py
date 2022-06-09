#!/usr/bin/env python3

# Lexer based on git from:
# Eli Bendersky (eliben@gmail.com)
# This code is in the public domain
# Last modified: August 2010


import re
import sys
from pathlib import Path
from typing import Union, List, Optional


class Token(object):
    """Class to represent a token"""

    def __init__(self, type, val):
        self.type = type
        self.val = val

    def __str__(self):
        if self.type == "NEWLINE":
            return f"{self.type}"
        elif self.type == "SPACE":
            return f"{self.type}"
        else:
            return f"{self.type}({self.val})"

    def __repr__(self):
        return str(self)

    def value(self) -> Union[str, int, bool]:
        """Return the value of the token as the proper type.

        Returns:
            Casted value of the token.
        """
        if self.type == "NUMBER":
            return int(self.val)
        if self.type == "TRUE":
            return True
        if self.type == "FALSE":
            return False
        else:
            return self.val


class ParserError(Exception):
    pass


class Parser:
    """Parser class to provide template substitution.

    Attributes:
        buf: Buffer containing the template.
        pos: Position in the buffer.
        group_type:
        env: Dictionary containing values for the substitutions
    """

    def __init__(self, buf: Union[str, Path], env: dict = None):
        """Create a parser.

        Args:
            buf: Text to be parsed or pointer to file.
            env: Dictionary containing values for substitutions.
        """
        if isinstance(buf, Path):
            self.buf = buf.read_text()
        else:
            self.buf = buf
        self.pos = 0

        rules = [
            (r"[\r\n]+", "NEWLINE"),
            (r"\s+", "SPACE"),
            (r"#+", "COMMENT"),
            ("\d+", "NUMBER"),
            ("[Tt]rue", "TRUE"),
            ("[Ff]alse", "FALSE"),
            ("=", "EQUAL"),
            ("\+", "PLUS"),
            ("\-", "MINUS"),
            ("\*", "MULT"),
            ("\(", "LP"),
            ("\)", "RP"),
            ("\[", "LB"),
            ("\]", "RB"),
            (r"..define::", "DEFINE"),
            (r"..for::", "FOR"),
            (r"..undef::", "UNDEF"),
            (r"..if::", "IF"),
            (r"..ifnot::", "IFNOT"),
            (r"..else::", "ELSE"),
            (r"..end::", "END"),
            (r"..\w+::", "VAR"),
            ("[a-zA-Z_0-9]+", "IDENTIFIER"),
        ]
        idx = 1
        regex_parts = []
        self.group_type = {}
        self.env = {} if env is None else env.copy()

        for regex, type in rules:
            groupname = f"GROUP{idx}"
            regex_parts.append(f"(?P<{groupname}>{regex})")
            self.group_type[groupname] = type
            idx += 1

        self.regex = re.compile("|".join(regex_parts))

    def get_token(self) -> Optional[Token]:
        """Get a token from the buffer.

        Returns:
            Token or None where no more tokens are available.

        Raises:
            ParserError: Error during parsing.
        """
        if self.pos >= len(self.buf):
            return None
        else:
            m = self.regex.match(self.buf, self.pos)
            if m:
                groupname = m.lastgroup
                tok_type = self.group_type[groupname]
                tok = Token(tok_type, m.group(groupname))
                self.pos = m.end()
                return tok

            raise ParserError

    def tokenize(self) -> List[Token]:
        """Obtain all tokens from the buffer.

        Returns:
            List of all tokens
        """
        tokens = []
        self.pos = 0
        while True:
            tok = self.get_token()
            if tok is None:
                break
            tokens.append(tok)
        return tokens

    def __handle_cond(self, tokens: List[Token]) -> bool:
        """Handle a conditional from tokens

        Args:
            tokens: List of tokens to obtain a boolean from
        """
        tokens = list(filter(lambda t: t.type != "SPACE", tokens))
        if tokens[0].type in ["TRUE", "FALSE"]:
            return tokens[0].value()
        if tokens[0].type == "IDENTIFIER":
            return bool(self.env.get(tokens[0].value(), None))
        else:
            return bool(tokens[0].value())

    def parse(self, tokens=None, iter_id=None) -> Optional[str]:
        """Parse tokens and execute the subsitution.

        Args:
            tokens: List of tokens to parse
            iter_id: If evaluating a loop, the iteration fo the loop.

        Returns:
            A string if the substitutions is executed or an empty string.
        """
        tokens = tokens if tokens is not None else self.tokenize()
        result = ""
        pos = 0
        while pos < len(tokens):
            token = tokens[pos]
            if token.type == "COMMENT":
                pos += 1
                while tokens[pos].type != "NEWLINE":
                    pos += 1

            elif token.type in ["SPACE", "NEWLINE"]:
                if tokens[pos - 1].type == "NEWLINE":
                    pos += 1
                    continue
                else:
                    result += token.val
                    pos += 1

            elif token.type == "FOR":
                pos += 2
                range_loop = []
                while tokens[pos].type != "NEWLINE":
                    range_loop.append(tokens[pos])
                    pos += 1

                start, end = self.parse(range_loop).split(" ")
                pos += 1
                body = []

                while tokens[pos].type != "END":
                    body.append(tokens[pos])
                    pos += 1

                for i in range(int(start), int(end)):
                    result += self.parse(body, iter_id=i)
                pos += 1

            elif token.type in ["IF", "IFNOT"]:
                cond_type = token.type
                cond = []
                pos += 1

                while tokens[pos].type != "NEWLINE":
                    cond.append(tokens[pos])
                    pos += 1

                pos += 1
                body = [[], []]
                branch_sel = 0
                level = 1

                while True:
                    if tokens[pos].type == "IF":
                        level += 1
                        body[branch_sel].append(tokens[pos])
                    elif tokens[pos].type == "ELSE":
                        if level == 1:
                            branch_sel = 1
                        else:
                            body[branch_sel].append(tokens[pos])
                    elif tokens[pos].type == "END":
                        if level <= 1:
                            break
                        else:
                            level -= 1
                            body[branch_sel].append(tokens[pos])
                            pos += 1
                    else:
                        body[branch_sel].append(tokens[pos])
                    pos += 1

                if cond_type == "IF":
                    cond_res = self.__handle_cond(cond)
                if cond_type == "IFNOT":
                    cond_res = not self.__handle_cond(cond)

                if cond_res:
                    res = self.parse(tokens=body[0])
                else:
                    res = self.parse(tokens=body[1])
                if res:
                    result += res
                pos += 1

            elif token.type == "DEFINE":
                key, val = None, None
                pos += 1
                while True:
                    if tokens[pos].type == "SPACE":
                        pos += 1
                    else:
                        if key is None:
                            key = tokens[pos].value()
                        elif val is None and key is not None:
                            val = tokens[pos].value()
                        else:
                            break
                        pos += 1
                self.env[key] = val
                pos += 2

            elif token.type == "UNDEF":
                key = None
                while True:
                    if tokens[pos].type == "IDENTIFIER":
                        key = tokens[pos].val
                        break
                    pos += 1
                del self.env[key]
                while tokens[pos].type != "NEWLINE":
                    pos += 1
                pos += 1

            elif token.type == "VAR":
                key = tokens[pos].val
                if (
                    len(tokens) > 3
                    and tokens[pos + 1].type == "LB"
                    and tokens[pos + 3].type == "RB"
                ):
                    pos += 1
                    idx = tokens[pos + 1].val  # Should be a number or ..it::
                    if idx == "..it::" and iter_id is None:
                        result += str(idx)
                    elif idx == "..it::" and iter_id is not None:
                        result += str(iter_id)
                    else:
                        result += str(self.env.get(key[2:-2], key)[int(idx)])

                    pos += 3
                else:
                    if key == "..it::" and iter_id is None:
                        result += str(idx)
                    elif key == "..it::" and iter_id is not None:
                        result += str(iter_id)
                    else:
                        result += str(self.env.get(key[2:-2], key))

                    pos += 1

            else:
                result += token.val
                pos += 1
        return result

    def eval(self) -> str:
        """Evaluate a template.

        Returns:
            Result of evaluating the template.
        """
        return self.parse(self.tokenize())
