"""Input-only digital I/O contracts; no client-computed readiness or totals."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from .models import Study
Variant = Literal['LOCK', 'DIRECT', 'GOOSE_BFI', 'LOCAL_H', 'EXTERNAL_F']
Text = Annotated[str, StringConstraints(max_length=2000)]
OutputClass = Literal['fast', 'form_c']
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Spare(StrictModel):
    di: Annotated[int, Field(strict=True, ge=0, le=99)]
    do: Annotated[int, Field(strict=True, ge=0, le=99)]
    basis: Literal['used', 'installed']


class Signal(StrictModel):
    id: Annotated[int, Field(strict=True, ge=0, le=9999999999)]
    name: Text
    source: Text
    destination: Text
    method: Literal['hardwired', 'GOOSE', 'SCADA message', 'internal', 'teleprotection', 'hardwired or communicated']
    di: Annotated[int, Field(strict=True, ge=0, le=99)]
    do: Annotated[int, Field(strict=True, ge=0, le=99)]
    coil: Annotated[bool, Field(strict=True)]
    included: Annotated[bool, Field(strict=True)]
    reference: Text
    condition: Text


class DigitalSettings(StrictModel):
    variant: Variant
    spare: Spare
    edits: dict[Variant, Annotated[list[Signal], Field(max_length=1000)]] = Field(default_factory=dict)

    output_classes: dict[Variant, dict[Annotated[str, StringConstraints(pattern=r'^[0-9]{1,10}$')], Annotated[list[OutputClass], Field(max_length=2)]]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_signals(self):
        for mapping in self.output_classes.values():
            if len(mapping) > 1000 or any(len(set(classes)) != len(classes) for classes in mapping.values()):
                raise ValueError('Invalid output class assignments.')
        for rows in self.edits.values():
            if len({row.id for row in rows}) != len(rows):
                raise ValueError('Duplicate signal identity in digital edits.')
        return self



class EngineeringRequest(StrictModel):
    study: Study
    scheme: Literal['dedicated', 'shared', 'combined']
    settings: DigitalSettings

    @model_validator(mode='before')
    @classmethod
    def persistent_identities_required(cls, data):
        if isinstance(data, dict) and isinstance(data.get('study'), dict):
            study = data['study']
            bays = study.get('bays')
            if 'uid' not in study or not isinstance(bays, list) or any(not isinstance(bay, dict) or 'uid' not in bay for bay in bays):
                raise ValueError('Engineering requests require stable study/equipment IDs; migrate a legacy project first.')
        return data
