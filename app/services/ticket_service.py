from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage
from typing import TypedDict, Dict, Any
import requests
from app.config import Config
from app.constants import JENKINS_ROLE, JENKINS_BASE_CONFIG_TEMPLATE
from app.utils.jenkins_utils import generate_basic_auth_header
import re
import json
from xml.sax.saxutils import escape
from lxml import etree

class TicketState(TypedDict):
    description: HumanMessage
    branch_name: str
    repository_name: str
    repository_url: str
    ssh_url_to_repo: str
    summary: str
    build_command: str
    jenkins_job_name: str

def analyze_description(state: TicketState) -> TicketState:
    """Analyze the ticket description using model."""

    llm = ChatOllama(model=Config.OLLAMA_MODEL, temperature=0.1)

    prompt = f"""
    Analyze the following ticket description and provide insights:
    
    {state['description']}
    
    Please provide:
    1. A brief summary of what the user wants to do
    2. The exact branch name mentioned in the description
    3. The complete repository URL mentioned in the description 
    4. The repository name (ONLY the final part after the last slash in the URL)
    5. Suggest appropriate Docker build command based on the repository name and branch name
    6. Suggest a Jenkins job name based on the repository name and branch name and if branch name is not provided, use "latest" as default.

    For Docker build command, consider:
        - User repository name as image name (lowercase)
        - Include a tag (latest or branch name)
        - Standard Docker build syntax

    Examples of good Docker commands:
        - "docker build -t my-app:latest ."
        - "docker build -t service-name:dev ."
        - "docker build -f Dockerfile -t app-name:v1.o ."
    
    Example: From URL "https://git.exmaple.com/xyz/project-smart/smart-tools/smart-service"
    - repository_name should be: "smart-service"

    Format the response as a JSON object:
    
    ```json
    {{
        "summary": "<brief summary>",
        "repository_name": "<final-part-of-url-only>", 
        "branch_name": "<extract-branch-name>", 
        "repository_url": "<complete-url>"
        "build_command": "<suggested-docker-build-command>"
        "jenkins_job_name": "<suggested-jenkins-job-name>"
    }}
    ```

    Extraction rules:
    - repository_name: Take ONLY the text after the FINAL slash in the URL
    - branch_name: Extract exactly as mentioned (dev, main, feature/name, etc.)
    - repository_url: Copy the complete URL exactly as provided
    - If no branch is mentioned, use empty string ""
    - For build_command, use format: "docker build -t <repository_name>:<branch-or-latest> ."

    Return ONLY the JSON object with no additional text.
    """
    
    response = llm.invoke(prompt)
    
    # Extract JSON from response
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response.content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response.content

    result_json = json.loads(json_str)

    state["branch_name"] = result_json.get("branch_name", "")
    state["repository_url"] = result_json.get("repository_url", "")
    state["summary"] = result_json.get("summary", "")
    state["repository_name"] = result_json.get("repository_name", "")
    state["build_command"] = result_json.get("build_command", "")
    state["jenkins_job_name"] = result_json.get("jenkins_job_name", "")

    return state

def add_jenkins_user_to_repository(state: TicketState) -> TicketState:
    """Add Jenkins user to the repository."""

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
                print("Jenkins user added to the repository successfully.")
            else:
                print("Failed to add Jenkins user to the repository.")
                raise Exception("Failed to add Jenkins user to the repository.")
        return state
    except Exception as e:
        print(e)
        raise Exception(e)


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
        print(jenkins_response.text)
        if jenkins_response.status_code == 200:
            print("Jenkins job created successfully.")
        return state
    except Exception as e:
        print(e)
        raise Exception(f"Failed to create Jenkins job configuration: {e}")


def create_ticket_workflow():
    """Create the ticket workflow graph."""
    workflow = StateGraph(TicketState)
    
    # Nodes
    workflow.add_node("analyze", analyze_description)
    workflow.add_node("gitlab", add_jenkins_user_to_repository)
    workflow.add_node("jenkins", create_jenkins_job)

    # Edges
    workflow.add_edge(START, "analyze")
    workflow.add_edge("analyze", "gitlab")
    workflow.add_edge("gitlab", "jenkins")
    workflow.add_edge("jenkins", END)
    
    # Compile the graph
    return workflow.compile()

def process_ticket_description(description: str) -> Dict[str, Any]:
    """Process a ticket description through the workflow."""
    workflow = create_ticket_workflow()
    
    # Initialize state
    initial_state = TicketState(
        description=HumanMessage(content=description),
        branch_name="",
        repository_url="",
        repository_name="",
        ssh_url_to_repo="",
        summary="",
        build_command=""
    )
    
    # Execute the workflow
    result = workflow.invoke(initial_state)
    
    return {
        "ticket_description": result["description"].content,
        "summary": result["summary"],
        "branch_name": result["branch_name"],
        "repository_name": result["repository_name"],
        "repository_url": result["repository_url"],
        "build_command": result["build_command"],
        "ssh_url_to_repo": result["ssh_url_to_repo"],
        "jenkins_job_name": result["jenkins_job_name"]   
    }