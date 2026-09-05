STACK = [
    "Python",
    "Bash",
    "Shell",
    "C++",
    "HTML5",
    "CSS3",
    "JavaScript",
    "Git",
    "Linux",
    "Docker",
    "Jupyter",
]


def draw_stack():
    """Draw a compact GitHub-style technology stack card."""

    height = 84

    out = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
            f'height="{height}" viewBox="0 0 {WIDTH} {height}" '
            f'role="img" aria-labelledby="title desc">'
        ),
        '<title id="title">Technology stack</title>',
        (
            '<desc id="desc">'
            'Python, Bash, Shell, C++, HTML5, CSS3, JavaScript, '
            'Git, Linux, Docker, Jupyter.'
            '</desc>'
        ),
        """
<style>
:root{color-scheme:light dark}
.bg{fill:#ffffff}
.ink{fill:#1f2328}
.grid{stroke:#d8dee4}
.stack-badge{fill:#f6f8fa;stroke:#d0d7de;stroke-width:1}
.stack-text{fill:#24292f;letter-spacing:.15px}
.stack-dot{fill:#2da44e}

@media(prefers-color-scheme:dark){
  .bg{fill:#0d1117}
  .ink{fill:#f0f6fc}
  .grid{stroke:#30363d}
  .stack-badge{fill:#161b22;stroke:#30363d}
  .stack-text{fill:#e6edf3}
  .stack-dot{fill:#3fb950}
}

text{
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,
  "Liberation Mono",monospace
}
</style>
""",
        f'<rect class="bg" width="{WIDTH}" height="{height}"/>',
        '<text x="4" y="27" class="ink" font-size="20" font-weight="600">stack</text>',
        '<line x1="70" y1="20" x2="756" y2="20" class="grid" stroke-width="1"/>',
    ]

    x = 4
    y = 46
    badge_h = 30
    gap = 6

    widths = {
        "Python": 64,
        "Bash": 56,
        "Shell": 58,
        "C++": 56,
        "HTML5": 58,
        "CSS3": 56,
        "JavaScript": 94,
        "Git": 56,
        "Linux": 58,
        "Docker": 64,
        "Jupyter": 72,
    }

    for label in STACK:
        badge_w = widths[label]
        safe_label = html.escape(label)
        dot_x = x + 11
        text_x = x + badge_w / 2 + 4

        out.extend(
            [
                f'<rect x="{x}" y="{y}" width="{badge_w}" height="{badge_h}" rx="7" class="stack-badge"/>',
                f'<circle cx="{dot_x}" cy="{y + 15}" r="2.5" class="stack-dot"/>',
                (
                    f'<text x="{text_x}" y="{y + 19}" class="stack-text" '
                    f'font-size="10.5" font-weight="600" text-anchor="middle">'
                    f'{safe_label}</text>'
                ),
            ]
        )

        x += badge_w + gap

    out.append("</svg>")
    return "".join(out)
