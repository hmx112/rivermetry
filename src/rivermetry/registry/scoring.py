def candidate_score(item: dict) -> int:
    score = 0
    score += min(35, int(item.get("data_quality_score", 0)))
    score += min(25, int(item.get("demand_score", 0)))
    score += 15 if item.get("nwps_match") else 0
    score += min(10, int(item.get("history_score", 0)))
    score += min(10, int(item.get("geographic_score", 0)))
    score += min(5, int(item.get("nearby_score", 0)))
    return min(100, score)
