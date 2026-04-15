from tools import *
from your_llm_client import call_llm

def agent(task, file_content):
    prompt = f"""
    Fix this Kubernetes YAML and make it valid.

    YAML:
    {file_content}
    """

    fixed = call_llm(prompt)

    write_file("deployment.yaml", fixed)

    valid, err = validate_yaml("deployment.yaml")

    if not valid:
        return file_content  # fallback

    git_commit("AI fix manifest")
    git_push()

    return fixed
