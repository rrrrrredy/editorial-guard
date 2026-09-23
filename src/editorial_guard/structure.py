"""Bounded Markdown structure checks; semantic order still needs a judge."""
from collections import Counter
from html.parser import HTMLParser
import re
from urllib.parse import unquote


def prose_lines(text):
    lines = text.splitlines()
    visible = []
    fence = None
    yaml = bool(lines and lines[0] == "---")
    for i, line in enumerate(lines):
        if yaml:
            if i and line in ("---", "..."):
                yaml = False
            visible.append("")
            continue
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            visible.append("")
            continue
        if match:
            fence = match[1]
            visible.append("")
        elif line.startswith(("    ", "\t")) and not re.match(r"^\s*(?:\d+[.)]|[-+*])\s", line):
            # Indented code is outside prose. List continuation semantics are reviewed by the judge.
            visible.append("")
        else:
            visible.append(line)
    return visible


class HtmlParts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value is None:
                continue
            if key == "id" or (tag == "a" and key == "name"):
                self.ids.append(value)
            if key in ("href", "src"):
                self.links.append(value)


def inline_targets(text):
    """Read balanced inline destinations, including relative and fragment links."""
    out = []
    for match in re.finditer(r"(?<!\\)\]\(", text):
        i = match.end()
        while i < len(text) and text[i].isspace():
            i += 1
        start = i
        if i < len(text) and text[i] == "<":
            end = text.find(">", i + 1)
            if end >= 0:
                out.append(text[i + 1:end])
            continue
        depth = 0
        while i < len(text):
            c = text[i]
            if c == "\\" and i + 1 < len(text):
                i += 2
                continue
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    break
                depth -= 1
            elif c.isspace() and depth == 0:
                break
            i += 1
        out.append(text[start:i])
    return out


def snapshot(text):
    lines = prose_lines(text)
    headings, shape, steps = [], [], []
    for i, line in enumerate(lines):
        atx = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*#*\s*$", line)
        if atx:
            headings.append((len(atx[1]), atx[2]))
        elif i and lines[i - 1].strip() and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line):
            headings.append((1 if line.strip()[0] == "=" else 2, lines[i - 1].strip()))
        item = re.match(r"^(\s*)(\d+[.)]|[-+*])[ \t]+(.+)$", line)
        if item:
            ordered = item[2][0].isdigit()
            shape.append((len(item[1].expandtabs(4)), "ol" if ordered else "ul"))
            if ordered:
                steps.append(re.sub(r"\s+", " ", item[3]).strip())
    prose = "\n".join(lines)
    # Inline code is protected by the fidelity layer, not interpreted as links/HTML.
    prose = re.sub(r"(`+)([^`\n]*?)\1", "", prose)
    html = HtmlParts()
    html.feed(prose)
    refs = []
    for match in re.finditer(r"(?m)^ {0,3}\[([^]\n]+)\]:[ \t]*(?:<([^>\n]*)>|(\S+))", prose):
        refs.append((match[1].casefold(), match[2] if match[2] is not None else match[3]))
    uses = [m[1].casefold() for m in re.finditer(r"\[[^]\n]*\]\[([^]\n]+)\]", prose)]
    return {"headings": headings, "list_shape": shape, "ordered_steps": steps,
            "links": inline_targets(prose) + html.links, "reference_definitions": refs,
            "reference_uses": uses, "ids": html.ids}


def anchor_names(state):
    names = set(state["ids"])
    counts = Counter()
    for _, title in state["headings"]:
        # GitHub-style common headings. Nonstandard renderer rules are outside this check.
        slug = re.sub(r"[^\w\- ]", "", title.casefold()).replace(" ", "-")
        index = counts[slug]
        counts[slug] += 1
        names.add(slug if index == 0 else f"{slug}-{index}")
    return names


def structure_changes(original, candidate, *, allow_heading_edits=False):
    before, after = snapshot(original), snapshot(candidate)
    changes = []
    for key in ("links", "reference_definitions", "reference_uses", "ids", "list_shape"):
        if before[key] != after[key]:
            changes.append(key)
    if before["headings"] != after["headings"]:
        if not allow_heading_edits or [h[0] for h in before["headings"]] != [h[0] for h in after["headings"]]:
            changes.append("headings")
        else:
            old_anchors, new_anchors = anchor_names(before), anchor_names(after)
            for target in before["links"] + [v for _, v in before["reference_definitions"]]:
                fragment = unquote(target[1:]) if target.startswith("#") else None
                if fragment in old_anchors and fragment not in new_anchors:
                    changes.append("broken_local_anchor")
                    break
    # Reworded steps require semantic review. Detect permutations only when all texts are preserved.
    if (before["ordered_steps"] != after["ordered_steps"]
            and Counter(before["ordered_steps"]) == Counter(after["ordered_steps"])):
        changes.append("ordered_step_order")
    return changes
