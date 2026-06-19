import os
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential


# Clear the console
os.system('cls' if os.name=='nt' else 'clear')

# Load environment variables from .env file
load_dotenv()
project_endpoint= os.getenv("PROJECT_ENDPOINT")
model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

healer_agent_name = "healer_bot"
healer_instructions = """
    You are a wise healer in a fantasy world. You tend to the health of your party members using magic and 
    by crafting potions. Your role is to assess injuries, perform healing actions, and advise on rest or 
    recovery when needed.

    Stay in character — do not reference technology or the user. Instead, respond with your choice of action.

    Keep your responses brief. Do not ask for more data — make a decision based on the scene described, 
    even if it's uncertain.

    Examples of situations you respond to: limping, poison, fatigue, battle wounds, cursed injuries, and morale.
"""

scout_agent_name = "scout_bot"
scout_instructions = """
    You are a clever and observant scout in a fantasy world. Your specialty is exploration, navigation, 
    puzzle-solving, and detecting traps. You assess situations that require perception, strategy, or finesse.

    Your task is to briefly describe what you notice or would do based on the environment. You should respond 
    like you're physically present — describe a clue you see, what you suspect, or what action you take.

    Keep responses short and strategic.

    Examples of situations you respond to: suspicious doors, puzzle mechanisms, hidden paths, trap triggers, terrain choices, and stealth.
"""

warrior_agent_name = "warrior_bot"
warrior_instructions = """
    You are a seasoned warrior adventurer in a fantasy world. Your job is to respond to threats, handle physical challenges, 
    and assess any situations that involve combat, brute force, or physical strength.

    Only respond with what you would do or how you assess the situation from your perspective as the warrior. Use brief, 
    confident language. Stay in character. No apologies, no unnecessary elaboration — just action and instinct.

    Examples of situations you respond to: ambushes, enemy attacks, broken doors, carrying heavy objects, or preparing for battle.
"""

if not project_endpoint or not model_deployment:
    raise ValueError("Set PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME in your environment or .env file.")


quest_master_instructions = """
You are the Questmaster, the intelligent guide of a three-member adventuring party exploring a short dungeon.
Delegate parts of the scenario to the Warrior, Scout, and Healer based on their specialties.

Return exactly three lines in this order:
Warrior: <response>
Scout: <response>
Healer: <response>
"""


def get_response_text(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text.strip()

    parts = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") != "message":
            continue
        for block in getattr(item, "content", []) or []:
            text_block = getattr(block, "text", None)
            value = getattr(text_block, "value", text_block)
            if value:
                parts.append(str(value).strip())

    return "\n".join(part for part in parts if part)


def create_prompt_agent(project, name: str, instructions: str):
    return project.agents.create_version(
        agent_name=name,
        definition=PromptAgentDefinition(
            model=model_deployment,
            instructions=instructions,
        ),
    )


def ask_agent(openai_client, agent_name: str, prompt: str) -> str:
    response = openai_client.responses.create(
        input=prompt,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
    )
    return get_response_text(response)


def delete_agent_version(project, agent_name: str, version: str) -> None:
    project.agents.delete_version(agent_name=agent_name, agent_version=version)


created_agents = []

with AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential()) as project:
    openai_client = project.get_openai_client()

    try:
        healer_agent = create_prompt_agent(project, healer_agent_name, healer_instructions)
        created_agents.append(healer_agent)

        scout_agent = create_prompt_agent(project, scout_agent_name, scout_instructions)
        created_agents.append(scout_agent)

        warrior_agent = create_prompt_agent(project, warrior_agent_name, warrior_instructions)
        created_agents.append(warrior_agent)

        quest_master_agent_name = "quest_master"
        quest_master_agent = create_prompt_agent(project, quest_master_agent_name, quest_master_instructions)
        created_agents.append(quest_master_agent)

        prompt = "We find a locked door with strange symbols, and the warrior is limping."
        print("Processing quest scenario. Please wait.")

        warrior_result = ask_agent(openai_client, warrior_agent_name, prompt)
        scout_result = ask_agent(openai_client, scout_agent_name, prompt)
        healer_result = ask_agent(openai_client, healer_agent_name, prompt)

        orchestrated_prompt = f"""
Scenario: {prompt}

Warrior draft response: {warrior_result}
Scout draft response: {scout_result}
Healer draft response: {healer_result}

Combine these into final coordinated actions.
""".strip()

        final_result = ask_agent(openai_client, quest_master_agent_name, orchestrated_prompt)
        print(f"assistant:\n{final_result}\n")

    finally:
        print("Cleaning up agents:")
        for created_agent in reversed(created_agents):
            try:
                delete_agent_version(project, created_agent.name, created_agent.version)
                print(f"Deleted {created_agent.name} (v{created_agent.version}).")
            except Exception as ex:  # pylint: disable=broad-exception-caught
                print(f"Could not delete {created_agent.name}: {ex}")