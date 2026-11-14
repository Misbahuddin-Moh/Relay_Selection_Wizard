"""Versioned input contracts shared by HTTP and portable project validation."""
from typing import Annotated, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from .assessment import CT_KEYS

Identity = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]
def new_identity():
    return str(uuid4())

Measurement = Literal["unknown", "present", "absent"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Bay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: Identity = Field(default_factory=new_identity)
    id: Label
    branches: Annotated[list[Label], Field(min_length=1, max_length=30)]
    ct: Measurement


CtCount = Annotated[int, Field(strict=True, ge=0, le=99)]


class CtInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lv_breaker_135: Optional[CtCount] = Field(...)
    lv_breaker_246: Optional[CtCount] = Field(...)
    hv_breaker_135: Optional[CtCount] = Field(...)
    hv_breaker_246: Optional[CtCount] = Field(...)
    transformer_hv_phase: Optional[CtCount] = Field(...)
    transformer_lv_phase: Optional[CtCount] = Field(...)
    transformer_hv_neutral: Optional[CtCount] = Field(...)
    transformer_lv_neutral: Optional[CtCount] = Field(...)


class CtProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Optional[CtCount]
    origin: Literal["assumed", "user", "document", "unknown"]
    revision: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class Study(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: Identity = Field(default_factory=new_identity)
    title: Label
    hv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    mv_kv: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    lv_ct: Measurement
    hv_ct: Measurement
    bays: Annotated[list[Bay], Field(min_length=1, max_length=40)]
    auxiliary: Literal["unknown", "included", "excluded"]
    ct_inventory: Optional[CtInventory] = None
    ct_provenance: dict[str, CtProvenance] = Field(default_factory=dict)
    hv_boundary: Literal["poi", "breaker_transformer", "bushing"] = "poi"
    include_poi_line: bool = False

    @model_validator(mode="after")
    def validate_equipment_ids(self):
        if set(self.ct_provenance) - set(CT_KEYS):
            raise ValueError("Unknown CT provenance field.")
        stable_ids = [bay.uid for bay in self.bays]
        if len(stable_ids) != len(set(stable_ids)) or self.uid in stable_ids:
            raise ValueError("Equipment identities must be unique.")
        bay_ids = [bay.id.casefold() for bay in self.bays]
        if len(set(bay_ids)) != len(bay_ids):
            raise ValueError("Collector breaker IDs must be unique.")
        branch_ids = [branch.casefold() for bay in self.bays for branch in bay.branches]
        if len(set(branch_ids)) != len(branch_ids):
            raise ValueError("Outgoing branch IDs must be unique.")
        return self


class DraftBay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: Identity
    id: Annotated[str, StringConstraints(max_length=100)]
    branches: Annotated[list[Annotated[str, StringConstraints(max_length=100)]], Field(min_length=1, max_length=30)]
    ct: Measurement


class StudyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uid: Identity
    title: Annotated[str, StringConstraints(max_length=100)]
    hv_kv: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    mv_kv: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    lv_ct: Measurement
    hv_ct: Measurement
    bays: Annotated[list[DraftBay], Field(min_length=1, max_length=40)]
    auxiliary: Literal["unknown", "included", "excluded"]
    ct_inventory: Optional[CtInventory] = None
    ct_provenance: dict[str, CtProvenance] = Field(default_factory=dict)
    hv_boundary: Literal["poi", "breaker_transformer", "bushing"] = "poi"
    include_poi_line: bool = False

    @model_validator(mode="after")
    def identities(self):
        ids = [self.uid, *(bay.uid for bay in self.bays)]
        if len(ids) != len(set(ids)) or set(self.ct_provenance) - set(CT_KEYS):
            raise ValueError("Draft identities or provenance fields are invalid.")
        return self
