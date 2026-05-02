"""Tests for the YAML settings source and the Settings singleton.

Filesystem and metadata access points are substituted with `create_autospec`
stand-ins:
  * `YamlSettingsSource.get_user_config_path` — redirects the user-config
    location under tmp_path.
  * `YamlSettingsSource.get_template_config_path` — points the source at a
    test-controlled template file.
  * `metadata.version` — pins the injected version string.

The user's real ~/.config/hack/config.yaml is never touched.
"""

import os
from importlib import metadata
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic.fields import FieldInfo
from pytest_mock import MockerFixture
from yaml import safe_dump, safe_load

from rebelist.hack.config import settings as settings_module
from rebelist.hack.config.settings import (
    JiraIssueCustomFieldSettings,
    JiraIssueCustomFieldType,
    JiraSettings,
    Settings,
    YamlSettingsSource,
)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(safe_dump(data, sort_keys=False), encoding='utf-8')


def _full_template_data() -> dict[str, Any]:
    """Build a payload that mirrors the bundled template."""
    return {
        'agent': {'model': 'test:model', 'api_key_name': 'TEST_API_KEY', 'api_key': 'secret'},
        'git': {'branch_categories': ['feature', 'bugfix']},
        'jira': {
            'host': 'https://jira.example.com',
            'token': 'token',
            'fields': {'project': 'XX', 'reporter': 'alice', 'issue_types': ['Bug']},
            'custom_fields': None,
            'templates': None,
        },
    }


@pytest.fixture
def isolated_yaml_paths(mocker: MockerFixture, tmp_path: Path) -> tuple[Path, Path]:
    """Substitute the user/template path resolvers with autospec'd staticmethod stand-ins."""
    user_config = tmp_path / YamlSettingsSource.CONFIG_RELATIVE_PATH
    _user_config_mock = create_autospec(YamlSettingsSource.get_user_config_path)
    _user_config_mock.return_value = user_config
    mocker.patch.object(YamlSettingsSource, 'get_user_config_path', new=staticmethod(_user_config_mock))

    template_config = tmp_path / 'template.yaml'
    _template_config_mock = create_autospec(YamlSettingsSource.get_template_config_path)
    _template_config_mock.return_value = template_config
    mocker.patch.object(YamlSettingsSource, 'get_template_config_path', new=staticmethod(_template_config_mock))

    return user_config, template_config


@pytest.fixture
def pinned_version(mocker: MockerFixture) -> str:
    """Pin metadata.version inside the settings module to a deterministic string."""
    pinned = '9.9.9-test'
    _version_mock = create_autospec(metadata.version)
    _version_mock.return_value = pinned
    mocker.patch.object(settings_module.metadata, 'version', new=_version_mock)
    return pinned


