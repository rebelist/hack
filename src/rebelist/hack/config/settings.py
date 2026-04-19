import os
import shutil
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any, Final

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml import safe_load

from rebelist.hack.models.jira import CustomFieldType

PACKAGE_NAME: Final[str] = 'rebelist-hack'

############################################
#              Components
############################################

NonEmptyString = Annotated[str, Field(min_length=1)]


class GeneralSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    name: str
    version: str


class AgentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    model: NonEmptyString
    api_key_name: NonEmptyString
    api_key: NonEmptyString


class JiraTicketReporterSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    default: NonEmptyString


class JiraIssueTypeSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    options: list[str]


class JiraTicketFieldsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    project: NonEmptyString
    reporter: JiraTicketReporterSettings
    issue_type: JiraIssueTypeSettings


class JiraTicketCustomFieldSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    name: NonEmptyString
    field_type: CustomFieldType
    default: str | list[str] | None = None


class JiraTicketTemplateSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    issue_type: str
    template: str


class JiraSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    host: NonEmptyString
    token: NonEmptyString
    fields: JiraTicketFieldsSettings
    custom_fields: dict[str, JiraTicketCustomFieldSettings]
    templates: list[JiraTicketTemplateSettings]


############################################
#              Root Settings
############################################


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    general: GeneralSettings
    agent: AgentSettings
    jira: JiraSettings

    @classmethod
    def __build(cls) -> Settings:
        """Build a fresh Settings instance from the local YAML config."""
        config_file = Path.home() / '.config/hack/config.yaml'

        if not config_file.exists():
            config_file.parent.mkdir(parents=True, exist_ok=True)
            template_file = Path(__file__).parent / 'template.config.yaml'
            shutil.copy(template_file, config_file)

        if not config_file.exists():
            raise FileNotFoundError(f'Config file not found: {config_file}')

        raw: dict[str, Any] = safe_load(config_file.read_text(encoding='utf-8'))

        # Inject dynamic metadata not stored in YAML
        version = metadata.version(PACKAGE_NAME)
        name = PACKAGE_NAME.split('-')[1].lower()
        raw['general'] = {'name': name, 'version': version}

        return cls(**raw)

    @classmethod
    @lru_cache(maxsize=1)
    def instance(cls) -> Settings:
        """Return a cached, lazily-initialized singleton Settings instance."""
        settings = cls.__build()
        os.environ[settings.agent.api_key_name] = settings.agent.api_key

        return settings
