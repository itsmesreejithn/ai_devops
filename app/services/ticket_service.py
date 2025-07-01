from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from typing import Dict, Any
import requests
from app.models.states.TicketState import TicketState
from app.config import Config
from app.constants import JENKINS_ROLE, JENKINS_BASE_CONFIG_TEMPLATE, JENKINS_BASE_DEPLOYMENT_CONFIG_TEMPLATE
from app.utils.jenkins_utils import generate_basic_auth_header, create_jenkins_job, run_jenkins_job
from app.utils.ssh_utils import read_readme
from app.utils.logger import logger
from app.templates.prompt_template import JENKINS_BUILD_FAILURE_PROMPT, TICKET_ANALYSIS_PROMPT, DOCKER_RUN_COMMAND_GENERATOR_PROMPT
import re
import json
import time
from xml.sax.saxutils import escape
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

CHECKPOINTER = InMemorySaver()

def analyze_description(state: TicketState) -> TicketState:
    """Analyze the ticket description using model."""
    try:
        logger.info("Analyzing ticket description with LLM")
        # llm = ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.1)
        llm = ChatGroq(model=Config.GROQ_MODEL, temperature=0.1)
        prompt = PromptTemplate(template=TICKET_ANALYSIS_PROMPT)
        response = llm.invoke(prompt.format(description=state['description'], docker_hub_repository=Config.DOCKER_HUB_REPOSITORY))
    except Exception as e:
        logger.error(f"Error analyzing description: {e}")
        raise Exception(f"Error analyzing description: {e}")
    
    # Extract JSON from response
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response.content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response.content

    try:
        result_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        logger.error(f"Raw response: {response.content}")
        # Fallback values
        result_json = {
            "branch_name": "main",
            "repository_url": "",
            "summary": "Failed to parse description",
            "repository_name": "unknown",
            "build_command": "docker build -t app .",
            "jenkins_job_name": "app-pipeline",
            "image": "app:latest"
        }

    return {
        "branch_name": result_json.get("branch_name", ""),
        "repository_url": result_json.get("repository_url", ""),
        "summary": result_json.get("summary", ""),
        "repository_name": result_json.get("repository_name", ""),
        "build_command": result_json.get("build_command", ""),
        "jenkins_job_name": result_json.get("jenkins_job_name", ""),
        "image": result_json.get("image", "")
    }

def add_jenkins_user_to_repository(state: TicketState) -> TicketState:
    """Add Jenkins user to the repository."""

    logger.info(f"Adding Jenkins user to repository: {state['repository_name']}")

    PROJECT_URL = f"{Config.GITLAB_URL}/api/v4/projects?search={state['repository_name']}"
    USER_URL = f"{Config.GITLAB_URL}/api/v4/users?username={Config.JENKINS_USERNAME}"
    try:
        projects = requests.get(PROJECT_URL, headers={
            "Authorization": f"Bearer {Config.GITLAB_ADMIN_ACCESS_TOKEN}"
        })

        users = requests.get(USER_URL, headers={
            "Authorization": f"Bearer {Config.GITLAB_ADMIN_ACCESS_TOKEN}"
        })

        if projects.status_code != 200 or users.status_code != 200:
            raise Exception("Failed to fetch projects or users.")
        elif len(projects.json()) == 0 or len(users.json()) == 0:
            raise Exception("No projects or users found with the provided details.")

        if projects and users:
            project_id = projects.json()[0]["id"]
            user_id = users.json()[0]["id"]
            state["ssh_url_to_repo"] = projects.json()[0]["ssh_url_to_repo"]

            ADD_USER_TO_PROJECT_URL = f"{Config.GITLAB_URL}/api/v4/projects/{project_id}/members?user_id={user_id}&access_level={JENKINS_ROLE}"
            resonse = requests.post(ADD_USER_TO_PROJECT_URL, headers={
                "Authorization": f"Bearer {Config.GITLAB_ADMIN_ACCESS_TOKEN}"
            })

            if resonse.status_code == 201 or resonse.status_code == 409:
                logger.info("Jenkins user added to the repository successfully.")
            else:
                logger.error("Failed to add Jenkins user to the repository.")
                raise Exception("Failed to add Jenkins user to the repository.")
        return state
    except Exception as e:
        logger.error(f"Error adding Jenkins user to repository: {e}")
        raise Exception(e)
    
