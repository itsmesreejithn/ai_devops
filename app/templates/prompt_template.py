# Reflection and Analysis Prompt Template for Jenkins Build Failure

JENKINS_BUILD_FAILURE_PROMPT = """
You are an expert DevOps engineer analyzing a Jenkins build failure. Take a step-by-step approach to diagnose and solve this issue.

**Build Context:**
- Repository: {repository_name}
- Branch: {branch_name}
- Build Command: {build_command}
- Job Name: {jenkins_job_name}

**Console Output:**
{console_text}

**Reflection and Analysis Process**

1. **Initial Assessment**
- What type of faliure occured? (compilation, dependency, configuration, etc.)
- At what stage did the build fail? (checkout, build, test, deployment)
- Are there any obvious error patterns or keywords?

2. **Root Cause Analysis**
- What is the primary error messge or exception?
- Are there any dependency conflicts or missing packages?
- Is this a code issue, environment issue, or configuration issue?
- Could this be related to the specific branch error or recent changes?

3. **Context Consideration**
- Does the error relate to the Docker build command used?
- Are there any environment-specifig issue (paths, permissions, resources)?
- Could this be a timing issue or resource constraint?

4. **Solution Strategy**
- What is the most likely fix for the issue?
- Are there alternative approach if the primary solution doesn't work?
- What preventive measures can be implemented?

5. **Action Plan**
Provide specific, actionable steps to resolve this issue:
- Immediate fixes to try
- Code changes needed (if any)
- Configuration adjustments
- Jenkis job modifications
- Testing recommendations


**IMPORTANT: Format your response as valid JSON with the following structure:**

{{
    "issue_summary": "Brief description of what went wrong",
    "root_cause": "Detailed explanation of why this happened",
    "failure_type": "compilation|dependency|configuration|environment|other",
    "failure_stage": "checkout|build|test|deployment|other",
    "primary_error": "Main error message or exception found",
    "recommended_solutions": {{
        "primary_solution": {{
            "description": "Most likely fix description",
            "steps": [
                "Step 1: Specific action to take",
                "Step 2: Next specific action",
                "Step 3: Additional action if needed"
            ]
        }},
        "alternative_solutions": [
            {{
                "description": "Alternative approach 1",
                "steps": [
                    "Alternative step 1",
                    "Alternative step 2"
                ]
            }},
            {{
                "description": "Alternative approach 2", 
                "steps": [
                    "Another alternative step 1",
                    "Another alternative step 2"
                ]
            }}
        ]
    }},
    "prevention_measures": [
        "Prevention measure 1",
        "Prevention measure 2",
        "Prevention measure 3"
    ],
    "next_steps": [
        "Immediate action 1",
        "Immediate action 2",
        "Immediate action 3"
    ],
    "code_changes_needed": true/false,
    "configuration_changes_needed": true/false,
    "jenkins_job_changes_needed": true/false,
    "estimated_fix_time": "quick|medium|complex"
}}

Return ONLY the JSON response, no additional text or formatting.

"""

# Ticket analysis prompt
TICKET_ANALYSIS_PROMPT = """

Analyze the following ticket description and provide insights:
        
{description}
        
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
        "repository_url": "<complete-url>",
        "build_command": "<suggested-docker-build-command>",
        "jenkins_job_name": "<suggested-jenkins-job-name>"
    }}
    ```

    Extraction rules:
    - repository_name: Take ONLY the text after the FINAL slash in the URL
    - branch_name: Extract exactly as mentioned (dev, main, feature/name, etc.)
    - repository_url: Copy the complete URL exactly as provided
    - If no branch is mentioned, use empty string ""
    - For build_command, use format: "docker build -t <repository_name>:<branch-or-latest> (USE BRANCH NAME FOR TAGGING IF BRANCH NAME IS AVAILABLE) ."

    Return ONLY the JSON object with no additional text.
"""