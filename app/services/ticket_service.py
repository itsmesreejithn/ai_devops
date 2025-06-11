from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from typing import TypedDict, Dict, Any
import requests
from app.config import Config
from app.constants import JENKINS_ROLE, JENKINS_BASE_CONFIG_TEMPLATE, JENKINS_BASE_DEPLOYMENT_CONFIG_TEMPLATE
from app.utils.jenkins_utils import generate_basic_auth_header, create_jenkins_job, run_jenkins_job
from app.utils.logger import logger
from app.templates.prompt_template import JENKINS_BUILD_FAILURE_PROMPT, TICKET_ANALYSIS_PROMPT
import re
import json
import time
from xml.sax.saxutils import escape
from lxml import etree
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class TicketState(TypedDict):
    description: HumanMessage
    branch_name: str
    repository_name: str
    repository_url: str
    ssh_url_to_repo: str
    summary: str
    build_command: str
    jenkins_job_name: str
    console_analysis: Dict[str, Any]
    current_job: str

def analyze_description(state: TicketState) -> TicketState:
    """Analyze the ticket description using model."""
    try:
        logger.info("Analyzing ticket description with LLM")
        # llm = ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.1)
        llm = ChatGroq(model=Config.GROQ_MODEL, temperature=0.1)
        prompt = PromptTemplate(template=TICKET_ANALYSIS_PROMPT)
        response = llm.invoke(prompt.format(description=state['description']))
    except Exception as e:
        logger.error(f"Error analyzing description: {e}")
        raise Exception(f"Error analyzing description: {e}")
    
    # Extract JSON from response
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response.content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response.content

    result_json = json.loads(json_str)

    return {
        "branch_name": result_json.get("branch_name", ""),
        "repository_url": result_json.get("repository_url", ""),
        "summary": result_json.get("summary", ""),
        "repository_name": result_json.get("repository_name", ""),
        "build_command": result_json.get("build_command", ""),
        "jenkins_job_name": result_json.get("jenkins_job_name", "")
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
        if state["current_job"] == "build":
            config_xml = JENKINS_BASE_CONFIG_TEMPLATE.replace("<GIT_SSH_URL>", escape(state["ssh_url_to_repo"])).replace("<JENKINS_CREDENTIAL_ID>", escape(Config.JENKINS_CREDENTIAL_ID)).replace("<BRANCH_NAME>", escape(state["branch_name"] if state["branch_name"] else "main")).replace("<BUILD_COMMAND>", escape(state["build_command"]))
            response = create_jenkins_job(config_xml=config_xml, jenkins_job=state["jenkins_job_name"])
            if not response:
                raise Exception("Failed to create Jenkins job.")
        elif state["current_job"] == "deploy":
            config_xml = JENKINS_BASE_DEPLOYMENT_CONFIG_TEMPLATE.replace("<AGENT_NODE>", escape()).replace("<DEPLOY_COMMAND", ) 
            response = create_jenkins_job(jenkins_job=state["jenkins_job_name"])
            if not response:
                raise Exception("Failed to run Jenkins job.")

    except Exception as e:
        logger.error(f"Failed Jenkins job: {e}")
        raise Exception(f"Error creating Jenkins job: {e}")


def create_jenkins_job(state: TicketState) -> TicketState:
    """Create a Jenkins job for the ticket."""
    try:
        config_xml = JENKINS_BASE_CONFIG_TEMPLATE.replace("<GIT_SSH_URL>", escape(state["ssh_url_to_repo"])).replace("<JENKINS_CREDENTIAL_ID>", escape(Config.JENKINS_CREDENTIAL_ID)).replace("<BRANCH_NAME>", escape(state["branch_name"] if state["branch_name"] else "main")).replace("<BUILD_COMMAND>", escape(state["build_command"]))
        etree.fromstring(config_xml.encode('utf-8'))
        JENKINS_CREATE_JOB_URL = f"{Config.JENKINS_URL}/createItem"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(JENKINS_CREATE_JOB_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        },
        params={"name": state["jenkins_job_name"]},
        data=config_xml.encode('utf-8'))
        jenkins_response.raise_for_status()
        if jenkins_response.status_code == 200:
            logger.info("Jenkins job created successfully.")
        return state
    except Exception as e:
        logger.error(f"Failed to create Jenkins job: {e}")
        raise Exception(f"Failed to create Jenkins job configuration: {e}")

