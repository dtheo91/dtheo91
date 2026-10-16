"""
Generates dark_mode.svg and light_mode.svg for the GitHub profile README.

Edit the PROFILE section below, then run:
    ACCESS_TOKEN=ghp_... USER_NAME=dtheo91 python today.py

Without ACCESS_TOKEN the stats fall back to the last cached values (or "–").
"""

import datetime as dt
import json
import os
import time
from html import escape
from pathlib import Path

import requests

ROOT = Path(__file__).parent
USER = os.environ.get("USER_NAME", "dtheo91")
TOKEN = os.environ.get("ACCESS_TOKEN")
CACHE = ROOT / "cache" / "stats.json"

# ───────────────────────────── PROFILE ─────────────────────────────
# Fill in your own details. Use None for an empty spacer line.
HEADER = "dtheo91@github"
BIRTHDAY = dt.date(1991, 12, 13)  # used for "Uptime"

PROFILE = [
    ("OS", "macOS"),
    ("Uptime", "{uptime}"),
    ("Host", "Wertgarantie Gruppe"),
    ("Kernel", "Machine Learning Engineer"),
    ("IDE", "VS Code, PyCharm, JupyterLab"),
    None,
    ("Languages.Programming", "Python, SQL"),
    ("Languages.Real", "German, English"),
    None,
    ("ML.Frameworks", "PyTorch, scikit-learn"),
    ("ML.Data", "NumPy, pandas"),
    ("ML.Ops", "MLflow, Docker, FastAPI"),
]

CONTACT = [
    ("Email", "dustintheobald@hotmail.de"),
    ("LinkedIn", "in/dustintheobald-ds"),
    ("Website", "dustintheobald.dev"),
]
# ───────────────────────────────────────────────────────────────────

WIDTH = 60  # characters per info line
FONT_SIZE = 14
CHAR_W = FONT_SIZE * 0.6
LINE_H = 18
INFO_X_CHARS = 38  # where the info column starts (in characters)

THEMES = {
    "dark_mode.svg": dict(bg="#161b22", text="#c9d1d9", key="#ffa657",
                          value="#a5d6ff", dots="#616e7f",
                          add="#3fb950", dele="#f85149"),
    "light_mode.svg": dict(bg="#f6f8fa", text="#24292f", key="#953800",
                           value="#0a3069", dots="#c2cfde",
                           add="#1a7f37", dele="#cf222e"),
}


