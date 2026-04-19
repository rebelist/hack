from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml import safe_load

from rebelist.hack.models.jira import CustomFieldType

PACKAGE_NAME: Final[str] = 'rebelist-hack'
PROJECT_ROOT: Final[str] = str(Path(__file__).resolve().parents[4])

############################################
#              App Settings
############################################


class GeneralSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    name: str
    version: str


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True, env_prefix='AGENT_')

    model: str = ''


class JiraSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True, env_prefix='JIRA_')

    host: str = ''
    token: str = ''
    templates: str = ''


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    general: GeneralSettings
    agent: AgentSettings
    jira: JiraSettings

    @classmethod
    def __build(cls) -> AppSettings:
        """Build a fresh Settings instance.

        Loads environment variables (if .env exists), reads application metadata, and constructs all configuration.
        """
        env_path = Path(f'{PROJECT_ROOT}/.env')

        if env_path.is_file():
            load_dotenv(env_path)

        version = metadata.version(PACKAGE_NAME)
        name = PACKAGE_NAME.split('-')[1].lower()

        return cls(
            general=GeneralSettings(name=name, version=version),
            agent=AgentSettings(),
            jira=JiraSettings(),
        )

    @classmethod
    @lru_cache(maxsize=1)
    def instance(cls) -> AppSettings:
        """Return a cached, lazily-initialized singleton Settings instance."""
        return cls.__build()


############################################
#              User Settings
############################################
class JiraTicketReporterSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    default: str


class JiraIssueTypeSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    description: str
    options: list[str]


class JiraTicketFieldsSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    project: str
    summary: str | None = None
    reporter: JiraTicketReporterSettings
    issue_type: JiraIssueTypeSettings


class JiraTicketCustomFieldSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    name: str
    field_type: CustomFieldType
    default: str | list[str] | None = None


class JiraTicketTemplateSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, str_strip_whitespace=True)

    issue_type: str
    template: str


class JiraTicketSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    fields: JiraTicketFieldsSettings
    custom_fields: dict[str, JiraTicketCustomFieldSettings]
    description_templates: list[JiraTicketTemplateSettings]


class UserSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    jira: JiraTicketSettings

    @classmethod
    def __build(cls) -> UserSettings:
        """Build a fresh user settings instance."""
        config_file = Path(f'{PROJECT_ROOT}/.hack/config.yaml')
        if not config_file.exists():
            raise FileNotFoundError(f'Config file not found: {config_file}')

        raw: dict[str, Any] = safe_load(config_file.read_text(encoding='utf-8'))

        return cls(**raw)

    @classmethod
    @lru_cache(maxsize=1)
    def instance(cls) -> UserSettings:
        """Return a cached, lazily-initialized singleton UserSettings instance."""
        return cls.__build()
