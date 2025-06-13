import base64
import requests
from jenkinsapi.jenkins import Jenkins
from app.config import Config
from lxml import etree
from app.utils.logger import logger

# jenkins_server = Jenkins(baseurl=Config.JENKINS_URL, username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)

def generate_basic_auth_header(username: str, password: str) -> str:
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return encoded_credentials

def get_jenkins_crumb(JENKINS_URL: str, encoded_credentials: str) -> str:
    try: 
        CRUB_URL = f"{JENKINS_URL}/crumbIssuer/api/json"
        response = requests.get(CRUB_URL, headers={"Authorization": encoded_credentials})
        print(response.json())
        if response.status_code == 200:
            return response.json()["crumbRequestField"], response.json()["crumb"]
    except Exception as e:
        print(e)
        raise Exception(f"Failed to get Jenkins crumb: {e}")
    

def create_jenkins_job(config_xml: str, jenkins_job_name: str):
    try:
        etree.fromstring(config_xml.encode('utf-8'))
        JENKINS_CREATE_JOB_URL = f"{Config.JENKINS_URL}/createItem"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(JENKINS_CREATE_JOB_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        },
        params={"name": jenkins_job_name},
        data=config_xml.encode('utf-8'))
        jenkins_response.raise_for_status()
        if jenkins_response.status_code != 200:
            logger.error("Failed to create jenkins job.")
            return False
        logger.info("Jenkins job created successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to create Jenkins job: {e}")
        raise Exception(f"Failed to create Jenkins job configuration: {e}")

def run_jenkins_job(jenkins_job_name: str):
    try:
        logger.info(f'Trigger jenkins job {jenkins_job_name}')
        TRIGGER_JENKINS_JOB_URL = f"{Config.JENKINS_URL}/job/{jenkins_job_name}/build"
        encoded_credentials = generate_basic_auth_header(username=Config.JENKINS_USERNAME, password=Config.JENKINS_API_TOKEN)
        jenkins_response = requests.post(TRIGGER_JENKINS_JOB_URL, headers={
            'Content-Type': 'application/xml',
            'Authorization': f'Basic {encoded_credentials}',
        })
        jenkins_response.raise_for_status()
        if jenkins_response.status_code != 201:
            logger.error("Failed to trigger jenkisn job")
            return False
        logger.info("Jenkins job triggered successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger Jenkins job: {e}")
        raise Exception(f"Failed to trigger Jenkins job: {e}")

    
# def create_new_node(node_name: str, node_description: str, num_executors: int):
#     nodes = jenkins_server.get_nodes()
#     config = {
#         'name': node_name,
#         'nodeDescription': node_description,
#         'numExecutors': num_executors,
#         'remoteFS': '/home/jenkins/agent',
#         'labelString': 'SLAVE-DOCKER linux',
#         'mode': 'EXCLUSIVE',
#         'launcher': {
#             'stapler-class': 'hudson.slaves.JNLPLauncher',
#             '$class': 'hudson.slaves.JNLPLauncher',
#             'workDirSettings': {
#                 'disabled': True,
#                 'workDirPath': '',
#                 'internalDir': 'remoting',
#                 'failIfWorkDirIsMissing': False
#             },
#             'tunnel': '',
#             'vmargs': '-Xmx1024m'
#         },
#         'retentionStrategy': {
#             'stapler-class': 'hudson.slaves.RetentionStrategy$Always',
#             '$class': 'hudson.slaves.RetentionStrategy$Always'
#         }
#     }

#     new_node = nodes.create_node_with_config(name=node_name, config=config)
