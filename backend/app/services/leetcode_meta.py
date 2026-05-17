"""Pulls problem metadata (slug, difficulty, is_paid_only) from LeetCode's public GraphQL.

LeetCode does not publish an official API. The GraphQL endpoint at
https://leetcode.com/graphql is used by the website itself; rate-limit kindly.
"""
from __future__ import annotations

import time
from typing import Iterator

import httpx

GRAPHQL_URL = "https://leetcode.com/graphql"

_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      questionFrontendId
      title
      titleSlug
      difficulty
      isPaidOnly
      acRate
      topicTags { name slug }
    }
  }
}
"""


def fetch_all(rate_limit_s: float = 1.1, page_size: int = 100) -> Iterator[dict]:
    """Yield every problem metadata record. ~3000 problems => ~30 pages."""
    skip = 0
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (interview-prep ingest)",
        "Referer": "https://leetcode.com/problemset/all/",
    }
    with httpx.Client(timeout=30.0) as client:
        while True:
            resp = client.post(
                GRAPHQL_URL,
                headers=headers,
                json={
                    "operationName": "problemsetQuestionList",
                    "query": _QUERY,
                    "variables": {
                        "categorySlug": "",
                        "skip": skip,
                        "limit": page_size,
                        "filters": {},
                    },
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload["data"]["problemsetQuestionList"]
            qs = data["questions"]
            if not qs:
                return
            for q in qs:
                yield {
                    "id": int(q["questionFrontendId"]),
                    "title": q["title"],
                    "slug": q["titleSlug"],
                    "difficulty": q["difficulty"],
                    "is_premium": bool(q["isPaidOnly"]),
                    "acceptance_pct": q.get("acRate"),
                    "topics": [t["slug"] for t in q.get("topicTags") or []],
                }
            skip += page_size
            if skip >= data["total"]:
                return
            time.sleep(rate_limit_s)