def jenkins_job(state: TicketState) -> TicketState:
    """Create a jenkins job tor the ticket and run that job"""
    try:
        jenkins_job_name = f'{state["jenkins_job_name"]}-{state["current_job"]}'
        if state["current_job"] == "build":
            logger.info("Running build job")
            build_command = f"{state['build_command']} \n echo 'This is the paswd for docker' docker login -u sreejithai --password-stdin \n docker push {state['image']}"
            config_xml = JENKINS_BASE_CONFIG_TEMPLATE.replace("<GIT_SSH_URL>", escape(state["ssh_url_to_repo"])).replace("<JENKINS_CREDENTIAL_ID>", escape(Config.JENKINS_CREDENTIAL_ID)).replace("<BRANCH_NAME>", escape(state["branch_name"] if state["branch_name"] else "main")).replace("<BUILD_COMMAND>", escape(build_command))
            response = create_jenkins_job(config_xml=config_xml, jenkins_job_name=jenkins_job_name)
            if not response:
                raise Exception("Failed to create Jenkins job.")
        elif state["current_job"] == "deploy":
            logger.info("Running deploy job")
            llm = ChatGroq(model=Config.GROQ_MODEL, temperature=0.1)
            prompt = PromptTemplate(template=DOCKER_RUN_COMMAND_GENERATOR_PROMPT)
            llm_response = llm.invoke(prompt.format(read_me=state["read_me"], dockerfile=state["dockerfile"], build_command=state["build_command"]))
            
            # Extract JSON from response
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', llm_response.content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = llm_response.content
                
            try:
                response_json = json.loads(json_str)
                generated_command = response_json.get("command", "")

                verificaiton_prompt = f"""
                Please review the generated Docker run command:
                {generated_command}
                
                Is this command correct for deploying the application?.
                - Type 'yes' to approve the command.
                - Type 'no' to reject the command.
                - Or type a custom command to use instead.
                """

                # Store the generated command in state for later use
                state["generated_command"] = generated_command
                
                # Use interrupt to pause and wait for human input
                user_response = interrupt(verificaiton_prompt)

                if user_response.lower().strip() == "yes":
                    state["run_command"] = generated_command
                    logger.info("User approved the generated Docker run command.")
                elif user_response.lower().strip() == "no":
                    logger.info("User rejected the Docker run command. Deployment will not proceed.")
                    state["current_job"] = "done"
                    return state
                else:
                    state["run_command"] = user_response.strip()
                    logger.info(f"User provided a custom Docker run command: {user_response.strip()}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                state["run_command"] = "docker run -d --name app app:latest"  # Fallback command
                
            deploy_command = f"echo 'This is the paswd for docker' sudo docker login -u sreejithai --password-stdin \n sudo {state['run_command']}"
            config_xml = JENKINS_BASE_DEPLOYMENT_CONFIG_TEMPLATE.replace("<AGENT_NODE>", escape(Config.JENKSIN_AGETN_NODE)).replace("<DEPLOY_COMMAND>", escape(deploy_command)) 
            response = create_jenkins_job(config_xml=config_xml, jenkins_job_name=jenkins_job_name)
            if not response:
                raise Exception("Failed to run Jenkins job.")
            
        if state["current_job"] != "done": 
            response = run_jenkins_job(jenkins_job_name=jenkins_job_name)
            if not response:
                raise Exception("Failed to run Jenkins job.")

        if state["current_job"] == "build":    
            read_me, dockerfile = read_readme(jenkins_job_name=jenkins_job_name)
            state["read_me"] = read_me
            state["dockerfile"] = dockerfile
        state["current_jenkins_job"] = jenkins_job_name
        return state
    except Exception as e:
        logger.error(f"Failed Jenkins job: {e}")
        raise Exception(f"Error creating Jenkins job: {e}")

def analyze_jenkis_console_output(state: TicketState) -> TicketState:
    """Analyze the the jenkis console outup"""
    try:
        logger.info(f'Analyzing jenkins job {state["current_jenkins_job"]} console output with LLM')
        time.sleep(10)
        console_analysis = {}
        # llm = ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.1)
        llm = ChatGroq(model=Config.GROQ_MODEL, temperature=0.1)
        JENKINS_CONSOLE_TEXT_URL = f"{Config.JENKINS_URL}/job/{state['current_jenkins_job']}/lastBuild/consoleText"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(JENKINS_CONSOLE_TEXT_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        })
        jenkins_response.raise_for_status()
        if jenkins_response.status_code == 200:
            console_text = jenkins_response.text 
            
            if "Finished: FAILURE" in console_text:
                logger.warning(f'Jenkins job {state["current_jenkins_job"]} failed')
                prompt = PromptTemplate(template=JENKINS_BUILD_FAILURE_PROMPT)     

                response = llm.invoke(prompt.format(
                    repository_name = state["repository_name"],
                    branch_name = state["branch_name"],
                    build_command = state["build_command"],
                    jenkins_job_name = state["current_jenkins_job"],
                    console_text = console_text,
                ))
                logger.info(f"Jenkins console output analyzed successfully")
                console_analysis = json.loads(response.content) or {}
            elif "Finished: SUCCESS" in console_text:
                logger.info(f'Jenkins job {state["current_jenkins_job"]} success')
        
        state["console_analysis"] = console_analysis
        
        if state["current_job"] == "build":
            logger.info(f"Current jenkins job switced to deploy")
            state["current_job"] = "deploy"
            return state

        if state["current_job"] == "deploy":
            logger.info(f"Current jenkins job switced to done")
            state["current_job"] = "done"
            return state

    except Exception as e:
        logger.error(f"Failed to analyze jenkins job console output: {e}")
        raise Exception(f"Failed to analyze jenkins job console output: {e}")

