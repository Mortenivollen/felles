"""
================================================================================
Lab 06b - Multi-Agents with Foundry (Beginner Training Script)
================================================================================
SCENARIO
--------
"Festival Planner Crew" helps a student plan a one-day city festival trip:
1) Explorer Agent proposes fun activity ideas.
2) Budget Agent turns ideas into a realistic spending plan.
3) Safety Agent checks practical risks and adds fallback suggestions.
4) Host Agent combines everything into one easy final itinerary.

WHAT THIS LAB TEACHES
---------------------
- How to create multiple Foundry AI agents from code.
- How to orchestrate them in a simple sequential pipeline.
- How one agent's output can become another agent's input.

PREREQUISITES
-------------
- az login
- .env file with:
    PROJECT_ENDPOINT=https://<your-foundry-project>.services.ai.azure.com/api/projects/<project>
    MODEL_DEPLOYMENT_NAME=gpt-4o-mini
================================================================================
"""

import os
from typing import Dict, List, Tuple

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


# We keep the agent names stable so students can re-run this script and see
# predictable resources in Foundry.
AGENT_CONFIGS: List[Tuple[str, str]] = [
    (
        "festival-explorer-agent",
        (
            "You are an Explorer Agent for city festivals. "
            "Given a user profile, suggest exactly 3 experiences. "
            "For each experience, include why it matches the user."
        ),
    ),
    (
        "festival-budget-agent",
        (
            "You are a Budget Agent. "
            "Convert festival ideas into a practical cost plan with categories: "
            "transport, food, tickets, and buffer. "
            "Keep total cost <= the user's budget when possible."
        ),
    ),
    (
        "festival-safety-agent",
        (
            "You are a Safety Agent. "
            "Review the draft plan and list 3 practical risks plus 3 mitigations. "
            "Focus on weather, crowd levels, and backup options."
        ),
    ),
    (
        "festival-host-agent",
        (
            "You are the Host Agent. "
            "Combine all specialist outputs into one polished day plan with this structure: "
            "Morning, Midday, Evening, Budget Summary, Safety Notes."
        ),
    ),
]


def validate_settings() -> Tuple[str, str]:
    """Read required environment variables and fail early if missing."""
    endpoint = os.getenv("PROJECT_ENDPOINT", "").strip()
    model_name = os.getenv("MODEL_DEPLOYMENT_NAME", "").strip()

    missing = [
        name
        for name, value in (
            ("PROJECT_ENDPOINT", endpoint),
            ("MODEL_DEPLOYMENT_NAME", model_name),
        )
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing required setting(s): "
            + ", ".join(missing)
            + ". Add them to your .env file before running this script."
        )

    return endpoint, model_name


def create_agent_versions(project_client: AIProjectClient, model_name: str) -> List[Tuple[str, str]]:
    """
    Create one version for each specialist agent.

    Returns a list of (agent_name, agent_version) so we can clean them up later.
    """
    created_versions: List[Tuple[str, str]] = []

    for agent_name, instructions in AGENT_CONFIGS:
        version = project_client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=model_name,
                instructions=instructions,
            ),
        )
        created_versions.append((version.name, version.version))
        print(f"Created agent version: {version.name} (v{version.version})")

    return created_versions


def run_agent(openai_client, agent_name: str, prompt: str) -> str:
    """
    Send one prompt to a specific Foundry agent and return plain text output.

    Note for learners:
    - extra_body.agent_reference tells Foundry which named agent to use.
    - The response object usually contains output_text for the final text answer.
    """
    response = openai_client.responses.create(
        input=prompt,
        extra_body={
            "agent_reference": {
                "name": agent_name,
                "type": "agent_reference",
            }
        },
    )
    return (response.output_text or "").strip() or "(No response text returned.)"


def ask_user_profile() -> Tuple[str, int, str]:
    """Collect simple user preferences to make the demo feel interactive."""
    city = input("City for your festival day plan [Lisbon]: ").strip() or "Lisbon"

    budget_text = input("Budget in USD [120]: ").strip() or "120"
    try:
        budget = max(20, int(budget_text))
    except ValueError:
        budget = 120

    vibe = input("Preferred vibe (music, food, art, mixed) [mixed]: ").strip() or "mixed"
    return city, budget, vibe


def main() -> None:
    load_dotenv()
    endpoint, model_name = validate_settings()

    city, budget, vibe = ask_user_profile()

    # We keep these outside the try block so cleanup logic can access them.
    created_versions: List[Tuple[str, str]] = []

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        try:
            created_versions = create_agent_versions(project_client, model_name)

            print("\nRunning multi-agent pipeline...\n")

            # Step 1: Explorer proposes festival experiences.
            explorer_output = run_agent(
                openai_client,
                "festival-explorer-agent",
                (
                    f"Create ideas for a one-day festival in {city}. "
                    f"User vibe: {vibe}. Keep suggestions concrete and beginner friendly."
                ),
            )

            # Step 2: Budget specialist receives Explorer output as context.
            budget_output = run_agent(
                openai_client,
                "festival-budget-agent",
                (
                    f"User budget: ${budget}.\n"
                    "Festival ideas from Explorer Agent:\n"
                    f"{explorer_output}"
                ),
            )

            # Step 3: Safety specialist checks risks in the draft plan.
            safety_output = run_agent(
                openai_client,
                "festival-safety-agent",
                (
                    "Review this plan and provide practical safety guidance.\n"
                    f"Ideas:\n{explorer_output}\n\nBudget Draft:\n{budget_output}"
                ),
            )

            # Step 4: Host agent merges all specialist outputs into one final answer.
            final_plan = run_agent(
                openai_client,
                "festival-host-agent",
                (
                    f"City: {city}\n"
                    f"Budget target: ${budget}\n"
                    f"Vibe: {vibe}\n\n"
                    f"Explorer output:\n{explorer_output}\n\n"
                    f"Budget output:\n{budget_output}\n\n"
                    f"Safety output:\n{safety_output}"
                ),
            )

            print("=" * 72)
            print("FINAL FESTIVAL PLAN")
            print("=" * 72)
            print(final_plan)
            print("=" * 72)

        finally:
            # Always attempt cleanup so Foundry projects do not collect many temp versions.
            for agent_name, agent_version in created_versions:
                try:
                    project_client.agents.delete_version(
                        agent_name=agent_name,
                        agent_version=agent_version,
                    )
                    print(f"Deleted temporary version: {agent_name} (v{agent_version})")
                except Exception as cleanup_error:
                    print(
                        "Cleanup warning for "
                        f"{agent_name} (v{agent_version}): {cleanup_error}"
                    )


if __name__ == "__main__":
    main()
