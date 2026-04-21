from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.config.settings import (
    JiraIssueTypeSettings,
    JiraSettings,
    JiraTicketCustomFieldSettings,
    JiraTicketFieldsSettings,
    JiraTicketReporterSettings,
)
from rebelist.hack.models.jira import CustomFieldType, DraftTicket, Ticket


class TestTicketFactory:
    def test_create_ticket_from_draft(self) -> None:
        """Verify that create method correctly maps DraftTicket and Settings to a Ticket."""
        # Setup mock settings
        jira_fields = JiraTicketFieldsSettings(
            project='PROJ',
            reporter=JiraTicketReporterSettings(default='reporter_user'),
            issue_type=JiraIssueTypeSettings(options=['Task', 'Bug']),
        )

        custom_field_cfg = JiraTicketCustomFieldSettings(
            name='customfield_10001', field_type=CustomFieldType.SELECT, default='Value1'
        )

        settings = JiraSettings(
            host='https://jira.com',
            token='token',
            fields=jira_fields,
            custom_fields={'Priority': custom_field_cfg},
            templates=[],
        )

        factory = TicketFactory(settings)

        draft = DraftTicket(summary='Test Summary', issue_type='Task', description='Test Description')

        ticket = factory.create(draft)

        assert isinstance(ticket, Ticket)
        assert ticket.project == 'PROJ'
        assert ticket.summary == 'Test Summary'
        assert ticket.reporter == 'reporter_user'
        assert ticket.description == 'Test Description'
        assert ticket.issue_type == 'Task'

        assert len(ticket.custom_fields) == 1
        cf = ticket.custom_fields[0]
        assert cf.field_id == 'customfield_10001'
        assert cf.field_type == CustomFieldType.SELECT
        assert cf.alias == 'Priority'
        assert cf.value == 'Value1'
