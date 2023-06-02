# Docker Image Cleanup Script

This Python script is designed to clean up Docker images from a Harbor registry.

## Usage

The script can be run from the command line with several arguments:

```bash
python3 -mpip install -r requirements.txt
python3 src/main.py --harbor-url <HARBOR_URL> --username <USERNAME> --password <PASSWORD> --project-name <PROJECT_NAME> [--repository-name <REPOSITORY_NAME>] --domain-name <DOMAIN_NAME> [--ignore-tags <IGNORE_TAGS>] [--dry-run]
```


Here is the explanation of each argument:

- `--harbor-url`: URL of the Harbor registry, including the protocol (e.g., `https://harbor.example.com`)
- `--username`: Username for the Harbor registry
- `--password`: Password for the Harbor registry
- `--project-name`: Name of the Harbor project
- `--repository-name` (optional): Name of the Harbor repository
- `--domain-name`: Domain name to match against image names
- `--ignore-tags` (optional): List of image tags to exclude from deletion
- `--dry-run` (optional): If provided, the script will not delete any images, just simulate the process

## Description

The script first collects the necessary arguments, and then retrieves a list of Docker images from the specified Harbor registry. The script filters out any images with tags that are specified to be ignored, and it can optionally restrict the operation to a specific repository.

The script determines which images to delete based on a set of rules defined in a cleanup policy, which is loaded from a separate file. The policy may specify certain tags to be saved (e.g., the latest 'n' tags for production and staging environments), and may specify a timeframe, such that only images older than a certain number of days are deleted.

The script can also handle kustomization files, which are used in Kubernetes for customizing application configuration. It finds all kustomization files in the current directory and its subdirectories and extracts any Docker images specified in these files.

If the `--dry-run` option is specified, the script will log the images that would be deleted, without actually deleting them.
