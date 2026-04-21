from typing import Annotated

from rich.console import Console
from rich.text import Text
from typer import Argument, Context, Exit, Option, Typer

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings

console = Console()
app = Typer()
jira = Typer()

app.add_typer(jira, name='jira')


@app.callback(invoke_without_command=True)
def bootstrap(context: Context, version: bool = Option(None, '--version', help='Show version.')) -> None:
    """Bootstrap the console and handle global options."""
    container = Container(Settings.instance())
    context.obj = container

    if version or context.invoked_subcommand is None:
        console.print(Text(f'{container.settings.general.name.capitalize()} - v{container.settings.general.version}'))
        console.print('Run [green]hack[/green] [yellow]--help[/yellow] for more information.')

        raise Exit()


@jira.command()
def ticket(
    context: Context, description: Annotated[str, Argument(help='Ticket description (use quotes for multiple words).')]
) -> None:
    """Create a Jira ticket from a natural language description. The type is inferred from a predefined set."""
    container: Container = context.obj

    with console.status('[bold yellow]Outsourcing clarity to a neural network...', spinner='dots'):
        key = container.create_ticket_command(description)

    console.print(f'[green]Ticket created! [/green] {container.settings.jira.host}/browse/{key}')


def main() -> None:
    """Entry point."""
    app()
