from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp_client import MCPFilesystemClient


@dataclass
class CandidateResult:
    name: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    experience_match: bool


class MatchingState(TypedDict, total=False):
    job_description: str
    files: list[dict[str, Any]]
    processed: list[dict[str, Any]]
    results: list[CandidateResult]


def extract_skills(text: str) -> set[str]:
    known_skills = {
        "react",
        "node.js",
        "nodejs",
        "typescript",
        "javascript",
        "mongodb",
        "express",
        "python",
        "fastapi",
        "django",
        "postgresql",
        "redis",
        "docker",
        "aws",
        "redux",
        "html",
        "css",
        "rest apis",
        "git",
    }

    lowered = text.lower()

    found = set()

    for skill in known_skills:
        if skill in lowered:
            found.add(skill)

    return found


def extract_years(text: str) -> int:
    matches = re.findall(
        r"(\d+)\s*\+?\s*years?",
        text.lower(),
    )

    if not matches:
        return 0

    return max(int(value) for value in matches)


def match_resume(
    filename: str,
    resume_text: str,
    job_description: str,
) -> CandidateResult:

    required_skills = extract_skills(job_description)
    candidate_skills = extract_skills(resume_text)

    matched = sorted(
        required_skills.intersection(candidate_skills)
    )

    missing = sorted(
        required_skills - candidate_skills
    )

    required_years = extract_years(job_description)
    candidate_years = extract_years(resume_text)

    skill_score = (
        round(len(matched) / len(required_skills) * 70)
        if required_skills
        else 0
    )

    experience_match = candidate_years >= required_years

    experience_score = 30 if experience_match else 0

    score = min(
        100,
        skill_score + experience_score,
    )

    candidate_name = filename.rsplit(".", 1)[0]

    return CandidateResult(
        name=candidate_name,
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        experience_match=experience_match,
    )


async def run_matching(
    job_description: str,
) -> list[CandidateResult]:

    mcp_client = MCPFilesystemClient()

    async def discover_files(state: MatchingState) -> dict[str, Any]:
        files = await mcp_client.list_files(extensions=[".txt"])
        return {"files": files}

    async def process_files(state: MatchingState) -> dict[str, Any]:
        file_paths = [item["path"] for item in state["files"]]
        processed = await mcp_client.batch_process(file_paths)
        return {"processed": processed}

    async def match_candidates(state: MatchingState) -> dict[str, Any]:
        results = [
            match_resume(item["path"], item["content"], state["job_description"])
            for item in state["processed"]
            if item.get("status") == "success"
        ]
        results.sort(key=lambda candidate: candidate.score, reverse=True)
        return {"results": results}

    graph = StateGraph(MatchingState)
    graph.add_node("discover_files", discover_files)
    graph.add_node("process_files", process_files)
    graph.add_node("match_candidates", match_candidates)
    graph.add_edge(START, "discover_files")
    graph.add_edge("discover_files", "process_files")
    graph.add_edge("process_files", "match_candidates")
    graph.add_edge("match_candidates", END)

    workflow = graph.compile()
    final_state = await workflow.ainvoke({"job_description": job_description})
    return final_state["results"]


async def main():

    job_description = """
    Full Stack Developer

    Requirements:
    3+ years experience
    React
    Node.js
    TypeScript
    JavaScript
    MongoDB
    Express
    Docker
    Git
    """

    results = await run_matching(
        job_description
    )

    print("\n" + "=" * 60)
    print("MCP-BASED CANDIDATE MATCHING")
    print("=" * 60)

    for index, candidate in enumerate(results, 1):

        print(
            f"\n{index}. {candidate.name}"
        )

        print(
            f"Score: {candidate.score}/100"
        )

        print(
            f"Matched skills: "
            f"{', '.join(candidate.matched_skills) or 'None'}"
        )

        print(
            f"Missing skills: "
            f"{', '.join(candidate.missing_skills) or 'None'}"
        )

        print(
            f"Experience match: "
            f"{candidate.experience_match}"
        )


if __name__ == "__main__":
    asyncio.run(main())
