from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.modules.score.schemas.score import ScoreValue

CorrectionReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class MatchResultCorrectionRequest(BaseModel):
    """Organiser's correction of a finalized result.

    The outcome, winner and loser are never accepted from the client; they
    are recalculated from the corrected scores.
    """

    model_config = ConfigDict(extra="forbid")

    team_a_score: ScoreValue
    team_b_score: ScoreValue
    reason: CorrectionReason
