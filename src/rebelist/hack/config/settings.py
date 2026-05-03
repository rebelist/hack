import os
import shutil
from enum import StrEnum, auto
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any, Final, TypeGuard

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr, ValidationError, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from yaml import safe_dump, safe_load

############################################
#              Errors
############################################


class SettingsError(Exception):
    """Raised when the user's YAML configuration cannot be loaded or validated."""

    @classmethod
    def from_validation_error(cls, validation: ValidationError) -> SettingsError:
        """Build a human-readable message from a Pydantic ValidationError."""
        parts: list[str] = []
        for error in validation.errors():
            loc = '.'.join(str(segment) for segment in error['loc'])
            msg = str(error['msg']).removeprefix('Value error, ')
            parts.append(f'{loc}: {msg}' if loc else msg)
        return cls('; '.join(parts))


############################################
#              Models
############################################

NonEmptyString = Annotated[str, Field(min_length=1)]
TitleString = Annotated[str, BeforeValidator(lambda v: v.title() if isinstance(v, str) else v)]


class JiraIssueCustomFieldType(StrEnum):
    """Custom Jira custom field type."""

    SELECT = auto()
    MULTI_SELECT = auto()
    USER = auto()
    TEXT = auto()


class GeneralSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    name: str
    version: str


class AgentSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    model: NonEmptyString
    api_key_name: NonEmptyString
    api_key: SecretStr


class JiraIssueFieldsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    project: NonEmptyString
    reporter: NonEmptyString
    issue_types: list[TitleString]


class JiraIssueCustomFieldSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    name: Annotated[
        str,
        Field(pattern=r'^customfield_\d+$', description="Internal Jira custom field ID (e.g., 'customfield_13207')."),
    ]
    alias: Annotated[NonEmptyString, Field(description='Human readable name for the custom field.')]
    field_type: JiraIssueCustomFieldType
    value: str | list[str] | None = None


class JiraIssueDescriptionTemplateSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    issue_type: str
    template: str


class JiraSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    host: NonEmptyString
    token: SecretStr
    fields: JiraIssueFieldsSettings
    custom_fields: list[JiraIssueCustomFieldSettings] = []
    templates: list[JiraIssueDescriptionTemplateSettings] = []

    @field_validator('token', mode='before')
    @classmethod
    def _reject_placeholder_token(cls, v: Any) -> Any:
        """Reject the config template placeholder so users get a clear error instead of an auth failure."""
        if isinstance(v, str) and v.strip().lower() in ('none', ''):
            raise ValueError('Jira token is not configured. Set a valid API token in ~/.config/hack/config.yaml.')
        return v

    @field_validator('custom_fields', 'templates', mode='before')
    @classmethod
    def _replace_none_with_empty_list(cls, v: Any) -> Any:
        """Convert explicit None values to an empty list to satisfy downstream type constraints."""
        return v if v is not None else []


class GitSettings(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    branch_categories: list[NonEmptyString]


############################################
#              Root Settings
############################################


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom Pydantic settings source that loads and merges YAML config."""

    PACKAGE_NAME: Final[str] = 'rebelist-hack'
    CONFIG_RELATIVE_PATH: Final[str] = '.config/hack/config.yaml'
    TEMPLATE_FILE_NAME: Final[str] = 'config.template.yaml'

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
    git: GitSettings

    def __init__(self, **values: Any) -> None:
        """Construct via Pydantic settings sources (env, YAML). All fields are populated by sources."""
        super().__init__(**values)

    def model_post_init(self, __context: Any) -> None:
        """Set up environment variables after initialization."""
        os.environ[self.agent.api_key_name] = self.agent.api_key.get_secret_value()

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

    @staticmethod
    def get_metadata() -> tuple[str, str]:
        """Return (app_name, version) without loading the full Settings graph."""
        name = YamlSettingsSource.PACKAGE_NAME.split('-')[1]
        version = metadata.version(YamlSettingsSource.PACKAGE_NAME)
        return name, version
