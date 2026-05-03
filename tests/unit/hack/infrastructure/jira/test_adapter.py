"""Tests for JiraMapper field-type dispatch and JiraGateway round-trips.

Jira's `Issue` resource is populated dynamically at runtime (the fields layer
is built from the live REST response), so `create_autospec(Issue, ...)` cannot
materialise the `.fields.summary` / `.fields.issuetype.name` attribute graph
the gateway reads. For the issue payloads alone we use a plain SimpleNamespace
— a real value object, not a mock — which is the cleanest substitute when
autospec is technically not viable.
"""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from jira import JIRA

from rebelist.hack.config.settings import (
    JiraIssueCustomFieldSettings,
    JiraIssueCustomFieldType,
    JiraIssueFieldsSettings,
    JiraSettings,
)
from rebelist.hack.domain.models import Ticket
from rebelist.hack.infrastructure.jira.adapter import JiraGateway, JiraMapper


def _settings_with(custom_fields: list[JiraIssueCustomFieldSettings]) -> JiraSettings:
    return JiraSettings(
        host='https://jira.example.com',
        token='tok',  # type: ignore[arg-type]
        fields=JiraIssueFieldsSettings(project='XX', reporter='alice', issue_types=['Bug']),
        custom_fields=custom_fields,
    )


@pytest.mark.unit
class TestJiraMapper:
    """Verify mapper output for all custom-field types and the defaults path."""

    def test_emits_base_fields_for_a_minimal_ticket(self, jira_settings: JiraSettings) -> None:
        """The base fields (project, summary, issuetype, reporter, description) are always present."""
        mapper = JiraMapper(jira_settings)
        ticket = Ticket(summary='Fix login', kind='Bug', description='h2. Steps')

        payload = mapper.to_dict(ticket)

        assert payload['project'] == {'key': jira_settings.fields.project}
        assert payload['summary'] == 'Fix login'
        assert payload['issuetype'] == {'name': 'Bug'}
        assert payload['reporter'] == {'name': jira_settings.fields.reporter}
        assert payload['description'] == 'h2. Steps'

    def test_user_custom_field_uses_name_envelope(self) -> None:
        """USER custom fields wrap the value in {'name': ...}."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10001', alias='owner', field_type=JiraIssueCustomFieldType.USER, value='alice'
                )
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10001'] == {'name': 'alice'}

    def test_select_custom_field_uses_value_envelope(self) -> None:
        """SELECT custom fields wrap the value in {'value': ...}."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10002',
                    alias='category',
                    field_type=JiraIssueCustomFieldType.SELECT,
                    value='Operational',
                )
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10002'] == {'value': 'Operational'}

    def test_multi_select_custom_field_with_list_value(self) -> None:
        """MULTI_SELECT lists become a list of {'value': item} envelopes."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10003',
                    alias='teams',
                    field_type=JiraIssueCustomFieldType.MULTI_SELECT,
                    value=['Team A', 'Team B'],
                )
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10003'] == [{'value': 'Team A'}, {'value': 'Team B'}]

    def test_multi_select_custom_field_with_scalar_value(self) -> None:
        """MULTI_SELECT with a single str is wrapped in a one-element list."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10003',
                    alias='teams',
                    field_type=JiraIssueCustomFieldType.MULTI_SELECT,
                    value='Team A',
                )
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10003'] == [{'value': 'Team A'}]

    def test_text_custom_field_passes_value_through(self) -> None:
        """TEXT custom fields write the raw value with no envelope."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10004',
                    alias='points',
                    field_type=JiraIssueCustomFieldType.TEXT,
                    value='5',
                )
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10004'] == '5'

    def test_processes_multiple_field_types_in_order(self) -> None:
        """All custom fields are mapped regardless of their position in the list."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10004', alias='points', field_type=JiraIssueCustomFieldType.TEXT, value='5'
                ),
                JiraIssueCustomFieldSettings(
                    name='customfield_10001', alias='owner', field_type=JiraIssueCustomFieldType.USER, value='alice'
                ),
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert payload['customfield_10004'] == '5'
        assert payload['customfield_10001'] == {'name': 'alice'}

    def test_skips_custom_fields_with_empty_value(self) -> None:
        """Custom fields with falsy values (None, '', []) are not emitted at all."""
        settings = _settings_with(
            [
                JiraIssueCustomFieldSettings(
                    name='customfield_10001', alias='owner', field_type=JiraIssueCustomFieldType.USER, value=None
                ),
                JiraIssueCustomFieldSettings(
                    name='customfield_10002', alias='cat', field_type=JiraIssueCustomFieldType.SELECT, value=''
                ),
                JiraIssueCustomFieldSettings(
                    name='customfield_10003', alias='teams', field_type=JiraIssueCustomFieldType.MULTI_SELECT, value=[]
                ),
            ]
        )

        payload = JiraMapper(settings).to_dict(Ticket(summary='S', kind='Bug', description='D'))

        assert 'customfield_10001' not in payload
        assert 'customfield_10002' not in payload
        assert 'customfield_10003' not in payload


@pytest.mark.unit
class TestJiraGateway:
    """Verify gateway delegates to the JIRA client and the mapper."""

    def test_add_ticket_calls_create_issue_and_returns_keyed_copy(self) -> None:
        """add_ticket delegates to JIRA.create_issue and returns a copy of the ticket with the issued key."""
        client = create_autospec(JIRA, instance=True)
        client.create_issue.return_value = SimpleNamespace(key='WS-42')
        mapper = create_autospec(JiraMapper, instance=True)
        mapper.to_dict.return_value = {'summary': 'S'}
        gateway = JiraGateway(client, mapper)
        ticket = Ticket(summary='S', kind='Bug', description='D')

        result = gateway.add_ticket(ticket)

        mapper.to_dict.assert_called_once_with(ticket)
        client.create_issue.assert_called_once_with(fields={'summary': 'S'})
        assert result.key == 'WS-42'
        assert ticket.key is None

    def test_get_ticket_constructs_ticket_from_jira_issue(self) -> None:
        """JiraGateway.get_ticket fetches the issue and maps it to a domain Ticket."""
        client = create_autospec(JIRA, instance=True)
        client.issue.return_value = SimpleNamespace(
            key='WS-7',
            fields=SimpleNamespace(
                summary='Fix login',
                issuetype=SimpleNamespace(name='Bug'),
                description='h2. Steps',
            ),
        )
        mapper = create_autospec(JiraMapper, instance=True)
        gateway = JiraGateway(client, mapper)

        ticket = gateway.get_ticket('WS-7')

        client.issue.assert_called_once_with('WS-7')
        assert ticket.key == 'WS-7'
        assert ticket.summary == 'Fix login'
        assert ticket.kind == 'Bug'
        assert ticket.description == 'h2. Steps'

    def test_get_ticket_falls_back_to_empty_description_when_missing(self) -> None:
        """If the Jira issue has no description attribute, the ticket description becomes ''."""
        client = create_autospec(JIRA, instance=True)
        client.issue.return_value = SimpleNamespace(
            key='WS-7',
            fields=SimpleNamespace(summary='Fix login', issuetype=SimpleNamespace(name='Bug')),
        )
        mapper = create_autospec(JiraMapper, instance=True)
        gateway = JiraGateway(client, mapper)

        ticket = gateway.get_ticket('WS-7')

        assert ticket.description == ''