def run_jenkins_job(state: TicketState) -> TicketState:
    """Run the jenkins job after job createion"""
    try:
        logger.info(f'Trigger jenkins job {state["jenkins_job_name"]}')
        TRIGGER_JENKINS_JOB_URL = f"{Config.JENKINS_URL}/job/{state['jenkins_job_name']}/build"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(TRIGGER_JENKINS_JOB_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        })
        jenkins_response.raise_for_status()
        if jenkins_response.status_code == 201:
            logger.info("Jenkins job triggered successfully.")
        return state
    except Exception as e:
        logger.error(f"Failed to trigger Jenkins job: {e}")
        raise Exception(f"Failed to trigger Jenkins job: {e}")

def analyze_jenkis_console_output(state: TicketState) -> TicketState:
    """Analyze the the jenkis console outup"""
    try:
        logger.info(f'Analyzing jenkins job {state["jenkins_job_name"]} console output with LLM')
        time.sleep(10)
        llm = ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.1)
        JENKINS_CONSOLE_TEXT_URL = f"{Config.JENKINS_URL}/job/{state['jenkins_job_name']}/lastBuild/consoleText"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(JENKINS_CONSOLE_TEXT_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        })
        jenkins_response.raise_for_status()
        if jenkins_response.status_code == 200:
            console_text = jenkins_response.text
            if "Finished: FAILURE" in console_text:
                logger.warning(f'Jenkins job {state["jenkins_job_name"]} failed')
                prompt = PromptTemplate(template=JENKINS_BUILD_FAILURE_PROMPT)     

                response = llm.invoke(prompt.format(
                    repository_name = state["repository_name"],
                    branch_name = state["branch_name"],
                    build_command = state["build_command"],
                    jenkins_job_name = state["jenkins_job_name"],
                    console_text = console_text
                ))
                logger.info(f"Jenkins console output analyzed successfully")

            return {
                "console_analysis": json.loads(response.content) or {}
            }
        
        if state["current_job"] == "build":
            logger.info(f"Current jenkins job switced to deploy")
            return {
                "current_job" : "deploy"
            }

        if state["current_job"] == "deploy":
            logger.info(f"Current jenkins job switced to done")
            return {
                "current_job" : "done"
            }
    except Exception as e:
        logger.error(f"Failed to analyze jenkins job console output: {e}")
        raise Exception(f"Failed to analyze jenkins job console output: {e}")

def create_ticket_workflow():
    """Create the ticket workflow graph."""
    workflow = StateGraph(TicketState)
    
    # Nodes
    workflow.add_node("analyze", analyze_description)
    workflow.add_node("gitlab", add_jenkins_user_to_repository)
    workflow.add_node("jenkins", create_jenkins_job)
    workflow.add_node("run", run_jenkins_job)
    workflow.add_node("console", analyze_jenkis_console_output)

    # Edges
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "gitlab")
    workflow.add_edge("gitlab", "jenkins")
    workflow.add_edge("jenkins", "run")
    workflow.add_edge("run", "console")
    workflow.add_edge("console", END)
    
    # Compile the graph
    return workflow.compile()

def process_ticket_description(description: str) -> Dict[str, Any]:
    """Process a ticket description through the workflow."""

    logger.info("Starting ticket processing workflow")
    workflow = create_ticket_workflow()
    
    # Initialize state
    initial_state = TicketState(
        description=HumanMessage(content=description),
        branch_name="",
        repository_url="",
        repository_name="",
        ssh_url_to_repo="",
        summary="",
        build_command="",
        console_analysis="",
        current_job="build"
    )
    
    logger.info(f"Processing ticket with description: {description[:100]}...")
    # Execute the workflow
    result = workflow.invoke(initial_state)
    
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
        "console_analysis": result["console_analysis"]
    }