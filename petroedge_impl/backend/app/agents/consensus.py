from __future__ import annotations

from collections import Counter

from app.agents.schemas import AgentResult, ConsensusResult


class ConsensusEngine:
    def build(self, results: list[AgentResult]) -> ConsensusResult:
        if not results:
            return ConsensusResult(
                overall_confidence=0.0,
                summary="No agent results were produced.",
                missing_evidence=["No agents executed."],
            )

        confidence = sum(result.confidence for result in results) / len(results)
        recommendations = []
        missing_evidence = []
        summaries = []

        for result in results:
            summaries.append(f"{result.agent_name}: {result.summary}")
            missing_evidence.extend(result.limitations)
            for finding in result.findings:
                recommendations.extend(finding.recommendations)

        recommendation_counts = Counter(recommendations)
        deduplicated_recommendations = [
            recommendation
            for recommendation, _ in recommendation_counts.most_common()
        ]

        strong_agents = [
            result.agent_name
            for result in results
            if result.confidence >= 0.70
        ]
        agreements = []
        if len(strong_agents) >= 2:
            agreements.append(
                "Multiple domain agents produced findings with confidence of at least 0.70."
            )

        summary = " ".join(summaries)

        return ConsensusResult(
            overall_confidence=round(confidence, 4),
            summary=summary,
            recommendations=deduplicated_recommendations,
            agreements=agreements,
            disagreements=[],
            missing_evidence=sorted(set(missing_evidence)),
        )