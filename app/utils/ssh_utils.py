import paramiko
from app.utils.logger import logger
from app.config import Config

def reader(ssh_client, command: str):
    stdin, stdout, stderr = ssh_client.exec_command(command)
    reader_path = stdout.read().decode('utf-8').strip()
    if not reader_path:
        return ""
    stdin, stdout, stderr = ssh_client.exec_command(f"cat {reader_path}")
    read_content = stdout.read().decode('utf-8')
        
    return read_content

def read_readme(jenkins_job_name: str) -> tuple:
    """Read the README.md file from the workspace path."""
    ssh_client = None
    try:
        logger.info(f"Connecting to Jenkins server to fetch README.md")
        workspace_path = f"{Config.JENKINS_WORKSPACE_PATH}/{jenkins_job_name}"
        logger.info(f"Workspace path: {workspace_path}")
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        username = Config.JENKINS_SSH_USERNAME
        hostname = Config.JENKINS_SSH_HOST
        
        # Connect using password authentication with specific SSH options
        ssh_client.connect(
            hostname=hostname,
            port=2222,
            username=username,
            password=Config.JENKINS_SSH_PASSWORD,
            allow_agent=False,
            look_for_keys=False,
            disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']}
        )
        
        # Check if README.md exists
        readme_content = reader(ssh_client, f"find {workspace_path} -name 'README.md' | head -1")
        dockerfile_content = reader(ssh_client, f"find {workspace_path} -name 'Dockerfile' | head -1")

        return readme_content, dockerfile_content
        
    except Exception as e:
        logger.error(f"Error fetching README.md: {e}")
        return "", ""  # Return empty tuple to match expected return type
    finally:
        if ssh_client:
            ssh_client.close()