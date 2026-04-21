import os
import shutil
from importlib import metadata
from pathlib import Path
from typing import Any

from pytest_mock import MockerFixture
from yaml import dump, safe_load

from rebelist.hack.config.settings import Settings, YamlSettingsSource


class TestSettings:
    def test_settings_instance_creation(self, tmp_path: Path, mocker: MockerFixture) -> None:
        """Verify that Settings.instance() loads configuration correctly."""
        config_dir = tmp_path / '.config/hack'
        config_dir.mkdir(parents=True)
        config_file = config_dir / 'config.yaml'

        config_data: dict[str, Any] = {
            'agent': {'model': 'openai:gpt-4', 'api_key_name': 'OPENAI_API_KEY', 'api_key': 'sk-1234'},
            'jira': {
                'host': 'https://jira.example.com',
                'token': 'secret_token',
                'fields': {
                    'project': 'PROJ',
                    'reporter': {'default': 'user1'},
                    'issue_type': {'options': ['Bug', 'Task']},
                },
                'custom_fields': {},
                'templates': [],
            },
        }
        config_file.write_text(dump(config_data))

        template_file = tmp_path / 'template.config.yaml'
        template_file.write_text(dump(config_data))

        mocker.patch.object(Path, 'home', return_value=tmp_path, autospec=True)
        mocker.patch.object(YamlSettingsSource, 'get_template_config_path', return_value=template_file, autospec=True)
        mocker.patch.object(metadata, 'version', return_value='1.2.3', autospec=True)

        Settings.reset()
        settings = Settings.instance()

        assert settings.general.version == '1.2.3'
        assert settings.agent.model == 'openai:gpt-4'
        assert os.environ['OPENAI_API_KEY'] == 'sk-1234'

    def test_settings_build_missing_file_copies_template(self, tmp_path: Path, mocker: MockerFixture) -> None:
        """Verify that Settings builds by copying the template when no user config exists."""
        template_file = tmp_path / 'template.config.yaml'
        template_file.write_text(
            dump(
                {
                    'agent': {'model': 'm', 'api_key_name': 'K', 'api_key': 'V'},
                    'jira': {
                        'host': 'h',
                        'token': 't',
                        'fields': {'project': 'P', 'reporter': {'default': 'r'}, 'issue_type': {'options': []}},
                        'custom_fields': {},
                        'templates': [],
                    },
                }
            )
        )

        mocker.patch.object(Path, 'home', return_value=tmp_path, autospec=True)
        mocker.patch.object(YamlSettingsSource, 'get_template_config_path', return_value=template_file, autospec=True)
        mocker.patch.object(metadata, 'version', return_value='0.0.1', autospec=True)

        # Use side_effect instead of wraps for a cleaner MagicMock behavior
        mock_copy = mocker.patch.object(shutil, 'copy', side_effect=_copy_file, autospec=True)

        Settings.reset()
        settings = Settings.instance()

        assert settings.agent.model == 'm'
        mock_copy.assert_called_once()
        assert (tmp_path / '.config/hack/config.yaml').exists()

    def test_settings_backfills_missing_keys_from_template(self, tmp_path: Path, mocker: MockerFixture) -> None:
        """Missing keys from template should be merged into user config."""
        config_dir = tmp_path / '.config/hack'
        config_dir.mkdir(parents=True)
        config_file = config_dir / 'config.yaml'

        user_config: dict[str, Any] = {
            'agent': {'model': 'user-m', 'api_key_name': 'K', 'api_key': 'V'},
            'jira': {
                'host': 'h',
                'token': 't',
                'fields': {'project': 'P', 'reporter': {'default': 'user1'}, 'issue_type': {'options': []}},
                'custom_fields': {},
                'templates': [],
            },
        }
        config_file.write_text(dump(user_config))

        template_file = tmp_path / 'template.config.yaml'
        template_data: dict[str, Any] = {
            'agent': {'model': 'tmpl', 'api_key_name': 'K', 'api_key': 'V', 'new_key': 'val'},
            'jira': {
                'host': 'h',
                'token': 't',
                'fields': {
                    'project': 'P',
                    'reporter': {'default': 'tmpl', 'new_sub': 'val'},
                    'issue_type': {'options': []},
                },
                'custom_fields': {},
                'templates': [],
            },
        }
        template_file.write_text(dump(template_data))

        mocker.patch.object(Path, 'home', return_value=tmp_path, autospec=True)
        mocker.patch.object(YamlSettingsSource, 'get_template_config_path', return_value=template_file, autospec=True)
        mocker.patch.object(metadata, 'version', return_value='1.0.0', autospec=True)

        Settings.reset()
        settings = Settings.instance()

        # Check in-memory object
        assert settings.agent.model == 'user-m'

        # Check disk persistence
        persisted = safe_load(config_file.read_text())
        assert persisted['agent']['new_key'] == 'val'
        assert persisted['jira']['fields']['reporter']['default'] == 'user1'
        assert persisted['jira']['fields']['reporter']['new_sub'] == 'val'


def _copy_file(src: Any, dst: Any) -> Any:
    """Help to simulate shutil.copy for tests."""
    Path(dst).write_bytes(Path(src).read_bytes())
    return dst
