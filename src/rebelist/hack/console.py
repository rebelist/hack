import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final

from pydantic import ValidationError
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from typer import Argument, Context, Exit, Option, Typer, confirm, prompt  # type: ignore

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings, SettingsError, YamlSettingsSource

console = Console()
error_console = Console(stderr=True)
app = Typer()
jira = Typer()
git = Typer()
score = Typer()

app.add_typer(jira, name='jira', help='Jira subcommand to interact with Jira workflows.')
app.add_typer(git, name='git', help='Git subcommand to interact with Git workflows.')
app.add_typer(score, name='score', help='Score subcommand to keep a score log of your achievements.')


@dataclass
class ApplicationState:
    """Per-invocation state attached to the Typer Context."""

    container: Container
    debug: bool


class Application:
    EXIT_ERROR: Final[int] = 1
    EXIT_SIGINT: Final[int] = 130

    def __call__(self) -> None:
        """Entry point. Render failures as a red line; let Typer-driven exits pass through."""
        debug = '--debug' in sys.argv
        try:
            app()
        except KeyboardInterrupt:
            error_console.print('[yellow]Aborted.[/yellow]')
            sys.exit(Application.EXIT_SIGINT)
        except Exception as error:
            if debug:
                error_console.print_exception()
            else:
                error_console.print(
                    Panel(str(error), title='[bold red]Error[/bold red]', border_style='red', title_align='left')
                )
            sys.exit(Application.EXIT_ERROR)


@app.callback(invoke_without_command=True)
def bootstrap(
    context: Context,
    version: bool = Option(False, '--version', help='Show version and exit.'),
    debug: bool = Option(False, '--debug', help='Show stack traces on error.'),
) -> None:
    """Bootstrap the console and handle global options."""
    try:
        container = Container(Settings())
    except ValidationError as error:
        raise SettingsError.from_validation_error(error) from error

    context.obj = ApplicationState(container=container, debug=debug)

    if version or context.invoked_subcommand is None:
        metadata = Settings.get_metadata()
        console.print(f'{metadata[0].capitalize()} - v{metadata[1]}')
        console.print(f'Run [green]{metadata[0]}[/green] [yellow]--help[/yellow] for more information.')
        raise Exit()


@app.command(name='info')
def diagnose_command(context: Context) -> None:
    """Show environment, version, and config metadata. Secrets are redacted."""
    state: ApplicationState = context.obj
    settings = state.container.settings

    table = Table(show_header=False, header_style='bold cyan')
    table.add_column('Property', style='yellow', no_wrap=True)
    table.add_column('Value')

    table.add_section()
    table.add_row('[bold green]General[/bold green]', '')
    table.add_section()
    table.add_row('Version', f'v{settings.general.version}')
    table.add_row('Python', sys.version.split()[0])
    table.add_row('Config Class', settings.__class__.__name__)
    table.add_row('Config Path', str(YamlSettingsSource.get_user_config_path()))
    table.add_section()

    table.add_section()
    table.add_row('[bold green]Agent[/bold green]', '')
    table.add_section()
    table.add_row('Model', settings.agent.model)
    table.add_row('API Key Name', settings.agent.api_key_name)
    table.add_row('API Key', '[dim](redacted)[/dim]')
    table.add_section()

    table.add_section()
    table.add_row('[bold green]Jira[/bold green]', '')
    table.add_section()
    table.add_row('Host', settings.jira.host)
    table.add_row('Token', '[dim](redacted)[/dim]')
    table.add_row('Project', settings.jira.fields.project)
    table.add_row('Issue Types', ', '.join(settings.jira.fields.issue_types))
    table.add_section()

    table.add_section()
    table.add_row('[bold green]Git[/bold green]', '')
    table.add_section()
    table.add_row('Branch Categories', ', '.join(settings.git.branch_categories))
    table.add_section()

    table.add_section()
    table.add_row('[bold green]Score[/bold green]', '')
    table.add_section()
    database_path = YamlSettingsSource.get_user_config_path().parent / state.container.DATABASE_FILE_NAME
    table.add_row('Database', str(database_path))

    console.print(table)


