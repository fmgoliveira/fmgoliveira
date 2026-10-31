#!/usr/bin/env python3
"""Generate assets/activity.svg: animated contribution bars, stat tiles and a language bar.

Usage:
  GH_TOKEN=... GH_LOGIN=fmgoliveira python scripts/generate_activity.py
  python scripts/generate_activity.py --sample sample.json   # offline preview

Only the Python standard library is needed.
"""
import argparse
import datetime as dt
import json
import os
import urllib.request
from collections import defaultdict

QUERY = """
query($login:String!){
  user(login:$login){
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
      totalCount
      nodes{ languages(first:8, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } }
    }
    contributionsCollection{
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount } } }
    }
  }
}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]


def summarize(user):
    cc = user["contributionsCollection"]
    cal = cc["contributionCalendar"]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]]
    # Languages: normalise per repo so one huge data repo cannot dominate.
    share = defaultdict(float)
    colors = {}
    for repo in user["repositories"]["nodes"]:
        edges = repo["languages"]["edges"]
        total = sum(e["size"] for e in edges)
        for e in edges:
            share[e["node"]["name"]] += e["size"] / total
            colors[e["node"]["name"]] = e["node"]["color"] or "#8b949e"
    top = sorted(share.items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in top)
    langs = [(n, v / total, colors[n]) for n, v in top]
    return {
        "weeks": weeks,
        "total": cal["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "repos": user["repositories"]["totalCount"],
        "langs": langs,
    }


W, H = 900, 372
PAD = 36


def render(s):
    weeks = s["weeks"][-52:]
    srt = sorted(weeks)
    cap = max(srt[int(len(srt) * 0.92)], 1)  # clip outliers so the chart stays readable
    chart_top, chart_h = 168, 96
    base = chart_top + chart_h
    pitch = (W - 2 * PAD) / len(weeks)
    bw = pitch * 0.68

    bars = []
    for i, v in enumerate(weeks):
        h = max(3.0, min(v / cap, 1.0) * chart_h)
        x = PAD + i * pitch + (pitch - bw) / 2
        cls = "bar last" if i == len(weeks) - 1 else "bar"
        fill = "url(#bar)" if v else "#ffffff22"
        bars.append(
            f'<rect class="{cls}" x="{x:.1f}" y="{base - h:.1f}" width="{bw:.1f}" height="{h:.1f}" '
            f'rx="{min(3, bw / 2):.1f}" fill="{fill}" style="animation-delay:{0.6 + i * 0.022:.2f}s"/>'
        )

    tiles = [("Contributions", s["total"]), ("Commits", s["commits"]), ("Pull requests", s["prs"]), ("Public repos", s["repos"])]
    tile_w = (W - 2 * PAD) / 4
    tile_svg = []
    for i, (label, val) in enumerate(tiles):
        x = PAD + i * tile_w
        tile_svg.append(
            f'<g class="tile" style="animation-delay:{0.15 + i * 0.12:.2f}s">'
            f'<text x="{x:.0f}" y="96" class="num">{val:,}</text>'
            f'<text x="{x:.0f}" y="118" class="lbl">{label}</text></g>'
        )

    # language bar
    lb_y, lb_w = 300, W - 2 * PAD
    segs, legend = [], []
    x = PAD
    for i, (name, frac, color) in enumerate(s["langs"]):
        w = lb_w * frac
        segs.append(f'<rect x="{x:.1f}" y="{lb_y}" width="{w + 1:.1f}" height="10" fill="{color}"/>')
        lx = PAD + i * (lb_w / len(s["langs"]))
        legend.append(
            f'<g class="tile" style="animation-delay:{1.6 + i * 0.1:.1f}s">'
            f'<circle cx="{lx + 5:.0f}" cy="337" r="5" fill="{color}"/>'
            f'<text x="{lx + 17:.0f}" y="341" class="leg">{name} <tspan class="pct">{frac * 100:.0f}%</tspan></text></g>'
        )
        x += w

    today = dt.date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub activity over the last 12 months">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1020"/><stop offset="1" stop-color="#141a33"/></linearGradient>
  <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#67e8f9"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient>
  <clipPath id="lang"><rect x="{PAD}" y="{lb_y}" width="{lb_w}" height="10" rx="5"/></clipPath>
</defs>
<style>
  text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}
  .ttl{{fill:#e5e7eb;font-size:15px;font-weight:600;letter-spacing:.3px}}
  .sub{{fill:#6b7280;font-size:12px}}
  .num{{fill:#f9fafb;font-size:34px;font-weight:700}}
  .lbl{{fill:#9ca3af;font-size:13px}}
  .leg{{fill:#d1d5db;font-size:13px}} .pct{{fill:#6b7280}}
  .tile{{opacity:0;animation:rise .8s cubic-bezier(.2,.8,.2,1) forwards}}
  @keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
  .bar{{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);animation:grow .9s cubic-bezier(.2,.8,.2,1) forwards}}
  @keyframes grow{{to{{transform:scaleY(1)}}}}
  .last{{animation:grow .9s cubic-bezier(.2,.8,.2,1) forwards,glow 2.4s ease-in-out 2.2s infinite}}
  @keyframes glow{{50%{{filter:drop-shadow(0 0 6px #67e8f9)}}}}
  .langs{{transform-box:fill-box;transform-origin:0 50%;transform:scaleX(0);animation:wipe 1.3s cubic-bezier(.2,.8,.2,1) 1.2s forwards}}
  @keyframes wipe{{to{{transform:scaleX(1)}}}}
  .scan{{animation:scan 6s linear infinite;opacity:.5}}
  @keyframes scan{{from{{transform:translateX(-120px)}}to{{transform:translateX({W}px)}}}}
  @media (prefers-reduced-motion:reduce){{*{{animation-duration:.01s!important;animation-delay:0s!important}}}}
</style>
<rect width="{W}" height="{H}" rx="20" fill="url(#bg)"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="19.5" fill="none" stroke="#ffffff" stroke-opacity=".08"/>
<text x="{PAD}" y="44" class="ttl">Activity</text>
<text x="{W - PAD}" y="44" class="sub" text-anchor="end">last 12 months · updated {today}</text>
{''.join(tile_svg)}
<line x1="{PAD}" y1="{base + 6}" x2="{W - PAD}" y2="{base + 6}" stroke="#ffffff" stroke-opacity=".08"/>
{''.join(bars)}
<rect class="scan" x="0" y="{base + 5}" width="120" height="2" fill="url(#bar)"/>
<g clip-path="url(#lang)"><rect x="{PAD}" y="{lb_y}" width="{lb_w}" height="10" fill="#ffffff10"/><g class="langs">{''.join(segs)}</g></g>
{''.join(legend)}
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="JSON file with a pre-summarised payload (skips the API)")
    ap.add_argument("--out", default="assets/activity.svg")
    args = ap.parse_args()
    if args.sample:
        s = json.load(open(args.sample))
        s["langs"] = [tuple(l) for l in s["langs"]]
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        login = os.environ.get("GH_LOGIN", "fmgoliveira")
        s = summarize(fetch(login, token))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(render(s))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
