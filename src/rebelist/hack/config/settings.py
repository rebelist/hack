import os
import shutil
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any, ClassVar, Final, TypeGuard

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from yaml import safe_dump, safe_load

from rebelist.hack.models.jira import CustomFieldType

############################################
#              Models
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


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom Pydantic settings source that loads and merges YAML config."""

    PACKAGE_NAME: Final[str] = 'rebelist-hack'
    CONFIG_RELATIVE_PATH: Final[str] = '.config/hack/config.yaml'
    TEMPLATE_FILE_NAME: Final[str] = 'template.config.yaml'

    @staticmethod
    def get_user_config_path() -> Path:
        """Return the absolute path to the user's YAML config file."""
        return Path.home() / YamlSettingsSource.CONFIG_RELATIVE_PATH

    @staticmethod
    def get_template_config_path() -> Path:
        """Return the absolute path to the bundled template config file."""
        return Path(__file__).parent / YamlSettingsSource.TEMPLATE_FILE_NAME

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Get the value, the key for model creation, and a flag indicating if the value is complex."""
        return None, field_name, False

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        """Prepare the value for model creation."""
        return value

    def __call__(self) -> dict[str, Any]:
        """Load the user config, seeding it from the template and back-filling new defaults.

        - If the user has no config file yet, the bundled template is copied over.
        - If the user already has a config file, any keys added to the template since it
          was first created are merged in with their default values while preserving
          every custom value the user has set. The updated file is written back so the
          user can inspect and further customize the new keys.
        """
        user_config = self.get_user_config_path()
        template_config = self.get_template_config_path()

        if not user_config.exists():
            user_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template_config, user_config)

        if not user_config.exists():
            raise FileNotFoundError(f'Config file not found: {user_config}')

        user_data: dict[str, Any] = safe_load(user_config.read_text(encoding='utf-8')) or {}
        template_data: dict[str, Any] = safe_load(template_config.read_text(encoding='utf-8')) or {}

        merged, has_changed = self.__merge_defaults(user_data, template_data)
        if has_changed:
            user_config.write_text(safe_dump(merged, sort_keys=False), encoding='utf-8')

        # Inject dynamic metadata
        version = metadata.version(YamlSettingsSource.PACKAGE_NAME)
        name = YamlSettingsSource.PACKAGE_NAME.split('-')[1].lower()
        merged['general'] = {'name': name, 'version': version}

        return merged

    @staticmethod
    def __is_dict_str_any(val: Any) -> TypeGuard[dict[str, Any]]:
        """Type guard to narrow `Any` to `dict[str, Any]`."""
        return isinstance(val, dict)

    @classmethod
    def __merge_defaults(cls, user: dict[str, Any], template: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Recursively fill missing keys in `user` with values from `template`.

        Existing user values are preserved. Nested dictionaries are merged key by key so
        that newly introduced settings get sensible defaults. Lists and scalars are
        treated as leaf values and are never overridden.
        Returns the merged mapping together with a flag indicating whether any key was added.
        """
        merged: dict[str, Any] = dict(user)
        has_changed = False
        for key, template_value in template.items():
            if key not in merged:
                merged[key] = template_value
                has_changed = True
                continue
            user_value = merged[key]
            if cls.__is_dict_str_any(template_value) and cls.__is_dict_str_any(user_value):
                nested, nested_changed = cls.__merge_defaults(user_value, template_value)
                merged[key] = nested
                has_changed = has_changed or nested_changed
        return merged, has_changed


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    general: GeneralSettings
    agent: AgentSettings
    jira: JiraSettings

    __instance: ClassVar[Settings | None] = None

    def __init__(self, **values: Any) -> None:
        """Initialize settings, allowing BaseSettings sources to provide values."""
        super().__init__(**values)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Override the default settings sources to include our custom YAML source."""
        return (
            init_settings,
            YamlSettingsSource(settings_cls),
            env_settings,
        )

    def model_post_init(self, __context: Any) -> None:
        """Set up environment variables after initialization."""
        os.environ[self.agent.api_key_name] = self.agent.api_key

    @classmethod
    def instance(cls) -> Settings:
        """Return the lazily initialized singleton instance."""
        if cls.__instance is not None:
            return cls.__instance

        instance = cls()
        cls.__instance = instance
        return instance

    @classmethod
    def reset(cls) -> None:
        """Clear the cached singleton. Intended for tests only."""
        cls.__instance = None
