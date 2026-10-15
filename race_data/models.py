"""Canonical units: seconds; identifiers are text; missing measurements are null."""
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Run(Model):
    run_id: str
    skill_id: str
    mode: Literal['live', 'test']
    team: str
    started_at: AwareDatetime
    station_id: str
    race_id: str
    round_id: str
    session_id: str
    race_name: str = ''
    session_name: str = ''
    session_start: str | None = None
    session_status: str | None = None


class Result(Model):
    result_id: str
    car_number: str
    team_name: str
    driver_name: str | None = None
    class_name: str | None = None
    position: int | None = None
    class_position: int | None = None
    completed_laps: int | None = Field(default=None, ge=0)
    best_lap_seconds: float | None = Field(default=None, ge=0)
    total_seconds: float | None = Field(default=None, ge=0)
    best_lap_number: int | None = None
    gap_seconds: float | None = Field(default=None, ge=0)
    gap_laps: int | None = Field(default=None, ge=0)
    leader_gap_seconds: float | None = Field(default=None, ge=0)
    leader_gap_laps: int | None = Field(default=None, ge=0)
    pit_stops: int | None = Field(default=None, ge=0)
    source_status: str | None = None
    extra_json: str = '{}'

    @model_validator(mode='after')
    def consistent_gaps(self):
        for seconds,laps in ((self.gap_seconds,self.gap_laps),(self.leader_gap_seconds,self.leader_gap_laps)):
            if seconds is not None and laps is not None:
                raise ValueError('A gap must use either seconds or laps')
        return self


class ControlMessage(Model):
    message_id: str
    sequence: int | None = None
    published_at_source: str | None = None
    event_time_source: str | None = None
    body: str


class Lap(Model):
    result_id: str
    car_number: str
    team_name: str
    lap_id: str
    lap_number: int
    crossing_at: AwareDatetime
    lap_seconds: float = Field(gt=0)
    received_at: AwareDatetime


class Collection(Model):
    run_id: str
    lane: Literal['results', 'control_message', 'weather', 'laps']
    status: Literal['waiting', 'ok', 'error', 'partial']
    attempted_at: AwareDatetime
    collected_at: AwareDatetime | None = None
    error: str = ''
    metadata_json: str = '{}'

    @model_validator(mode='after')
    def collection_time(self):
        if (self.status in ('ok','partial')) != (self.collected_at is not None):
            raise ValueError('Only successful/partial batches have a collected_at timestamp')
        return self


class LapAnalysis(Model):
    result_id: str
    analysis_at: AwareDatetime
    received_at: AwareDatetime
    car_number: str
    team_name: str
    status: Literal['ok', 'error', 'no_laps_before_cutoff']
    laps_at_cutoff: int | None = None
    last_crossing_at: AwareDatetime | None = None
    last_lap_seconds: float | None = None
    crossing_age_seconds: float | None = None
    pace_median_seconds: float | None = None
    pace_mad_seconds: float | None = None
    pace_samples: int | None = None
    excluded_recent_laps: int | None = None
    previous10_median_seconds: float | None = None
    pace_change_seconds: float | None = None
    assumed_pit_loss_seconds: float | None = None
    pit_loss_equivalent_laps: float | None = None
    phase_estimate_usable: bool | None = None
    error: str = ''


class WeatherFrame(Model):
    run_id: str
    collected_at: AwareDatetime
    source_time: AwareDatetime
    image_path: str
    nowcast_available: bool


class Envelope(Model):
    schema_version: Literal[2] = 2
    dataset: Literal['results', 'control_messages', 'laps', 'pace', 'weather']
    snapshot_id: str
    run: Run
    collection: Collection