def should_loop(state: TicketState) -> str:
    """Check if the ticket is done"""
    if state["current_job"] == "done":
        return "end"
    if state["current_job"] == "deploy":
        return "continue"

def create_ticket_workflow():
    """Create the ticket workflow graph."""
    workflow = StateGraph(TicketState)
    
    # Nodes
    workflow.add_node("analyze", analyze_description)
    workflow.add_node("gitlab", add_jenkins_user_to_repository)
    workflow.add_node("jenkins", jenkins_job)
    workflow.add_node("console", analyze_jenkis_console_output)

    # Edges
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "gitlab")
    workflow.add_edge("gitlab", "jenkins")
    workflow.add_edge("jenkins", "console")
    workflow.add_conditional_edges(
        "console",
        should_loop,
        {
            "continue": "jenkins",
            "end": END
        }
    )
    workflow.add_edge("console", END)
    
    # Compile the graph
    return workflow.compile(checkpointer=CHECKPOINTER)


def process_ticket_description(thread_id: str, description: str = None, user_input: str = None) -> Dict[str, Any]:
    """Process a ticket description through the workflow."""
    logger.info("Starting ticket processing workflow")

    workflow = create_ticket_workflow()
    thread_config = {"configurable": {"thread_id": thread_id}}
    
    try:
        if user_input is None and description is not None:
            # Initialize state for new workflow
            initial_state = TicketState(
                description=HumanMessage(content=description),
                branch_name="",
                repository_url="",
                repository_name="",
                ssh_url_to_repo="",
                summary="",
                jenkins_job_name="",
                build_command="",
                readme_content="",
                current_job="build",
                read_me="",
                run_command="",
                current_jenkins_job="",
                image=""
            )
            logger.info(f"Processing ticket with description: {description[:100]}...")
            result = workflow.invoke(initial_state, config=thread_config)
        else:
            logger.info(f"Resuming workflow with user input: {user_input} and thread_id: {thread_id}")
            result = workflow.invoke(Command(resume=user_input), config=thread_config)
        
        logger.info(f"Ticket processing completed successfully for repository: {result['repository_name']}")
        return {
            "ticket_description": result["description"].content,
            "summary": result["summary"],
            "branch_name": result["branch_name"],
            "repository_name": result["repository_name"],
            "repository_url": result["repository_url"],
            "build_command": result["build_command"],
            "ssh_url_to_repo": result["ssh_url_to_repo"],
            "jenkins_job_name": result["jenkins_job_name"],
            "console_analysis": result["console_analysis"],
        }
    except Exception as e:
        logger.error(f"Error in ticket processing: {e}")
        raise e