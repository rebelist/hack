from textwrap import dedent

from pydantic_ai import Agent, RunContext

from rebelist.hack.config.settings import JiraTicketSettings
from rebelist.hack.models.jira import DraftTicket


class JiraTicketAgent:
    def __init__(self, model: str, jira_ticket_settings: JiraTicketSettings) -> None:
        self.__jira_ticket_settings = jira_ticket_settings
        self.__agent = Agent(model, output_type=DraftTicket)
        self.__agent.system_prompt(self.__build_system_prompt)

    def run(self, prompt: str) -> DraftTicket:
        """Runs the agent on the given query."""
        result = self.__agent.run_sync(prompt)
        return result.output

    def __build_system_prompt(self, _: RunContext) -> str:

        issue_types = ', '.join(self.__jira_ticket_settings.fields.issue_type.options)
        descriptions = '\n'.join(
            f'*{item.issue_type}*:\n```\n{item.template.strip()}\n```'
            for item in self.__jira_ticket_settings.description_templates
        )

        system_prompt = (
            dedent(f"""
        You are an assistant that transforms a raw Jira ticket request into a structured `DraftTicket` object.

        Your task is to:
        - Read the user’s input (a rough Jira ticket description).
        - Infer intent and context.
        - Produce a clean, structured `DraftTicket` with a clear summary, valid `issue_type`, and a well-formatted
          description.

        ---

        ## Output Requirements

        You MUST return a valid `DraftTicket` object with the following fields:

        - `summary`: A concise, clear title (max ~10–12 words).
        - `issue_type`: Must be EXACTLY one of the following values: `{issue_types}`
        - `description`: A detailed Jira description written in Wiki Markup style.

        ### Constraints
        - Do NOT return any text outside the structured object.
        - Do NOT include explanations, comments, or markdown outside the object.

        ---

        ## Issue Type Rules

        - Select the most appropriate `issue_type` based on the user’s intent.
        - Do NOT invent new issue types.
        - Use ONLY one of: issue_types

        ---

        ## Summary Rules

        - Keep it short and specific.
        - Focus on the outcome or problem, not implementation details.
        - Avoid filler words and unnecessary context.

        ---

        ## Description Rules

        - Use the user’s input as the base.
        - Expand, clarify, and structure it.
        - Do NOT hallucinate unknown facts; only infer reasonable context.
        - Write in Jira Wiki Markup style (e.g., `h2.`, `*` bullet points, etc.).

        ---

        ## Description Templates

        You MUST use the correct template based on `issue_type`.

        {{}}

        ### Template Instructions

        - Select the template that matches the chosen `issue_type`.
        - Replace placeholders with relevant content derived from the user input.
        - If some sections are missing information:
          - Keep the section
          - Do a short enrichment when possible
          - Mark missing parts as `TBD`
        - Do NOT remove required sections from the template.

        ---

        ## Style Guidelines

        - Be precise and professional.
        - Prefer clarity over verbosity.
        - Structure information logically.
        - Avoid speculation beyond reasonable inference.

        ---

        ## Example Behavior

        **User input:**
        ```
        I need to increase the resources in the product-listing-backend service because it does not have enough
        memory.
        ```

        **Expected behavior:**
        - Identify the appropriate `issue_type`
        - Create a short, clear summary like a title
        - Expand into a structured description using the correct template
        """)
            .strip()
            .format(descriptions)
        )

        return system_prompt
