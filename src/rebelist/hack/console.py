import sys
from dataclasses import dataclass
from typing import Annotated, Final

from pydantic import ValidationError
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from typer import Argument, Context, Exit, Option, Typer

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings, SettingsError

console = Console()
error_console = Console(stderr=True)
app = Typer()
jira = Typer()
git = Typer()

app.add_typer(jira, name='jira', help='Jira subcommand to interact with Jira workflows.')
app.add_typer(git, name='git', help='Git subcommand to interact with Git workflows.')


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
        except Exit:
            raise
        except KeyboardInterrupt:
            error_console.print('[yellow]Aborted.[/yellow]')
            sys.exit(Application.EXIT_SIGINT)
        except Exception as error:
            error_console.print(f'[red]Error:[/red] {error}')
            if debug:
                error_console.print_exception()
            sys.exit(Application.EXIT_ERROR)


@app.callback(invoke_without_command=True)
def bootstrap(
    context: Context,
    version: bool = Option(False, '--version', help='Show version and exit.'),
    debug: bool = Option(False, '--debug', help='Show stack traces on error.'),
) -> None:
    """Bootstrap the console and handle global options."""
    try:
        container = Container(Settings.instance())
    except ValidationError as error:
        raise SettingsError.from_validation_error(error) from error

    context.obj = ApplicationState(container=container, debug=debug)

    if version or context.invoked_subcommand is None:
        name = container.settings.general.name.lower()
        console.print(f'{name.capitalize()} - v{container.settings.general.version}')
        console.print(f'Run [green]{name}[/green] [yellow]--help[/yellow] for more information.')
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
        console.print('[yellow]Dry run — no ticket created![/yellow]')
        table = Table(show_header=False, width=120)
        table.add_column('Property', style='yellow', no_wrap=True)
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
        console.print(f'[yellow]Dry run —[/yellow] would checkout: {output}')
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
        console.print('[yellow]Dry run — no commit created.[/yellow]')
    console.print(output)


main = Application()
