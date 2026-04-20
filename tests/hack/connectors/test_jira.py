from typing import Any
from unittest.mock import create_autospec

from jira import JIRA

from rebelist.hack.connectors.jira import JiraGateway, JiraTicketMapper
from rebelist.hack.models.jira import CustomField, CustomFieldType, Ticket


class TestJiraTicketMapper:
    def test_map_basic_fields(self) -> None:
        """Verify that basic ticket fields are mapped correctly to Jira API format."""
        ticket = Ticket(
            project='HACK', summary='Summary', reporter='user1', description='Desc', issue_type='Task', custom_fields=[]
        )

        expected: dict[str, Any] = {
            'project': {'key': 'HACK'},
            'summary': 'Summary',
            'issuetype': {'name': 'Task'},
            'reporter': {'name': 'user1'},
            'description': 'Desc',
        }

        assert JiraTicketMapper.map(ticket) == expected

    def test_map_custom_fields(self) -> None:
        """Verify that various custom field types are mapped correctly."""
        custom_fields = [
            CustomField(field_id='customfield_101', field_type=CustomFieldType.USER, alias='Assignee', value='bob'),
            CustomField(field_id='customfield_102', field_type=CustomFieldType.SELECT, alias='Priority', value='High'),
            CustomField(
                field_id='customfield_103', field_type=CustomFieldType.MULTI_SELECT, alias='Labels', value=['L1', 'L2']
            ),
            CustomField(field_id='customfield_104', field_type=CustomFieldType.MULTI_SELECT, alias='Tags', value='T1'),
            CustomField(field_id='customfield_105', field_type=CustomFieldType.TEXT, alias='Note', value='Some text'),
        ]
        ticket = Ticket(
            project='HACK', summary='S', reporter='u', description='D', issue_type='Task', custom_fields=custom_fields
        )

        mapped = JiraTicketMapper.map(ticket)

        assert mapped['customfield_101'] == {'name': 'bob'}
        assert mapped['customfield_102'] == {'value': 'High'}
        assert mapped['customfield_103'] == [{'value': 'L1'}, {'value': 'L2'}]
        assert mapped['customfield_104'] == [{'value': 'T1'}]
        assert mapped['customfield_105'] == 'Some text'


class TestJiraGateway:
    def test_add_ticket(self) -> None:
        """Verify that add_ticket calls the Jira client with mapped data."""
        mock_client = create_autospec(JIRA)
        gateway = JiraGateway(mock_client)

        ticket = Ticket(
            project='HACK', summary='Summary', reporter='user1', description='Desc', issue_type='Task', custom_fields=[]
        )

        mock_issue = create_autospec(lambda: None)
        mock_issue.key = 'HACK-999'
        mock_client.create_issue.return_value = mock_issue

        key = gateway.add_ticket(ticket)

        assert key == 'HACK-999'
        mock_client.create_issue.assert_called_once()
        _, kwargs = mock_client.create_issue.call_args
        assert kwargs['fields']['project']['key'] == 'HACK'
