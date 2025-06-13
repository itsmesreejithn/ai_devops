from langchain_core.messages import HumanMessage
from typing import TypedDict, Dict, Any


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
    read_me: str
    run_command: str
    dockerfile: str
    current_jenkins_job: str
    image: str