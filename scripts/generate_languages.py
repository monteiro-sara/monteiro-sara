#!/usr/bin/env python3
"""Generate contribution and language SVGs for a GitHub profile README."""

import html
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

API = "https://api.github.com/graphql"
WIDTH = 760
STATS_START = date(2026, 3, 1)
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
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stat-graphics",
        },
    )
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
    start = STATS_START

    if today < start:
        start = today

    common = {
        "login": login,
        "from": f"{start}T00:00:00Z",
        "to": f"{today}T23:59:59Z",
    }

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
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
            f'height="{height}" viewBox="0 0 {WIDTH} {height}" '
            f'role="img" aria-labelledby="title desc">'
        ),
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        (
            "<style>"
            ":root{color-scheme:light dark}"
            ".bg{fill:#fff}"
            ".ink{fill:#1f2328}"
            ".muted{fill:#656d76}"
            ".line{stroke:#8c959f}"
            ".bar{fill:#8c959f}"
            ".stem{stroke:#8c959f}"
            ".dot{fill:#1f2328}"
            ".grid{stroke:#d8dee4}"
            ".track{fill:#eaeef2}"
            "@media(prefers-color-scheme:dark){"
            ".bg{fill:#0d1117}"
            ".ink{fill:#f0f6fc}"
            ".muted{fill:#8b949e}"
            ".line{stroke:#c9d1d9}"
            ".bar{fill:#c9d1d9}"
            ".stem{stroke:#8b949e}"
            ".dot{fill:#f0f6fc}"
            ".grid{stroke:#30363d}"
            ".track{fill:#30363d}"
            "}"
            'text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'
            '"Liberation Mono",monospace}'
            "</style>"
        ),
        f'<rect class="bg" width="{WIDTH}" height="{height}"/>',
    ]


def draw_stats(login, calendar):
    """
    Draw a daily contribution chart.

    Each calendar day gets its own vertical stem + dot. Heights use square-root
    scaling so normal 10–20 contribution days remain visible even when there is
    a much larger outlier day.
    """
    height = 220
    left, right = 4, WIDTH - 4
    chart_left, chart_right = 4, WIDTH - 4
    chart_top, base = 118, 196
    chart_height = base - chart_top

    days = [
        d
        for week in calendar["weeks"]
        for d in week["contributionDays"]
        if date.fromisoformat(d["date"]) >= STATS_START
    ]

    if not days:
        days = [{"date": STATS_START.isoformat(), "contributionCount": 0}]

    counts = [int(d["contributionCount"]) for d in days]
    total = sum(counts)
    active = sum(v > 0 for v in counts)
    peak = max(counts) if counts else 0

    # Prevent division by zero while keeping a sensible scale.
    scale_peak = max(peak, 1)

    # Daily points fill the width. With ~6 months of data this leaves enough
    # horizontal room for each day to remain visually distinct.
    step = (chart_right - chart_left) / max(len(days) - 1, 1)

    start_label = STATS_START.strftime("%b %Y")
    title = f"{total} contributions since {start_label}"
    description = (
        f"{active} active days and a peak day of {peak} contributions. "
        "Daily stem-and-dot heights use square-root scaling."
    )

    out = svg_head(height, title, description)

    # Summary text
    out.extend(
        [
            f'<text x="{left}" y="52" class="ink" font-size="54" font-weight="600">{total}</text>',
            (
                f'<text x="{left}" y="78" class="muted" font-size="13">'
                f'contributions since {start_label}</text>'
            ),
            (
                f'<text x="{right}" y="29" class="ink" font-size="22" '
                f'font-weight="600" text-anchor="end">{active}</text>'
            ),
            (
                f'<text x="{right}" y="49" class="muted" font-size="11" '
                'text-anchor="end">active days</text>'
            ),
            (
                f'<text x="{right}" y="78" class="ink" font-size="22" '
                f'font-weight="600" text-anchor="end">{peak}</text>'
            ),
            (
                f'<text x="{right}" y="98" class="muted" font-size="11" '
                'text-anchor="end">peak day</text>'
            ),
        ]
    )

    # Baseline
    out.append(
        f'<line x1="{chart_left}" y1="{base}" x2="{chart_right}" y2="{base}" '
        'class="grid" stroke-width="1"/>'
    )

    # Month separators + month labels
    previous_month = None

    for i, day in enumerate(days):
        d = date.fromisoformat(day["date"])
        month_key = (d.year, d.month)

        if month_key != previous_month:
            x = chart_left + i * step

            if i != 0:
                out.append(
                    f'<line x1="{x:.2f}" y1="{chart_top}" x2="{x:.2f}" y2="{base}" '
                    'class="grid" stroke-width="1" stroke-dasharray="2 4"/>'
                )

            out.append(
                f'<text x="{x + 3:.2f}" y="{chart_top - 7}" class="muted" '
                f'font-size="10">{d.strftime("%b")}</text>'
            )
            previous_month = month_key

    # Daily stems + dots
    # Square-root scaling compresses the extreme outlier without hiding it.
    for i, day in enumerate(days):
        count = int(day["contributionCount"])
        if count <= 0:
            continue

        x = chart_left + i * step
        scaled = (count / scale_peak) ** 0.5
        y = base - max(2.0, scaled * chart_height)

        # Very small dots can disappear at GitHub README scale, so use a
        # slightly larger radius for higher-count days.
        radius = 1.6 + min(1.8, 1.8 * scaled)

        out.extend(
            [
                "<g>",
                (
                    f"<title>{html.escape(day['date'])}: "
                    f"{count} contribution{'s' if count != 1 else ''}</title>"
                ),
                (
                    f'<line x1="{x:.2f}" y1="{base}" x2="{x:.2f}" y2="{y:.2f}" '
                    'class="stem" stroke-width="1.35" stroke-linecap="round"/>'
                ),
                (
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
                    'class="dot"/>'
                ),
                "</g>",
            ]
        )

    out.append("</svg>")
    return "".join(out)


def draw_languages(login, totals, repo_counts):
    height = 220
    by_bytes = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    by_repos = sorted(repo_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    total = sum(totals.values()) or 1

    out = svg_head(
        height,
        f"Languages used by {login}",
        "Top languages by code bytes and repository count.",
    )

    groups = [
        (40, "BY BYTES", by_bytes, True),
        (425, "BY REPOS", by_repos, False),
    ]

    for gx, heading, data, percentages in groups:
        out.append(
            f'<text x="{gx}" y="30" class="muted" font-size="10" '
            f'letter-spacing="1.6">{heading}</text>'
        )

        peak = max((value for _, value in data), default=1)

        for row, (name, value) in enumerate(data):
            y = 57 + row * 29
            bar_x, bar_w = gx + 102, 188
            shown = f"{value / total * 100:.0f}%" if percentages else str(value)

            out.extend(
                [
                    (
                        f'<text x="{gx}" y="{y}" class="ink" font-size="12" '
                        f'font-weight="600">{html.escape(name.lower())}</text>'
                    ),
                    (
                        f'<rect x="{bar_x}" y="{y - 10}" width="{bar_w}" '
                        'height="9" rx="3" class="track"/>'
                    ),
                    (
                        f'<rect x="{bar_x}" y="{y - 10}" '
                        f'width="{max(4, bar_w * value / max(peak, 1)):.1f}" '
                        'height="9" rx="3" class="bar"/>'
                    ),
                    (
                        f'<text x="{gx + 340}" y="{y}" class="muted" '
                        f'font-size="11" text-anchor="end">{shown}</text>'
                    ),
                ]
            )

    out.append("</svg>")
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
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")

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
