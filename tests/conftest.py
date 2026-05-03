"""Shared fixtures for the rebelist.hack test suite.

Every collaborator that the production code reaches for (`Path.home`,
`metadata.version`, the bundled YAML template path, etc.) is substituted
via a `create_autospec`-built mock — single, consistent mock-construction
mechanism across the entire suite. No `MonkeyPatch`, no raw `MagicMock`.
"""

from importlib import metadata
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from pytest_mock import MockerFixture
from yaml import safe_dump

from rebelist.hack.config import settings as settings_module
from rebelist.hack.config.settings import (
    AgentSettings,
    GeneralSettings,
    GitSettings,
    JiraIssueCustomFieldSettings,
    JiraIssueCustomFieldType,
    JiraIssueDescriptionTemplateSettings,
    JiraIssueFieldsSettings,
    JiraSettings,
    Settings,
    YamlSettingsSource,
)


@pytest.fixture
def general_settings() -> GeneralSettings:
    """Provide a deterministic GeneralSettings fixture."""
    return GeneralSettings(name='hack', version='0.0.0-test')


@pytest.fixture
def agent_settings() -> AgentSettings:
    """Provide a deterministic AgentSettings fixture."""
    return AgentSettings(
        model='test:dummy-model',
        api_key_name='TEST_API_KEY',
        api_key='secret',  # type: ignore[arg-type]
    )


@pytest.fixture
def jira_fields_settings() -> JiraIssueFieldsSettings:
    """Provide a deterministic JiraIssueFieldsSettings fixture."""
    return JiraIssueFieldsSettings(project='XX', reporter='alice', issue_types=['Bug', 'User Story'])


@pytest.fixture
def jira_template_settings() -> list[JiraIssueDescriptionTemplateSettings]:
    """Provide a deterministic list of issue templates."""
    return [
        JiraIssueDescriptionTemplateSettings(issue_type='Bug', template='h2. Steps\n# do thing'),
        JiraIssueDescriptionTemplateSettings(issue_type='User Story', template='h2. Story\n*As a* user'),
    ]


@pytest.fixture
def jira_custom_fields_settings() -> list[JiraIssueCustomFieldSettings]:
    """Provide one custom field of every supported type."""
    return [
        JiraIssueCustomFieldSettings(
            name='customfield_10001', alias='owner', field_type=JiraIssueCustomFieldType.USER, value='alice'
        ),
        JiraIssueCustomFieldSettings(
            name='customfield_10002',
            alias='category',
            field_type=JiraIssueCustomFieldType.SELECT,
            value='Operational Tasks',
        ),
        JiraIssueCustomFieldSettings(
            name='customfield_10003',
            alias='teams',
            field_type=JiraIssueCustomFieldType.MULTI_SELECT,
            value=['Team A', 'Team B'],
        ),
        JiraIssueCustomFieldSettings(
            name='customfield_10004',
            alias='points',
            field_type=JiraIssueCustomFieldType.TEXT,
            value='5',
        ),
    ]


@pytest.fixture
def jira_settings(
    jira_fields_settings: JiraIssueFieldsSettings,
    jira_custom_fields_settings: list[JiraIssueCustomFieldSettings],
    jira_template_settings: list[JiraIssueDescriptionTemplateSettings],
) -> JiraSettings:
    """Provide a deterministic JiraSettings fixture."""
    return JiraSettings(
        host='https://jira.example.com',
        token='token-value',  # type: ignore[arg-type]
        fields=jira_fields_settings,
        custom_fields=jira_custom_fields_settings,
        templates=jira_template_settings,
    )


@pytest.fixture
def git_settings() -> GitSettings:
    """Provide a deterministic GitSettings fixture."""
    return GitSettings(
        branch_categories=['feature', 'bugfix', 'hotfix', 'refactor', 'docs', 'chore'],
    )


@pytest.fixture
def settings(
    mocker: MockerFixture,
    tmp_path: Path,
    general_settings: GeneralSettings,
    agent_settings: AgentSettings,
    jira_settings: JiraSettings,
    git_settings: GitSettings,
) -> Settings:
    """Build a fully isolated Settings instance via the production code path.

    Two free-standing callables the production source reads from are substituted
    with `create_autospec`-built stand-ins:
      * `YamlSettingsSource.get_user_config_path` — points the source at a
        tmp_path-backed file so no real user config is touched.
      * `metadata.version` — pinned to general_settings.version for determinism.
    """
    config_path = tmp_path / YamlSettingsSource.CONFIG_RELATIVE_PATH

    _path_mock = create_autospec(YamlSettingsSource.get_user_config_path)
    _path_mock.return_value = config_path
    mocker.patch.object(YamlSettingsSource, 'get_user_config_path', new=staticmethod(_path_mock))

    _version_mock = create_autospec(metadata.version)
    _version_mock.return_value = general_settings.version
    mocker.patch.object(settings_module.metadata, 'version', new=_version_mock)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    agent_payload = agent_settings.model_dump(mode='json')
    agent_payload['api_key'] = agent_settings.api_key.get_secret_value()
    jira_payload = jira_settings.model_dump(mode='json')
    jira_payload['token'] = jira_settings.token.get_secret_value()
    config_path.write_text(
        safe_dump(
            {
                'agent': agent_payload,
                'jira': jira_payload,
                'git': git_settings.model_dump(mode='json'),
            },
            sort_keys=False,
        ),
        encoding='utf-8',
    )

    return Settings()