# ───────────────────────────── stats ───────────────────────────────
def gql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"bearer {TOKEN}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_stats():
    q = """
    query($login: String!, $after: String) {
      user(login: $login) {
        id createdAt
        followers { totalCount }
        repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) { totalCount }
        repositories(first: 100, after: $after, ownerAffiliations: [OWNER], isFork: false) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { nameWithOwner stargazerCount }
        }
      }
    }"""
    repos, after = [], None
    while True:
        u = gql(q, {"login": USER, "after": after})["user"]
        repos += u["repositories"]["nodes"]
        page = u["repositories"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        after = page["endCursor"]

    # commits, year by year since account creation
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    cq = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions restrictedContributionsCount
        }
      }
    }"""
    commits, start = 0, created
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        c = gql(cq, {"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        cc = c["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        start = end

    # lines of code: additions/deletions authored by USER in own repos
    added = deleted = 0
    for repo in repos:
        weeks = contributor_weeks(repo["nameWithOwner"])
        added += sum(w["a"] for w in weeks)
        deleted += sum(w["d"] for w in weeks)

    return {
        "repos": u["repositories"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": u["followers"]["totalCount"],
        "commits": commits,
        "loc_add": added,
        "loc_del": deleted,
    }


def contributor_weeks(full_name):
    """GitHub computes these stats lazily and answers 202 until ready."""
    url = f"https://api.github.com/repos/{full_name}/stats/contributors"
    headers = {"Authorization": f"token {TOKEN}"}
    for _ in range(6):
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            for c in r.json() or []:
                if c.get("author") and c["author"]["login"].lower() == USER.lower():
                    return c["weeks"]
            return []
        if r.status_code == 202:
            time.sleep(5)
            continue
        return []
    return []


def load_stats():
    cached = json.loads(CACHE.read_text()) if CACHE.exists() else None
    if not TOKEN:
        return cached
    try:
        stats = fetch_stats()
        # if a repo's stats were still computing, keep the higher cached LOC
        if cached:
            for k in ("loc_add", "loc_del"):
                stats[k] = max(stats[k], cached.get(k, 0))
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(stats, indent=2))
        return stats
    except Exception as e:  # keep the README alive if the API hiccups
        print("stats fetch failed:", e)
        return cached


# ───────────────────────────── render ──────────────────────────────
def uptime(birthday, today=None):
    today = today or dt.date.today()
    y = today.year - birthday.year
    m = today.month - birthday.month
    d = today.day - birthday.day
    if d < 0:
        m -= 1
        prev_month = (today.replace(day=1) - dt.timedelta(days=1))
        d += prev_month.day
    if m < 0:
        y -= 1
        m += 12
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(y, 'year')}, {plural(m, 'month')}, {plural(d, 'day')}"


def fmt(n):
    return "–" if n is None else f"{n:,}"


def span(cls, text):
    return f'<tspan class="{cls}">{escape(text)}</tspan>'


def kv_line(key, value, width=WIDTH):
    """'. Key: ........ value' padded to a fixed width."""
    parts = key.split(".")
    dots = width - len(". ") - len(key) - len(": ") - len(value) - 1
    key_svg = span("cc", ".").join(span("key", p) for p in parts)
    return (span("cc", ". ") + key_svg + ":" + span("cc", " " + "." * max(dots, 1) + " ")
            + span("value", value))


def section(title, width=WIDTH):
    t = f"— {title} " if title else ""
    return escape(t + "—" * (width - len(t)))


def build_info(stats):
    s = stats or {}
    lines = [escape(HEADER) + " " + escape("—" * (WIDTH - len(HEADER) - 1))]
    for row in PROFILE:
        if row is None:
            lines.append(span("cc", ". "))
            continue
        k, v = row
        lines.append(kv_line(k, v.format(uptime=uptime(BIRTHDAY))))
    lines.append("")
    lines.append(section("Contact"))
    lines += [kv_line(k, v) for k, v in CONTACT]
    lines.append("")
    lines.append(section("GitHub Stats"))

    def half(key, value, width, lead=True):
        prefix = ". " if lead else ""
        dots = width - len(prefix) - len(key) - len(": ") - len(value) - 1
        return ((span("cc", prefix) if lead else "") + span("key", key) + ":" +
                span("cc", " " + "." * max(dots, 1) + " ") + span("value", value))

    repos = f"{fmt(s.get('repos'))}"
    contrib = f"{fmt(s.get('contributed'))}"
    left_w = 34
    repo_val = f"{repos} {{Contributed: {contrib}}}"
    # Repos line with coloured "Contributed"
    dots = left_w - len(". Repos: ") - len(repo_val) - 1
    repo_svg = (span("cc", ". ") + span("key", "Repos") + ":" +
                span("cc", " " + "." * max(dots, 1) + " ") + span("value", repos) +
                " {" + span("key", "Contributed") + ": " + span("value", contrib) + "}")
    sep = " | "
    right_w = WIDTH - left_w - len(sep)
    lines.append(repo_svg + sep + half("Stars", fmt(s.get("stars")), right_w, lead=False))
    lines.append(half("Commits", fmt(s.get("commits")), left_w) + sep +
                 half("Followers", fmt(s.get("followers")), right_w, lead=False))

    add, dele = s.get("loc_add"), s.get("loc_del")
    total = None if add is None else add - dele
    tail = f"{fmt(total)} ( {fmt(add)}++, {fmt(dele)}-- )"
    dots = WIDTH - len(". Lines of Code on GitHub: ") - len(tail) - 1
    lines.append(span("cc", ". ") + span("key", "Lines of Code on GitHub") + ":" +
                 span("cc", " " + "." * max(dots, 1) + " ") + span("value", fmt(total)) +
                 " ( " + span("add", f"{fmt(add)}++") + ", " + span("del", f"{fmt(dele)}--") + " )")
    return lines


def render(theme, art, info):
    rows = max(len(art), len(info))
    pad_top = 30
    height = pad_top + rows * LINE_H + 20
    width = int((INFO_X_CHARS + WIDTH) * CHAR_W + 45)
    # vertically centre the shorter block
    art_off = (rows - len(art)) // 2
    info_off = (rows - len(info)) // 2
    out = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,\'DejaVu Sans Mono\',Menlo,monospace" '
        f'width="{width}px" height="{height}px" font-size="{FONT_SIZE}px">',
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback'; "
        "font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        f".key {{fill: {theme['key']};}} .value {{fill: {theme['value']};}} .cc {{fill: {theme['dots']};}} "
        f".add {{fill: {theme['add']};}} .del {{fill: {theme['dele']};}} text, tspan {{white-space: pre;}}",
        "</style>",
        f'<rect width="{width}px" height="{height}px" fill="{theme["bg"]}" rx="15"/>',
        f'<text x="20" y="{pad_top}" fill="{theme["text"]}" class="ascii">',
    ]
    for i, line in enumerate(art):
        y = pad_top + (i + art_off) * LINE_H
        out.append(f'<tspan x="20" y="{y}">{escape(line)}</tspan>')
    out.append("</text>")
    x = int(20 + INFO_X_CHARS * CHAR_W)
    out.append(f'<text x="{x}" y="{pad_top}" fill="{theme["text"]}">')
    for i, line in enumerate(info):
        y = pad_top + (i + info_off) * LINE_H
        out.append(f'<tspan x="{x}" y="{y}">{line}</tspan>')
    out.append("</text>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    art = (ROOT / "ascii_art.txt").read_text().rstrip("\n").split("\n")
    info = build_info(load_stats())
    for name, theme in THEMES.items():
        (ROOT / name).write_text(render(theme, art, info))
    print("wrote", ", ".join(THEMES))


if __name__ == "__main__":
    main()
