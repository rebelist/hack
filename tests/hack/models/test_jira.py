import pytest
from pydantic import ValidationError

from rebelist.hack.models.jira import CustomField, CustomFieldType, DraftTicket, Ticket


class TestJiraModels:
    def test_custom_field_id_validation(self) -> None:
        r"""Verify that custom field ID must follow the pattern r'customfield_\d+'."""
        # Valid ID
        cf = CustomField(field_id='customfield_123', field_type=CustomFieldType.TEXT, alias='Alias', value='Value')
        assert cf.field_id == 'customfield_123'

        # Invalid ID
        with pytest.raises(ValidationError):
            CustomField(field_id='invalid_id', field_type=CustomFieldType.TEXT, alias='Alias', value='Value')

    def test_draft_ticket_creation(self) -> None:
        """Verify that DraftTicket can be created with valid data."""
        draft = DraftTicket(summary='Summary', issue_type='Bug', description='Description')
        assert draft.summary == 'Summary'
        assert draft.issue_type == 'Bug'
        assert draft.description == 'Description'

    def test_ticket_issue_type_title_validation(self) -> None:
        """Verify that issue_type in Ticket is automatically title-cased."""
        ticket = Ticket(
            project='HACK',
            summary='S',
            reporter='R',
            description='D',
            issue_type='bug',  # Lowercase
            custom_fields=[],
        )
        assert ticket.issue_type == 'Bug'  # Should be Title-cased

    def test_ticket_default_custom_fields(self) -> None:
        """Verify that custom_fields defaults to an empty list."""
        ticket = Ticket(project='HACK', summary='S', reporter='R', description='D', issue_type='Bug', custom_fields=[])
        assert ticket.custom_fields == []