@pytest.mark.unit
class TestYamlSettingsSourceCallable:
    """Verify the load/seed/merge behaviour of the custom YAML source."""

    def test_seeds_user_config_from_template_when_missing(
        self, isolated_yaml_paths: tuple[Path, Path], pinned_version: str
    ) -> None:
        """First-run path: template is copied into the user config location."""
        user_config, template_config = isolated_yaml_paths
        _write_yaml(template_config, _full_template_data())

        result = YamlSettingsSource(Settings)()

        assert user_config.exists(), 'user config should be created on first run'
        assert result['agent']['model'] == 'test:model'
        assert result['general'] == {'name': 'hack', 'version': pinned_version}

    def test_back_fills_new_keys_into_existing_user_config(
        self, isolated_yaml_paths: tuple[Path, Path], pinned_version: str
    ) -> None:
        """If template adds a new key, it's merged into the user file with defaults preserved."""
        user_config, template_config = isolated_yaml_paths
        existing = _full_template_data()
        existing['agent']['api_key'] = 'user-edited'
        _write_yaml(user_config, existing)

        template = _full_template_data()
        template['new_section'] = {'enabled': True}
        _write_yaml(template_config, template)

        YamlSettingsSource(Settings)()

        on_disk = safe_load(user_config.read_text(encoding='utf-8'))
        assert on_disk['agent']['api_key'] == 'user-edited', 'user value must be preserved'
        assert on_disk['new_section'] == {'enabled': True}, 'new template key must be back-filled'

    def test_does_not_rewrite_user_config_when_no_changes(
        self, isolated_yaml_paths: tuple[Path, Path], pinned_version: str
    ) -> None:
        """If the user file already has every template key, no write back occurs."""
        user_config, template_config = isolated_yaml_paths
        data = _full_template_data()
        _write_yaml(user_config, data)
        _write_yaml(template_config, data)
        original_mtime = user_config.stat().st_mtime_ns

        YamlSettingsSource(Settings)()

        assert user_config.stat().st_mtime_ns == original_mtime, 'user file should not be rewritten'

    def test_handles_empty_user_yaml(self, isolated_yaml_paths: tuple[Path, Path], pinned_version: str) -> None:
        """An empty (zero-byte) user YAML still merges cleanly with the template defaults."""
        user_config, template_config = isolated_yaml_paths
        user_config.parent.mkdir(parents=True, exist_ok=True)
        user_config.write_text('', encoding='utf-8')
        _write_yaml(template_config, _full_template_data())

        result = YamlSettingsSource(Settings)()

        assert result['agent']['model'] == 'test:model'

    def test_get_field_value_returns_neutral_tuple(self) -> None:
        """get_field_value is a no-op since values come from __call__."""
        source = YamlSettingsSource(Settings)
        field_info = FieldInfo(annotation=str)

        value, key, complex_flag = source.get_field_value(field_info, 'agent')

        assert value is None
        assert key == 'agent'
        assert complex_flag is False

    def test_prepare_field_value_passes_through(self) -> None:
        """prepare_field_value returns its input unchanged."""
        source = YamlSettingsSource(Settings)
        field_info = FieldInfo(annotation=str)

        assert source.prepare_field_value('agent', field_info, {'x': 1}, True) == {'x': 1}

    def test_default_user_config_path_under_home(self) -> None:
        """The unpatched get_user_config_path resolves under the user's HOME directory."""
        path = YamlSettingsSource.get_user_config_path()

        assert path == Path.home() / YamlSettingsSource.CONFIG_RELATIVE_PATH


@pytest.mark.unit
class TestSettingsSingleton:
    """Verify Settings.instance lazy initialisation and reset."""

    def test_instance_is_cached_across_calls(self, settings: Settings) -> None:
        """Once initialised, Settings.instance returns the same object."""
        first = Settings.instance()
        second = Settings.instance()

        assert first is second is settings

    def test_reset_clears_the_cache(self, settings: Settings) -> None:
        """After reset, the next call constructs a fresh instance."""
        del settings  # the fixture installs the YAML source; we just need it active
        first = Settings.instance()
        Settings.reset()
        second = Settings.instance()

        assert first is not second, 'reset must force a fresh construction'

    def test_model_post_init_exports_api_key_to_environment(self, settings: Settings) -> None:
        """Constructing Settings sets os.environ[api_key_name] to the configured api_key."""
        assert os.environ[settings.agent.api_key_name] == settings.agent.api_key


@pytest.mark.unit
class TestJiraSettingsValidator:
    """Verify the field validator that maps explicit None -> []."""

    def test_none_becomes_empty_list_for_custom_fields(self) -> None:
        """Pydantic must coerce explicit None to [] for custom_fields and templates."""
        jira = JiraSettings.model_validate(
            {
                'host': 'https://jira.example.com',
                'token': 'tok',
                'fields': {'project': 'X', 'reporter': 'alice', 'issue_types': ['Bug']},
                'custom_fields': None,
                'templates': None,
            }
        )

        assert jira.custom_fields == []
        assert jira.templates == []

    def test_custom_field_id_pattern_is_enforced(self) -> None:
        r"""The custom-field name must match `customfield_\d+`."""
        with pytest.raises(ValueError, match='String should match pattern'):
            JiraIssueCustomFieldSettings(
                name='wrong_id',
                alias='owner',
                field_type=JiraIssueCustomFieldType.USER,
                value='alice',
            )
