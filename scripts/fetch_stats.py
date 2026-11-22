#!/usr/bin/env python3
"""Refresh the GitHub stats block in README.md.

Reads the profile repo's own README, replaces everything between the
`<!-- STATS:START -->` and `<!-- STATS:END -->` markers with a freshly
generated neofetch-style stats section, and writes the file back.

Environment:
    GITHUB_TOKEN   token with at least public repo read scope
    GH_LOGIN       username (defaults to the token's owner)

Run by .github/workflows/update.yml on a schedule; can also be run by hand.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
START = "<!-- STATS:START -->"
END = "<!-- STATS:END -->"


def request(url: str, token: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "neofetch-profile-updater")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    bio
    location
    company
    websiteUrl
    createdAt
    followers { totalCount }
    following { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
      totalCount
    }
    starredRepositories { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
    }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) {
      totalCount
    }
  }
}
"""

STARS_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(
      first: 100
      after: $after
      privacy: PUBLIC
      ownerAffiliations: OWNER
      isFork: false
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
  }
}
"""

LANGS_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(
      first: 100
      privacy: PUBLIC
      ownerAffiliations: OWNER
      isFork: false
      orderBy: { field: PUSHED_AT, direction: DESC }
    ) {
      nodes {
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def gql(query: str, variables: dict, token: str) -> dict:
    payload = request(GRAPHQL, token, {"query": query, "variables": variables})
    if "errors" in payload:
        raise RuntimeError("GraphQL error: " + payload["errors"][0]["message"])
    return payload["data"]


def total_stars(login: str, token: str) -> int:
    total, after = 0, None
    while True:
        page = gql(STARS_QUERY, {"login": login, "after": after}, token)["user"]["repositories"]
        total += sum(node["stargazerCount"] for node in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return total
        after = page["pageInfo"]["endCursor"]


def top_languages(login: str, token: str, limit: int = 4) -> list[tuple[str, int]]:
    sizes: dict[str, int] = {}
    nodes = gql(LANGS_QUERY, {"login": login}, token)["user"]["repositories"]["nodes"]
    for repo in nodes:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:limit]


def approximate_lines(login: str, token: str) -> int:
    """Contribution calendar is the only cheap proxy GitHub gives us."""
    year = gql(
        "query($login: String!) { user(login: $login) "
        "{ contributionsCollection { totalCommitContributions } } }",
        {"login": login},
        token,
    )
    commits = year["user"]["contributionsCollection"]["totalCommitContributions"]
    # ~60 changed lines per commit is a rough but stable estimate.
    return commits * 60


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def uptime(created: str) -> str:
    born = datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - born).days
    years, rest = divmod(days, 365)
    months = rest // 30
    if years and months:
        return f"{years} years, {months} months"
    if years:
        return f"{years} years"
    return f"{months} months"


def build(user: dict, stars: int, langs: list[tuple[str, int]], lines: int) -> str:
    name = user.get("name") or user["login"]
    langs_text = ", ".join(name_ for name_, _ in langs) or "—"
    contrib = user["contributionsCollection"]
    rows = [
        ("OS", "Windows 11 / Android"),
        ("Uptime", uptime(user["createdAt"])),
        ("Host", "GitHub"),
        ("Kernel", "git " + (name.lower().replace(" ", "-"))),
        ("IDE", "VS Code"),
        ("Shell", "PowerShell"),
        ("Languages", langs_text),
        ("Hobbies", "coding, music, exploring"),
        ("Contact", user["login"] + "@github"),
        ("Website", user.get("websiteUrl") or "—"),
    ]
    width = max(len(k) for k, _ in rows) + 1
    out = [f"{user['login']}@github", "-" * (width + 26)]
    for key, value in rows:
        out.append(f"{key:<{width}}: {value}")
    out.append("")
    out.append("- GitHub Stats")
    out.append(
        f"{'Repos':<{width}}: {user['repositories']['totalCount']}"
        f"    {'Stars':<{width}}: {stars}"
    )
    out.append(
        f"{'Commits':<{width}}: {contrib['totalCommitContributions']}"
        f"    {'PRs':<{width}}: {contrib['totalPullRequestContributions']}"
    )
    out.append(
        f"{'Issues':<{width}}: {contrib['totalIssueContributions']}"
        f"    {'Followers':<{width}}: {user['followers']['totalCount']}"
    )
    out.append(f"{'Lines (est.)':<{width}}: {human(lines)}")
    out.append("")
    out.append(f"_updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    return "\n".join(out)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("missing GITHUB_TOKEN", file=sys.stderr)
        return 1
    login = os.environ.get("GH_LOGIN") or gql(
        "query { viewer { login } }", {}, token
    )["viewer"]["login"]

    user = gql(USER_QUERY, {"login": login}, token)["user"]
    if user is None:
        print(f"user {login} not found", file=sys.stderr)
        return 1

    block = build(user, total_stars(login, token), top_languages(login, token), approximate_lines(login, token))

    readme_path = "README.md"
    with open(readme_path, encoding="utf-8") as fh:
        text = fh.read()
    head, sep, tail = text.partition(START)
    if not sep:
        print("missing STATS markers in README", file=sys.stderr)
        return 1
    _, _, rest = tail.partition(END)
    with open(readme_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(head + START + "\n```\n" + block + "\n```\n" + END + rest)
    print(f"updated stats for {login}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
