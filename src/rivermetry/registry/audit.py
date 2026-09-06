from rivermetry.registry.scoring import candidate_score


def audit_candidates(items: list[dict]) -> list[dict]:
    report = []
    for item in items:
        score = candidate_score(item)
        report.append({**item, "score": score, "promotion_ready": score >= 70 and item.get("hard_gate") is True})
    return sorted(report, key=lambda item: (-item["score"], item["location_id"]))
