import sys
from typing import Annotated

from jira.exceptions import JIRAError
from pydantic import ValidationError
from rich.console import Console
from rich.text import Text
from typer import Argument, Context, Exit, Option, Typer

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.infrastructure.git.manager import GitCommandError, GitTimeoutError

console = Console()
error_console = Console(stderr=True)
app = Typer()
jira = Typer()
git = Typer()

app.add_typer(jira, name='jira')
app.add_typer(git, name='git')


@app.callback(invoke_without_command=True)
def bootstrap(context: Context, version: bool = Option(None, '--version', help='Show version.')) -> None:
    """Bootstrap the console and handle global options."""
    container = Container(Settings.instance())
    context.obj = container

    if version or context.invoked_subcommand is None:
        name = container.settings.general.name.lower()
        console.print(Text(f'{name.capitalize()} - v{container.settings.general.version}'))
        console.print(f'Run [green]{name}[/green] [yellow]--help[/yellow] for more information.')

        raise Exit()


@jira.command(name='ticket')
def jira_ticket_command(
    context: Context, description: Annotated[str, Argument(help='Ticket description (use quotes for multiple words).')]
) -> None:
    """Create a Jira ticket from a natural language description. The type is inferred from a predefined set."""
    container: Container = context.obj

    with console.status('[grey58]Outsourcing clarity to a neural network...[/grey58]', spinner='dots'):
        ticket = container.create_ticket_command(description)
        console.print(f'[green]Ticket created! [/green] {container.settings.jira.host}/browse/{ticket.key}')


@git.command(name='branch')
def git_checkout_branch_command(
    context: Context, ticket_key: Annotated[str, Argument(help='Ticket key like WS-120.')]
) -> None:
    """Checkout a new git branch from a jira ticket identifier."""
    container: Container = context.obj

    with console.status('[grey58]Attempting to translate human intent into a branch name...[/grey58]', spinner='dots'):
        output = container.git_checkout_branch_command(ticket_key)
        console.print(output)


@git.command(name='commit')
def git_commit_command(
    context: Context, description: Annotated[str, Argument(help='Commit message description')]
) -> None:
    """Perform a commit on the current git repository."""
    container: Container = context.obj

    with console.status('[grey58]Compressing human chaos into a commit message...[/grey58]', spinner='dots'):
        output = container.git_commit_command(description)
        console.print(output)


def main() -> None:
    """Entry point. Render expected failures as a single red line; let Typer-driven exits pass through."""
    try:
        app()
    except Exit:
        raise
    except (GitCommandError, GitTimeoutError) as error:
        error_console.print(f'[red]Git error:[/red] {error}')
        sys.exit(1)
    except JIRAError as error:
        message = error.text or str(error)
        error_console.print(f'[red]Jira error:[/red] {message}')
        sys.exit(1)
    except ValidationError as error:
        error_console.print(f'[red]Invalid agent output:[/red] {error.error_count()} validation error(s).')
        sys.exit(1)
    except KeyboardInterrupt:
        error_console.print('[yellow]Aborted.[/yellow]')
        sys.exit(130)
    except Exception as error:
        error_console.print(f'[red]Unexpected error:[/red] {error}')
        sys.exit(1)
