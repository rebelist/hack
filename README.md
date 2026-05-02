<h1 align="center"><img src="docs/images/hack.png" alt="Hack"/></h1>
<p align="center">
    <b>An internal CLI tool to automate repetitive tasks and support more consistent development workflows.</b>
</p>

<p align="center">
   <a href="https://github.com/rebelist/hack/releases"><img src="https://img.shields.io/badge/Release-0.3.1-e63946?logo=github&logoColor=white" alt="Release" /></a>
   <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white" alt="Python" /></a>
   <a href="https://github.com/rebelist/hack/actions/workflows/ci.yaml"><img src="https://github.com/rebelist/hack/actions/workflows/ci.yaml/badge.svg" alt="CI" /></a>
   <a href="https://codecov.io/gh/rebelist/hack" ><img src="https://codecov.io/gh/rebelist/hack/graph/badge.svg?token=lqdBu0NiZO" alt="Codecov"/></a>
   <a href="https://mit-license.org/"><img src="https://img.shields.io/badge/License-MIT-lightgray.svg" alt="License: MIT" /></a>
</p>

---

`hack` is an internal CLI for automating repetitive development and coordination tasks, nudging teams toward consistent
practices.

The first workflow it ships is **AI-assisted Jira ticket creation**: natural-language input is interpreted by an LLM
into a structured draft, issue type, summary, and a wiki-style description, then applied against your team's
YAML-based field and template configuration.

## Requirements

- Python `3.14.x`
- A Jira instance and API token
- A model supported by [`pydantic-ai`](https://ai.pydantic.dev/models/) — defaults to
  `openrouter:nvidia/nemotron-3-super-120b-a12b:free`

## Installation

```bash
brew install pipx
pipx ensurepath
pipx install git+https://github.com/rebelist/hack.git
```

## Configuration

Run `hack` once to generate the config file, then open it:

```bash
~/.config/hack/config.yaml
```

Fill in the required values:

```yaml
agent:
  model: "openrouter:nvidia/nemotron-3-super-120b-a12b:free"
  api_key_name: "OPENROUTER_API_KEY"
  api_key: ""                          # Use a dummy value for Ollama

jira:
  host: "https://jira.example.com"
  token: ""
```

> Any provider supported by [pydantic-ai](https://ai.pydantic.dev/models/) works, including Ollama for local models.

Then configure your Jira templates and field values to match your project's conventions.

## Usage

```bash
hack jira ticket "Users can't reset their password on mobile"
```

The command interprets the input, picks the right issue type, writes a structured description, and creates the ticket in
Jira using your configured templates.

![demo_ticket_create.gif](docs/images/demo_ticket_create.gif)

```bash
hack git branch "WS-1238"
```

Fetches the Jira ticket, passes its details to an LLM to pick a branch category and a kebab-case name, then checks out
a new branch named `{category}/{TICKET-KEY}-{kebab-name}` (e.g. `feature/WS-1238-reset-password-on-mobile`).

![demo_git_branch.gif](docs/images/demo_git_branch.gif)

```bash
hack git commit "Some description of the commit"
```

Reads the current branch to extract the ticket key, passes your description to an LLM to produce a concise commit
subject and optional body, then commits with the ticket key auto-prepended to the subject (e.g.
`WS-1238 Fix reset password on mobile`).

![demo_git_commit.gif](docs/images/demo_git_commit.gif)

## License

[MIT](https://mit-license.org/)