#!/usr/bin/env python3
"""Generate contribution, language, and stack SVGs for a GitHub profile README."""

import html
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone

API = "https://api.github.com/graphql"
WIDTH = 760

# Stats are calculated over all of 2026, while the daily chart starts in March.
YEAR_START = date(2026, 1, 1)
CHART_START = date(2026, 3, 1)

EXCLUDED = {"Jupyter Notebook"}

# Static technology/tool stack shown on the profile.
STACK = [
    ("Python", "#3776AB", "#FFFFFF"),
    ("Bash / Shell", "#4EAA25", "#FFFFFF"),
    ("C++", "#00599C", "#FFFFFF"),
    ("HTML5", "#E34F26", "#FFFFFF"),
    ("CSS3", "#1572B6", "#FFFFFF"),
    ("JavaScript", "#F7DF1E", "#111111"),
    ("Git", "#F05032", "#FFFFFF"),
    ("Linux", "#FCC624", "#111111"),
    ("Docker", "#2496ED", "#FFFFFF"),
    ("Jupyter", "#F37626", "#FFFFFF"),
    ("GitHub Actions", "#2088FF", "#FFFFFF"),
]

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
    start = YEAR_START if today >= YEAR_START else today

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


def flatten_days(calendar):
    return [
        d
        for week in calendar["weeks"]
        for d in week["contributionDays"]
    ]


def contribution_summary(calendar):
    """Return 2026 totals and peak day/week/month statistics."""
    days = flatten_days(calendar)
    counts = [int(d["contributionCount"]) for d in days]

    total = int(calendar.get("totalContributions", sum(counts)))
    active = sum(v > 0 for v in counts)
    peak_day = max(counts, default=0)

    weekly = [
        sum(int(d["contributionCount"]) for d in week["contributionDays"])
        for week in calendar["weeks"]
    ]
    peak_week = max(weekly, default=0)

    monthly = defaultdict(int)
    for d in days:
        dt = date.fromisoformat(d["date"])
        monthly[(dt.year, dt.month)] += int(d["contributionCount"])

    if monthly:
        peak_month_key, peak_month = max(monthly.items(), key=lambda item: item[1])
        peak_month_name = date(peak_month_key[0], peak_month_key[1], 1).strftime("%b")
    else:
        peak_month, peak_month_name = 0, ""

    return {
        "total": total,
        "active": active,
        "peak_month": peak_month,
        "peak_month_name": peak_month_name,
        "peak_week": peak_week,
        "peak_day": peak_day,
    }


def draw_stats(login, calendar):
    """
    Draw 2026 summary statistics plus a daily chart beginning 1 March 2026.

    The daily chart uses square-root scaling so normal 10–20 contribution days
    remain visually meaningful even when a much larger outlier day is present.
    """
    height = 220
    left, right = 4, WIDTH - 4
    chart_left, chart_right = 4, WIDTH - 4
    chart_top, base = 122, 196
    chart_height = base - chart_top

    stats = contribution_summary(calendar)

    days = [
        d for d in flatten_days(calendar)
        if date.fromisoformat(d["date"]) >= CHART_START
    ]

    if not days:
        days = [{"date": CHART_START.isoformat(), "contributionCount": 0}]

    chart_counts = [int(d["contributionCount"]) for d in days]
    chart_peak = max(chart_counts, default=0)
    scale_peak = max(chart_peak, 1)
    step = (chart_right - chart_left) / max(len(days) - 1, 1)

    title = f"{stats['total']} contributions in 2026"
    description = (
        f"{stats['active']} active days, peak month {stats['peak_month']} "
        f"({stats['peak_month_name']}), peak week {stats['peak_week']}, "
        f"and peak day {stats['peak_day']}. Daily chart begins Mar 2026."
    )

    out = svg_head(height, title, description)

    # Main 2026 total on the left.
    out.extend(
        [
            (
                f'<text x="{left}" y="52" class="ink" font-size="54" '
                f'font-weight="600">{stats["total"]}</text>'
            ),
            (
                f'<text x="{left}" y="78" class="muted" font-size="13">'
                "contributions in 2026</text>"
            ),
        ]
    )

    # Four compact stat blocks on the right, all next to one another.
    stat_blocks = [
        (stats["active"], "active days", ""),
        (stats["peak_month"], "peak month", stats["peak_month_name"]),
        (stats["peak_week"], "peak week", ""),
        (stats["peak_day"], "peak day", ""),
    ]

    first_x = 392
    block_w = 91

    for i, (value, label, sublabel) in enumerate(stat_blocks):
        x = first_x + i * block_w

        out.append(
            f'<text x="{x}" y="42" class="ink" font-size="22" '
            f'font-weight="600" text-anchor="middle">{value}</text>'
        )
        out.append(
            f'<text x="{x}" y="63" class="muted" font-size="9.5" '
            f'text-anchor="middle">{label}</text>'
        )

        if sublabel:
            out.append(
                f'<text x="{x}" y="79" class="muted" font-size="9" '
                f'text-anchor="middle">{sublabel}</text>'
            )

    # Daily chart baseline.
    out.append(
        f'<line x1="{chart_left}" y1="{base}" x2="{chart_right}" y2="{base}" '
        'class="grid" stroke-width="1"/>'
    )

    # Month separators + labels.
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

    # Daily stems + dots.
    for i, day in enumerate(days):
        count = int(day["contributionCount"])
        if count <= 0:
            continue

        x = chart_left + i * step
        scaled = (count / scale_peak) ** 0.5
        y = base - max(2.0, scaled * chart_height)
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


def draw_stack():
    """Draw a compact, colored technology-stack badge card."""
    height = 132
    out = svg_head(
        height,
        "Technology stack",
        "Python, Bash and Shell, C++, HTML5, CSS3, JavaScript, Git, Linux, "
        "Docker, Jupyter, and GitHub Actions.",
    )

    out.extend(
        [
            '<text x="4" y="28" class="ink" font-size="22" font-weight="600">stack</text>',
            '<line x1="72" y1="21" x2="756" y2="21" class="grid" stroke-width="1"/>',
        ]
    )

    x, y = 4, 55
    gap_x, gap_y = 8, 12
    badge_h = 27

    # Slightly generous monospaced approximation; badges wrap automatically.
    for label, fill, text_fill in STACK:
        badge_w = max(58, 18 + len(label) * 7.2)

        if x + badge_w > WIDTH - 4:
            x = 4
            y += badge_h + gap_y

        safe_label = html.escape(label)
        out.extend(
            [
                (
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{badge_w:.1f}" '
                    f'height="{badge_h}" rx="6" fill="{fill}"/>'
                ),
                (
                    f'<text x="{x + badge_w / 2:.1f}" y="{y + 18:.1f}" '
                    f'fill="{text_fill}" font-size="11" font-weight="600" '
                    f'text-anchor="middle">{safe_label}</text>'
                ),
            ]
        )

        x += badge_w + gap_x

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

    if write_if_changed("stack.svg", draw_stack()):
        changed.append("stack.svg")

    print("updated: " + (", ".join(changed) if changed else "nothing"))


if __name__ == "__main__":
    main()
