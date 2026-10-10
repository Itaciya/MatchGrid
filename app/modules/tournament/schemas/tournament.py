from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TournamentFormatConfig(BaseModel):
    """Base configuration supporting optional tournament scoring rules."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_scoring_rules(self):
        allowed_scoring_keys = {
            "points_per_win",
            "points_per_draw",
            "points_per_loss",
        }

        extra_fields = self.__pydantic_extra__ or {}

        unknown_fields = set(extra_fields) - allowed_scoring_keys
        if unknown_fields:
            raise ValueError(
                "Unsupported format configuration keys: "
                + ", ".join(sorted(unknown_fields))
            )

        for rule_name, rule_value in extra_fields.items():
            if (
                not isinstance(rule_value, int)
                or isinstance(rule_value, bool)
                or rule_value < 0
            ):
                raise ValueError(
                    f"{rule_name} must be a non-negative integer"
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