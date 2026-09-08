#!/usr/bin/env python3
"""Fetch live GitHub numbers and render stats.svg.

Runs inside the profile repo's Action. With no token it falls back to sample
numbers so the layout can be checked locally.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

USER = os.environ.get("GH_USER", "azmain-arnob")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT", "stats.svg")

MONO = "ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,DejaVu Sans Mono,monospace"
SANS = "Segoe UI,Helvetica Neue,Helvetica,Arial,sans-serif"

QUERY = """
query($login:String!){
  user(login:$login){
    followers{ totalCount }
    publicRepos: repositories(privacy: PUBLIC, ownerAffiliations: OWNER){ totalCount }
    repositories(first:100, ownerAffiliations: OWNER, isFork:false){
      nodes{
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}){
          edges{ size node{ name color } }
        }
      }
    }
    contributionsCollection{
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar{ totalContributions }
    }
  }
}
"""


def fetch():
    if not TOKEN:
        return None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": "bearer " + TOKEN,
                 "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit("GraphQL error: %s" % payload["errors"])
    return payload["data"]["user"]


def collect(user):
    if user is None:                       # local preview
        return dict(repos=10, stars=4, followers=4, contributions=642, commits=498,
                    langs=[("Python", "#3572A5", 41.0), ("Jupyter Notebook", "#DA5B0B", 22.0),
                           ("JavaScript", "#f1e05a", 14.0), ("HTML", "#e34c26", 11.0),
                           ("CSS", "#563d7c", 7.0), ("Java", "#b07219", 5.0)])
    sizes, colors, stars = {}, {}, 0
    for repo in user["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#3E8CFF"
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    return dict(
        repos=user["publicRepos"]["totalCount"],
        stars=stars,
        followers=user["followers"]["totalCount"],
        contributions=user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        commits=user["contributionsCollection"]["totalCommitContributions"],
        langs=[(n, colors[n], round(s * 100.0 / total, 1)) for n, s in top],
    )


def render(d):
    W, H = 1200, 282
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC").upper()

    tiles = [("PUBLIC REPOS", d["repos"]), ("STARS EARNED", d["stars"]),
             ("FOLLOWERS", d["followers"]), ("CONTRIBUTIONS / YR", d["contributions"])]
    tw, tx0, ty = 276, 24, 58
    tile_svg = []
    for i, (label, value) in enumerate(tiles):
        x = tx0 + i * (tw + 12)
        tile_svg.append(
            f'<g class="tile t{i}">'
            f'<rect x="{x}" y="{ty}" width="{tw}" height="86" rx="10" fill="#0A1730" stroke="#1B2C4E"/>'
            f'<path d="M{x+11} {ty+30}V{ty+11}h19" fill="none" stroke="#3E8CFF" stroke-opacity="0.6" stroke-width="1.2"/>'
            f'<text x="{x+20}" y="{ty+48}" font-family="{SANS}" font-size="30" font-weight="700" fill="#EAF2FF">{value}</text>'
            f'<text x="{x+20}" y="{ty+70}" font-family="{MONO}" font-size="10.5" letter-spacing="1.8" fill="#63799C">{label}</text>'
            f'</g>')

    bars, by = [], 190
    for i, (name, color, pct) in enumerate(d["langs"]):
        col, row = i // 3, i % 3
        x = 24 + col * 588
        y = by + row * 27
        bars.append(
            f'<g class="bar b{i}">'
            f'<circle cx="{x+5}" cy="{y+7}" r="4.5" fill="{color}"/>'
            f'<text x="{x+18}" y="{y+11}" font-family="{MONO}" font-size="11.5" fill="#BDD4F2">{name}</text>'
            f'<text x="{x+544}" y="{y+11}" text-anchor="end" font-family="{MONO}" font-size="11" fill="#63799C">{pct}%</text>'
            f'<rect x="{x+180}" y="{y+3}" width="330" height="7" rx="3.5" fill="#101F3C"/>'
            f'<rect class="fill f{i}" x="{x+180}" y="{y+3}" width="{max(4, 330*pct/100.0):.1f}" height="7" rx="3.5" fill="{color}"/>'
            f'</g>')

    css = "\n".join(
        f"  .t{i} {{ animation: pop 12s ease-out infinite; animation-delay: {i*0.12:.2f}s }}"
        for i in range(len(tiles)))
    css += "\n" + "\n".join(
        f"  .f{i} {{ animation: grow 12s cubic-bezier(.2,.8,.2,1) infinite; animation-delay: {0.5+i*0.09:.2f}s }}"
        for i in range(len(bars)))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub statistics for {USER}">
<defs>
  <pattern id="ggrid" width="30" height="30" patternUnits="userSpaceOnUse">
    <path d="M30 0H0V30" fill="none" stroke="#3E8CFF" stroke-opacity="0.07" stroke-width="0.6"/>
  </pattern>
<style>
  .tile, .bar {{ transform-box: fill-box; }}
  .fill {{ transform-box: fill-box; transform-origin: left; }}
{css}
  @keyframes pop {{ 0% {{opacity:0; transform:translateY(8px)}} 7%,100% {{opacity:1; transform:translateY(0)}} }}
  @keyframes grow {{ 0%,4% {{transform:scaleX(0)}} 22%,100% {{transform:scaleX(1)}} }}
  .live {{ animation: blink 1.8s steps(1) infinite }}
  @keyframes blink {{ 0%,50% {{opacity:1}} 51%,100% {{opacity:0.25}} }}
</style>
</defs>
<rect width="{W}" height="{H}" rx="10" fill="#050A16"/>
<rect width="{W}" height="{H}" rx="10" fill="url(#ggrid)"/>
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="none" stroke="#1B2C4E"/>

<circle class="live" cx="32" cy="30" r="4.5" fill="#54D6A6"/>
<text x="46" y="34" font-family="{MONO}" font-size="12" letter-spacing="2.6" fill="#7FE3FF">LIVE FROM THE GITHUB API</text>
<text x="{W-24}" y="34" text-anchor="end" font-family="{MONO}" font-size="10.5" letter-spacing="1.6" fill="#4A5F82">UPDATED {stamp}</text>
<rect x="24" y="46" width="{W-48}" height="1" fill="#16233F"/>

{''.join(tile_svg)}

<text x="24" y="172" font-family="{MONO}" font-size="10.5" letter-spacing="2.4" fill="#4E8BE0">MOST USED LANGUAGES</text>
{''.join(bars)}
</svg>'''


if __name__ == "__main__":
    data = collect(fetch())
    open(OUT, "w").write(render(data))
    print("wrote", OUT, data["repos"], "repos,", data["stars"], "stars")
