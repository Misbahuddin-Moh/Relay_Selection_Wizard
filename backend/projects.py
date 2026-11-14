"""Portable input files. No analysis, provider permissions, source text or approvals."""
from typing import Annotated, Literal
import re
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator, field_validator
from .models import Identity, Study, StudyDraft, new_identity
from .options import preview_options
from .engine import analyze

MAX_PROJECT_BYTES = 2 * 1024 * 1024
Variant = Literal['LOCK', 'DIRECT', 'GOOSE_BFI', 'LOCAL_H', 'EXTERNAL_F']
Text = Annotated[str, StringConstraints(max_length=2000)]
InputCount = Annotated[str, StringConstraints(pattern=r'^(|[0-9]{1,3})$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RelayInputs(StrictModel):
    neutral: InputCount = ''
    vt: InputCount = ''


class Spare(StrictModel):
    di: Annotated[int, Field(strict=True, ge=0, le=99)]
    do: Annotated[int, Field(strict=True, ge=0, le=99)]
    basis: Literal['used', 'installed']


class Signal(StrictModel):
    id: Annotated[int, Field(strict=True, ge=0)]
    name: Text
    source: Text
    destination: Text
    method: Literal['hardwired', 'GOOSE', 'SCADA message', 'internal', 'teleprotection', 'hardwired or communicated']
    di: Annotated[int, Field(strict=True, ge=0, le=99)]
    do: Annotated[int, Field(strict=True, ge=0, le=99)]
    coil: bool
    included: bool
    reference: Text
    condition: Text


class DigitalSettings(StrictModel):
    variant: Variant
    spare: Spare
    edits: dict[Variant, Annotated[list[Signal], Field(max_length=1000)]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_signals(self):
        for rows in self.edits.values():
            if len({row.id for row in rows}) != len(rows):
                raise ValueError('Duplicate signal identity in digital edits.')
        return self


class RemoteChecks(StrictModel):
    remoteCt: Literal['unknown', 'present', 'absent'] = 'unknown'
    remoteModel: Annotated[str, StringConstraints(max_length=200)] = ''
    compatibleModel: Annotated[str, StringConstraints(max_length=200)] = ''
    channel: bool = False
    dtt: Literal['unknown', 'not_required', 'pending', 'verified'] = 'unknown'


class Decisions(StrictModel):
    selection: Annotated[str, StringConstraints(max_length=100)] = ''
    requirements: dict[str, RelayInputs] = Field(default_factory=dict)
    retired_requirements: dict[str, RelayInputs] = Field(default_factory=dict)
    digital_settings: dict[str, DigitalSettings] = Field(default_factory=dict)
    digital_bay_order: list[Identity] = Field(default_factory=list, max_length=40)
    digital_include_line: bool = False
    ordering_notes: dict[str, dict[Literal['dc', 'ct', 'comms', 'chassis', 'analog', 'build', 'digital', 'cpu', 'supply'], Annotated[str, StringConstraints(max_length=1000)]]] = Field(default_factory=dict)
    retired_ordering_notes: dict[str, dict[Literal['dc', 'ct', 'comms', 'chassis', 'analog', 'build', 'digital', 'cpu', 'supply'], Annotated[str, StringConstraints(max_length=1000)]]] = Field(default_factory=dict)
    line_checks: RemoteChecks = Field(default_factory=RemoteChecks)
    notices: Annotated[list[Annotated[str, StringConstraints(max_length=300)]], Field(max_length=30)] = Field(default_factory=list)

    @model_validator(mode='after')
    def bounded_maps(self):
        for mapping in (self.requirements, self.retired_requirements, self.digital_settings, self.ordering_notes, self.retired_ordering_notes):
            if len(mapping) > 500 or any(len(key) > 200 for key in mapping):
                raise ValueError('Too many decisions or invalid decision key.')
        return self


class ProjectFile(StrictModel):
    format: Literal['relay-wizard-project']
    schema_version: Literal[1]
    project_id: Identity
    study: Study
    draft: StudyDraft | None = None
    decisions: Decisions = Field(default_factory=Decisions)

    @model_validator(mode='before')
    @classmethod
    def persistent_identity_required(cls, data):
        if isinstance(data, dict) and isinstance(data.get('study'), dict):
            study = data['study']
            bays = study.get('bays')
            if 'uid' not in study or not isinstance(bays, list) or any(not isinstance(bay, dict) or 'uid' not in bay for bay in bays):
                raise ValueError('Versioned project files require persistent study and equipment identities.')
        return data

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_version_type(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('Unsupported project schema version.')
        return value

    @model_validator(mode='after')
    def references(self):
        if self.draft is not None and self.draft.uid != self.study.uid:
            raise ValueError('Draft must retain the active study identity.')
        options = {option['option_id']: option for boundary in ('poi', 'breaker_transformer', 'bushing')
                   for option in preview_options({**self.study.model_dump(), 'hv_boundary': boundary})['options']}
        role_keys = {f"{option_id}/{role['role_id']}" for option_id, option in options.items()
                     for role in option['device_requirements']}
        if self.decisions.selection and self.decisions.selection not in options:
            raise ValueError('Unknown selected protection option.')
        if set(self.decisions.requirements) - role_keys:
            raise ValueError('A relay decision references absent equipment. Retire it explicitly before saving.')
        if set(self.decisions.digital_settings) - options.keys():
            raise ValueError('Digital settings reference an unknown protection option.')
        role_pattern = r'(dedicated|shared|combined):(poi|breaker_transformer|bushing)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        for key in self.decisions.retired_requirements:
            if not re.fullmatch(role_pattern, key):
                raise ValueError('Invalid retired role identity.')
        for key in self.decisions.retired_ordering_notes:
            if '/' not in key or not re.fullmatch(role_pattern, key.rsplit('/', 1)[0]) or key.rsplit('/', 1)[-1] not in ('GE T60', 'SEL-487E-3'):
                raise ValueError('Invalid retired ordering role or model.')
        for key in self.decisions.ordering_notes:
            if key.rsplit('/', 1)[0] not in role_keys or key.rsplit('/', 1)[-1] not in ('GE T60', 'SEL-487E-3'):
                raise ValueError('Ordering notes reference an unknown role or model.')
        return self


def project_role_keys(study):
    return [f"{option['option_id']}/{role['role_id']}"
            for boundary in ('poi', 'breaker_transformer', 'bushing')
            for option in preview_options({**study, 'hv_boundary': boundary})['options']
            for role in option['device_requirements']]


def validate_project(data):
    warnings = []
    if isinstance(data, dict) and 'format' not in data and 'schema_version' not in data:
        # Legacy raw station JSON is the only supported migration. Assign once,
        # return the IDs, and persist them in the new envelope.
        study = Study.model_validate(data)
        project = ProjectFile(format='relay-wizard-project', schema_version=1, project_id=new_identity(), study=study)
        warnings.append('Legacy station imported with new persistent identities; previous approvals are unavailable.')
    else:
        project = ProjectFile.model_validate(data)
    result = project.model_dump()
    order = [bay['uid'] for bay in result['study']['bays']]
    decisions = result['decisions']
    if decisions['digital_bay_order'] != order or decisions['digital_include_line'] != result['study']['include_poi_line']:
        if any(settings['edits'] for settings in decisions['digital_settings'].values()):
            warnings.append('Positional digital edits were cleared because breaker order or line scope changed.')
        for settings in decisions['digital_settings'].values():
            settings['edits'] = {}
        decisions['digital_bay_order'] = order
        decisions['digital_include_line'] = result['study']['include_poi_line']
    role_keys = project_role_keys(result['study'])
    return {'project': result, 'analysis': analyze(result['study']),
            'warnings': warnings, 'role_keys': role_keys}
