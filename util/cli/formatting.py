try:
    from termcolor import colored
except ImportError:
    colored = None

import re


def none_str_list2list(v):
    if v is None:
        return []
    elif isinstance(v, str):
        return [v]
    elif isinstance(v, list):
        return v
    else:
        raise ValueError(
            f"Illegal parameter type ({type(v)} not in {{None, str, list}})"
        )


def none_or_str(v):
    if v is None or isinstance(v, str):
        return v
    else:
        raise ValueError(f"Illegal parameter type ({type(v)} not in {{None, str}})")


class Style:

    def __init__(self, content, color=None, bg=None, style=None):
        self.content = str(content)
        self.color = none_or_str(color)
        self.bg = none_or_str(bg)
        self.style = none_str_list2list(style)

    def merge(self, style):
        self.color = style.color
        self.bg = style.bg
        self.style = self.style.extend(style.style)

    def __str__(self):
        if colored:

            if "\x1b[0m" in self.content:
                style, term = re.split(
                    "@", colored("@", self.color, self.bg, attrs=self.style)
                )

                self.content = self.content.replace(term, f"{term}{style}")
                self.content = f"{self.content}{term}"

            return colored(self.content, self.color, self.bg, attrs=self.style)
        else:
            return self.content

    def __repr__(self):
        return f'("{(self.content, )}", {self.color}, {self.bg}, {self.style})'


def bold(text):
    return Style(text, style="bold")


def b(text):
    return bold(text)


def heading(text):
    return Style(text, style="bold", color="white")


def higlight(text):
    return Style(text, color="blue")


def h(text):
    return higlight(text)


def good(text):
    return Style(text, color="green")


def bad(text):
    return Style(text, color="red")


def debug(text):
    return Style(text, style="dark")


def warn(text):
    return Style(text, color="red")


def check():
    return Style("\N{HEAVY CHECK MARK}", color="green")
