from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TournamentFormatConfig(BaseModel):
    """Base configuration for tournament format and ranking rules."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_scoring_rules(self):
        allowed_extra_fields = {
            "points_per_win",
            "points_per_draw",
            "points_per_loss",
            "tie_break_rules",
        }

        allowed_tie_break_rules = {
            "points",
            "score_difference",
            "score_for",
            "score_against",
            "wins",
            "draws",
            "losses",
            "team_name",
        }

        extra_fields = self.__pydantic_extra__ or {}

        # Reject unsupported configuration keys.
        unknown_fields = set(extra_fields) - allowed_extra_fields

        if unknown_fields:
            raise ValueError(
                "Unsupported format configuration keys: "
                + ", ".join(sorted(unknown_fields))
            )

        # Validate optional scoring values.
        scoring_keys = (
            "points_per_win",
            "points_per_draw",
            "points_per_loss",
        )

        for rule_name in scoring_keys:
            if rule_name not in extra_fields:
                continue

            rule_value = extra_fields[rule_name]

            if (
                not isinstance(rule_value, int)
                or isinstance(rule_value, bool)
                or rule_value < 0
            ):
                raise ValueError(
                    f"{rule_name} must be a non-negative integer"
                )

        # Validate the optional ranking tie-break order.
        if "tie_break_rules" in extra_fields:
            rules = extra_fields["tie_break_rules"]

            if not isinstance(rules, list):
                raise ValueError("tie_break_rules must be a list")

            invalid_rules = [
                rule
                for rule in rules
                if (
                    not isinstance(rule, str)
                    or rule not in allowed_tie_break_rules
                )
            ]

            if invalid_rules:
                raise ValueError(
                    "Invalid tie_break_rules entry. Allowed rules are: "
                    + ", ".join(sorted(allowed_tie_break_rules))
                )

            if len(rules) != len(set(rules)):
                raise ValueError(
                    "tie_break_rules cannot contain duplicate entries"
                )

        return self


class RoundRobinConfig(TournamentFormatConfig):
    """Configuration required for round-robin tournaments."""

    number_of_teams: int = Field(ge=2)


class SingleEliminationConfig(TournamentFormatConfig):
    """Configuration required for single-elimination tournaments."""

    number_of_teams: int = Field(ge=2)


class DoubleEliminationConfig(TournamentFormatConfig):
    """Configuration required for double-elimination tournaments."""

    number_of_teams: int = Field(ge=2)


class TournamentCreate(BaseModel):
    """Schema for creating a tournament."""

    name: str = Field(min_length=3, max_length=150)
    description: str | None = None
    format: str = Field(min_length=1, max_length=50)

    format_config: (
        RoundRobinConfig
        | SingleEliminationConfig
        | DoubleEliminationConfig
        | None
    ) = None

    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TournamentUpdate(BaseModel):
    """Schema for updating a tournament."""

    name: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = None
    format: str | None = Field(default=None, min_length=1, max_length=50)

    format_config: (
        RoundRobinConfig
        | SingleEliminationConfig
        | DoubleEliminationConfig
        | None
    ) = None

    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def check_dates(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")
        return self


class TournamentResponse(BaseModel):
    """Schema for returning tournament data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    format: str

    format_config: (
        RoundRobinConfig
        | SingleEliminationConfig
        | DoubleEliminationConfig
        | None
    )

    start_date: datetime
    end_date: datetime
    status: str
    organizer_id: int
    created_at: datetime
    updated_at: datetime

class TournamentStandingResponse(BaseModel):
    """Consistent response schema for a team's tournament standing."""

    rank: int = Field(ge=1)
    team_id: int
    team_name: str

    played: int = Field(ge=0)
    wins: int = Field(ge=0)
    draws: int = Field(ge=0)
    losses: int = Field(ge=0)

    score_for: int = Field(ge=0)
    score_against: int = Field(ge=0)
    score_difference: int

    points: int = Field(ge=0)