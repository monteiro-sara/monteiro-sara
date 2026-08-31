#!/usr/bin/env python3
"""Generate contribution and language SVGs for a GitHub profile README."""

import html
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

API = "https://api.github.com/graphql"
WIDTH = 760
EXCLUDED = {"Jupyter Notebook"}
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!, $after: String) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER,
                 isFork: false, privacy: PUBLIC,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 30, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def request(token, variables):
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "profile-stat-graphics"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise RuntimeError("GitHub user was not found")
    return user


def collect(login, token):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    common = {"login": login, "from": f"{start}T00:00:00Z",
              "to": f"{today}T23:59:59Z"}
    totals, repo_counts = defaultdict(int), defaultdict(int)
    after, calendar = None, None
    while True:
        user = request(token, {**common, "after": after})
        if calendar is None:
            calendar = user["contributionsCollection"]["contributionCalendar"]
        repos = user["repositories"]
        for repository in repos["nodes"]:
            primary = None
            for edge in (repository.get("languages") or {}).get("edges") or []:
                name = edge["node"]["name"]
                if name in EXCLUDED:
                    continue
                totals[name] += int(edge["size"])
                primary = primary or name
            if primary:
                repo_counts[primary] += 1
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    return calendar, totals, repo_counts


def svg_head(height, title, description):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        '<style>:root{color-scheme:light dark}.bg{fill:#fff}.ink{fill:#1f2328}.muted{fill:#656d76}.line{stroke:#8c959f}.bar{fill:#8c959f}.area{fill:#8c959f;opacity:.2}.track{fill:#eaeef2}@media(prefers-color-scheme:dark){.bg{fill:#0d1117}.ink{fill:#f0f6fc}.muted{fill:#8b949e}.line{stroke:#c9d1d9}.bar{fill:#c9d1d9}.area{fill:#c9d1d9;opacity:.2}.track{fill:#30363d}}text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}</style>',
        f'<rect class="bg" width="{WIDTH}" height="{height}"/>']


def draw_stats(login, calendar):
    height, left, right = 180, 4, WIDTH - 4
    weeks = calendar["weeks"]
    weekly = [sum(day["contributionCount"] for day in w["contributionDays"])
              for w in weeks]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = calendar["totalContributions"]
    active = sum(d["contributionCount"] > 0 for d in days)
    best = max(weekly) if weekly else 0
    peak = max(weekly) if weekly else 1
    base, top = 160, 102
    step = (right - left) / max(len(weekly) - 1, 1)
    points = [(left + i * step, base - (v / max(peak, 1)) * (base - top))
              for i, v in enumerate(weekly or [0])]
    line = " ".join(f"L{x:.1f},{y:.1f}" for x, y in points[1:])
    area = (f"M{points[0][0]:.1f},{base} L{points[0][0]:.1f},{points[0][1]:.1f} "
            f"{line} L{points[-1][0]:.1f},{base} Z")
    path = f"M{points[0][0]:.1f},{points[0][1]:.1f} {line}"
    out = svg_head(height, f"{total} contributions in the last year",
                   f"{active} active days and a best week of {best} contributions.")
    out.extend([
        f'<text x="4" y="52" class="ink" font-size="54" font-weight="600">{total}</text>',
        '<text x="4" y="78" class="muted" font-size="13">contributions in the last year</text>',
        f'<text x="{right}" y="29" class="ink" font-size="22" font-weight="600" text-anchor="end">{active}</text>',
        f'<text x="{right}" y="49" class="muted" font-size="11" text-anchor="end">active days</text>',
        f'<text x="{right}" y="78" class="ink" font-size="22" font-weight="600" text-anchor="end">{best}</text>',
        f'<text x="{right}" y="98" class="muted" font-size="11" text-anchor="end">best week</text>',
        f'<path d="{area}" class="area"/>',
        f'<path d="{path}" class="line" fill="none" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>',
        f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="4" class="ink"/>',
        '</svg>'])
    return "".join(out)


def draw_languages(login, totals, repo_counts):
    height = 220
    by_bytes = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    by_repos = sorted(repo_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    total = sum(totals.values()) or 1
    out = svg_head(height, f"Languages used by {login}",
                   "Top languages by code bytes and repository count.")
    groups = [(40, "BY BYTES", by_bytes, True),
              (425, "BY REPOS", by_repos, False)]
    for gx, heading, data, percentages in groups:
        out.append(f'<text x="{gx}" y="30" class="muted" font-size="10" letter-spacing="1.6">{heading}</text>')
        peak = max((value for _, value in data), default=1)
        for row, (name, value) in enumerate(data):
            y = 57 + row * 29
            bar_x, bar_w = gx + 102, 188
            shown = f"{value / total * 100:.0f}%" if percentages else str(value)
            out.extend([
                f'<text x="{gx}" y="{y}" class="ink" font-size="12" font-weight="600">{html.escape(name.lower())}</text>',
                f'<rect x="{bar_x}" y="{y - 10}" width="{bar_w}" height="9" rx="3" class="track"/>',
                f'<rect x="{bar_x}" y="{y - 10}" width="{max(4, bar_w * value / max(peak, 1)):.1f}" height="9" rx="3" class="bar"/>',
                f'<text x="{gx + 340}" y="{y}" class="muted" font-size="11" text-anchor="end">{shown}</text>'])
    out.append('</svg>')
    return "".join(out)


def write_if_changed(path, content):
    previous = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            previous = handle.read()
    if previous == content:
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return True


def main():
    token, login = os.environ.get("GITHUB_TOKEN"), os.environ.get("GH_LOGIN")
    if not token or not login:
        sys.exit("GITHUB_TOKEN and GH_LOGIN are required")
    calendar, totals, repo_counts = collect(login, token)
    changed = []
    if write_if_changed("stats.svg", draw_stats(login, calendar)):
        changed.append("stats.svg")
    if write_if_changed("languages.svg", draw_languages(login, totals, repo_counts)):
        changed.append("languages.svg")
    print("updated: " + (", ".join(changed) if changed else "nothing"))


if __name__ == "__main__":
    main()
