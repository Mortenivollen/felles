import os
from dotenv import load_dotenv
# Add references
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ConnectedAgentTool, MessageRole, ListSortOrder
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

# Connect to the agents client

# Initialize the AgentsClient
agents_client = AgentsClient(endpoint=project_endpoint, credential=DefaultAzureCredential())

with agents_client:

    # Create the healer agent on the Azure AI agent service
    # Create the healer agent on the Azure AI agent service
    healer_agent = agents_client.create_agent(
        model=model_deployment,
        name=healer_agent_name,
        instructions=healer_instructions
    )


    # Create a connected agent tool for the healer agent
    # Create the healer agent on the Azure AI agent service
    healer_agent_tool = ConnectedAgentTool(
        id=healer_agent.id, 
        name=healer_agent_name, 
        description="Responsible for healing party members and addressing injuries."
    )


    # Create the scout agent and connected tool
    # Create the scout agent and connected tool
    scout_agent = agents_client.create_agent(
        model=model_deployment,
        name=scout_agent_name,
        instructions=scout_instructions
    )
    scout_agent_tool = ConnectedAgentTool(
        id=scout_agent.id, 
        name=scout_agent_name, 
        description="Goes ahead of the main party to perform reconnaissance."
    )


    # Create the warrior agent and connected tool
    # Create the warrior agent and connected tool
    warrior_agent = agents_client.create_agent(
        model=model_deployment,
        name=warrior_agent_name,
        instructions=warrior_instructions
    )
    warrior_agent_tool = ConnectedAgentTool(
        id=warrior_agent.id, 
        name=warrior_agent_name, 
        description="Responds to combat or physical challenges."
    )


    # Create a main agent with the Connected Agent tools
    # Create a main agent with the Connected Agent tools
    agent = agents_client.create_agent(
        model=model_deployment,
        name="quest_master",
        instructions="""
            You are the Questmaster, the intelligent guide of a three-member adventuring party exploring a short dungeon. 
            Based on the scenario, delegate tasks to the appropriate party member. The current party members are: Warrior, Scout, Healer.
            Only include the party member's response, do not provide an analysis or summary.
        """,
        tools=[
            healer_agent_tool.definitions[0],
            scout_agent_tool.definitions[0],
            warrior_agent_tool.definitions[0]
        ]
    )


    # Create thread for the chat session
    # Create thread for the chat session
    print("Creating agent thread.")
    thread = agents_client.threads.create()


    # Create the quest prompt
    prompt = "We find a locked door with strange symbols, and the warrior is limping."


    # Send a prompt to the agent
    # Send a prompt to the agent
    message = agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=prompt,
    )


    # Create and process Agent run in thread with tools
    # Create and process Agent run in thread with tools
    print("Processing agent thread. Please wait.")
    run = agents_client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)


    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Fetch and log all messages
    messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    for message in messages:
        if message.text_messages:
            last_msg = message.text_messages[-1]
            print(f"{message.role}:\n{last_msg.text.value}\n")
    
    # Delete the Agent when done
    print("Cleaning up agents:")
    agents_client.delete_agent(agent.id)
    print("Deleted quest master agent.")

    # Delete the connected Agent when done
    agents_client.delete_agent(healer_agent.id)
    print("Deleted healer agent.")
    agents_client.delete_agent(scout_agent.id)
    print("Deleted scout agent.")
    agents_client.delete_agent(warrior_agent.id)
    print("Deleted warrior agent.")