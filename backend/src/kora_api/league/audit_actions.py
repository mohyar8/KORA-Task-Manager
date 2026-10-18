"""Audited league actions: only the round title, changed Team ids and their points are stored."""

from kora_api.audit.service import action

LEAGUE = "league"
LEAGUE_UPDATED = action("league.updated", LEAGUE, "round_title", "changed_team_ids", "points")
