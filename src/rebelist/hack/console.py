from typing import Annotated

from rich import print as pprint
from rich.text import Text
from typer import Argument, Context, Exit, Option, Typer

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings

app = Typer()
jira = Typer()

app.add_typer(jira, name='jira')


@app.callback(invoke_without_command=True)
def bootstrap(context: Context, version: bool = Option(None, '--version', help='Show version.')) -> None:
    """Bootstrap the console and handle global options."""
    container = Container(Settings.instance())
    context.obj = container

    if version or context.invoked_subcommand is None:
        pprint(Text(f'{container.settings.general.name.capitalize()} - v{container.settings.general.version}'))
        pprint('Run [green]hack[/green] [yellow]--help[/yellow] for more information.')

        raise Exit()


@jira.command()
def ticket(
    context: Context, description: Annotated[str, Argument(help='Ticket description (use quotes for multiple words).')]
) -> None:
    """Create a Jira ticket from a natural language description. The type is inferred from a predefined set."""
    container: Container = context.obj
    key = container.create_ticket_command(description)
    pprint(f'[green]Ticket created! [/green] {container.settings.jira.host}/browse/{key}')


def main() -> None:
    """Entry point."""
    app()