@jira.command(name='ticket')
def jira_ticket_command(
    context: Context,
    description: Annotated[str, Argument(help='Ticket description (use quotes for multiple words).')],
    dry_run: Annotated[bool, Option('--dry-run', help='Render the ticket without creating it in Jira.')] = False,
) -> None:
    """Create a Jira ticket from a natural language description. The type is inferred from a predefined set."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Outsourcing clarity to a neural network...[/grey58]', spinner='dots'):
        ticket = state.container.create_ticket_command(description, dry_run=dry_run)

    if dry_run:
        console.print('[tan]Dry run — no ticket created![/tan]')
        table = Table(show_header=True, width=120, show_lines=True)
        table.add_column('Section', style='yellow', no_wrap=True)
        table.add_column('Value')

        table.add_row('Summary', ticket.summary)
        table.add_row('Kind', ticket.kind)
        table.add_row('Description', Markdown(ticket.description, justify='left'))

        console.print(table)
        return

    console.print(f'[green]Ticket created! [/green] {state.container.settings.jira.host}/browse/{ticket.key}')


@git.command(name='branch')
def git_checkout_branch_command(
    context: Context,
    ticket_key: Annotated[str, Argument(help='Ticket key like WS-120.')],
    dry_run: Annotated[bool, Option('--dry-run', help='Print the resolved branch name without checking out.')] = False,
) -> None:
    """Checkout a new git branch from a jira ticket identifier."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Attempting to translate human intent into a branch name...[/grey58]', spinner='dots'):
        output = state.container.git_checkout_branch_command(ticket_key, dry_run=dry_run)

    if dry_run:
        console.print(f'[tan]Dry run — would checkout:[/tan] {output}')
        return
    console.print(output)


@git.command(name='commit')
def git_commit_command(
    context: Context,
    description: Annotated[str, Argument(help='Commit message description')],
    dry_run: Annotated[bool, Option('--dry-run', help='Print the rendered commit message without committing.')] = False,
) -> None:
    """Perform a commit on the current git repository."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Compressing human chaos into a commit message...[/grey58]', spinner='dots'):
        output = state.container.git_commit_command(description, dry_run=dry_run)

    if dry_run:
        console.print('[tan]Dry run — no commit created.[/tan]')
    console.print(output)


@score.command(name='save')
def score_save_command(
    context: Context,
    description: Annotated[str, Argument(help='What you accomplished (use quotes for multiple words).')],
    dry_run: Annotated[bool, Option('--dry-run', help='Show the cleaned entry without saving it.')] = False,
) -> None:
    """Save an achievement to your score log. The entry is lightly cleaned up by an LLM before storing."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Polishing your humble brag...[/grey58]', spinner='dots'):
        saved = state.container.score_save_command(description, dry_run=dry_run)

    if dry_run:
        console.print('[tan]Dry run — nothing saved.[/tan]')
        console.print(saved.description)
        return

    console.print(f'[green]Achievement logged![/green] {saved.description}')


@score.command(name='export')
def score_export_command(
    context: Context,
    file: Annotated[Path, Argument(help='Destination markdown file, e.g. score-log.md.')],
    dry_run: Annotated[bool, Option('--dry-run', help='Render the score log without writing the file.')] = False,
) -> None:
    """Export every achievement as a categorized, LLM-formatted score log markdown file."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Spinning a year of wins into a brag...[/grey58]', spinner='dots'):
        markdown = state.container.score_export_command(file, dry_run=dry_run)

    if dry_run:
        console.print('[tan]Dry run — file not written.[/tan]')
        console.print(Markdown(markdown))
        return

    console.print(f'[green]Score log exported![/green] {file}')


@score.command(name='list')
def score_list_command(context: Context) -> None:
    """List your score log entries chronologically (oldest first), each prefixed with its id."""
    state: ApplicationState = context.obj

    with console.status('[grey58]Tallying up your wins...[/grey58]', spinner='dots'):
        scores = state.container.score_list_command()

    if not scores:
        console.print('[tan]No achievements recorded yet. Use `hack score save "..."` to add one.[/tan]')
        return

    for score_entry in scores:
        timestamp = score_entry.created_at.strftime('%Y-%m-%d %H:%M') if score_entry.created_at else ''
        label = escape(f'[{score_entry.entry_id}]')
        console.print(f'[cyan]{label}[/cyan] [dim]{timestamp}[/dim]  {escape(score_entry.description)}')


@score.command(name='delete')
def score_delete_command(
    context: Context,
    entry_id: Annotated[int | None, Option('--entry-id', help='Id of the entry to delete.')] = None,
    all_entries: Annotated[bool, Option('--all', help='Delete every entry from the score log.')] = False,
) -> None:
    """Delete a score log entry by its id, or wipe the whole log with --all."""
    state: ApplicationState = context.obj

    if all_entries:
        if not confirm('This will permanently delete ALL score log entries. Are you sure?'):
            console.print('[tan]Aborted — nothing was deleted.[/tan]')
            return
        with console.status('[grey58]Wiping the slate clean...[/grey58]', spinner='dots'):
            removed = state.container.score_delete_all_command()
        console.print(f'[green]Deleted all {removed} score log entries.[/green]')
        return

    target_id: int = entry_id if entry_id is not None else prompt('Which entry id do you want to delete?', type=int)

    with console.status('[grey58]Rewriting history...[/grey58]', spinner='dots'):
        deleted = state.container.score_delete_command(target_id)

    if deleted is None:
        console.print(f'[yellow]No entry found with id {target_id}.[/yellow]')
        return

    console.print(f'[green]Deleted entry {target_id}.[/green] {escape(deleted.description)}')


main = Application()
