import os
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import pytest
from yaml import dump

from rebelist.hack.config.settings import Settings


class TestSettings:
    def test_settings_instance_creation(self, tmp_path: Path) -> None:
        """Verify that Settings.instance() loads configuration correctly (using mock file)."""
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

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(Path, 'home', lambda: tmp_path)

            # metadata.version needs to be mocked too
            def mock_version(_path: Any) -> str:
                return '1.2.3'

            mp.setattr('rebelist.hack.config.settings.metadata.version', mock_version)

            # Clear lru_cache for testing
            Settings.instance.cache_clear()

            settings = Settings.instance()

            assert settings.general.version == '1.2.3'
            assert settings.agent.model == 'openai:gpt-4'
            assert os.environ['OPENAI_API_KEY'] == 'sk-1234'

    def test_settings_build_missing_file_copy_template(self, tmp_path: Path) -> None:
        """Verify that Settings builds by copying template if config doesn't exist."""
        # This test checks the logic where it copies template.config.yaml
        _ = tmp_path / '.config/hack'
        # Not creating the file here

        # We need a dummy template file in the right place relative to settings.py
        # But we can't easily place it there in the real src.
        # So we mock the copy operation or the template path.

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(Path, 'home', lambda: tmp_path)

            # Mock shutil.copy to avoid needing the real template file
            mock_copy = create_autospec(lambda src, dst: None)
            mp.setattr('rebelist.hack.config.settings.shutil.copy', mock_copy)

            # Mock safe_load to return something valid after "copy"
            # Since copy was mocked, the file won't actually exist unless we create it
            # but __build will fail at config_file.read_text()

            # Let's create the file after the "copy" would have happened
            def side_effect(src: str | Path, dst: str | Path) -> None:
                Path(dst).write_text(
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

            mock_copy.side_effect = side_effect

            def mock_version(_path: Any) -> str:
                return '0.0.1'

            mp.setattr('rebelist.hack.config.settings.metadata.version', mock_version)

            Settings.instance.cache_clear()
            settings = Settings.instance()

            assert settings.agent.model == 'm'
            mock_copy.assert_called_once()
