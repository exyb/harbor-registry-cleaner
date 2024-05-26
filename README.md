# Docker Image Cleanup Script

This Python script is designed to clean up Docker images from a Harbor registry, now only support harbor API version v2.

## Usage

The script can be run from the command line with several arguments:

```bash
python3 -m pip install -r requirements.txt
python3 src/main.py --harbor-url <HARBOR_URL> --username <USERNAME> --password <PASSWORD> --project-name <PROJECT_NAME> [--repository-name <REPOSITORY_NAME>] --domain-name <DOMAIN_NAME> [--ignore-tags <IGNORE_TAGS>] [--ignore-repos <IGNORE_REPOS>] [--dry-run]
```


Here is the explanation of each argument:

- `--harbor-url`: URL of the Harbor registry, including the protocol (e.g., `https://harbor.example.com`)
- `--username`: Username for the Harbor registry
- `--password`: Password for the Harbor registry
- `--project-name`: Name of the Harbor project
- `--repository-name` (optional): Name of the Harbor repository
- `--domain-name`: Domain name to match against image names
- `--ignore-tags` (optional): List of image tags to exclude from deletion
- `--ignore-repos` (optional): List of repos to exclude
- `--dry-run` (optional): If provided, the script will not delete any images, just simulate the process

## Description

The script first collects the necessary arguments, and then retrieves a list of Docker images from the specified Harbor registry. The script filters out any images with tags that are specified to be ignored, and it can optionally restrict the operation to a specific repository.

The script determines which images to delete based on a set of rules defined in a cleanup policy, which is loaded from a separate file. The policy may specify certain tags to be saved (e.g., the latest 'n' tags for production and staging environments), and may specify a timeframe, such that only images older than a certain number of days are deleted.

The script can also handle kustomization files, which are used in Kubernetes for customizing application configuration. It finds all kustomization files in the current directory and its subdirectories and extracts any Docker images specified in these files.

If the `--dry-run` option is specified, the script will log the images that would be deleted, without actually deleting them.

# Configurations

`Filename`: harbor_elcanup_policy.yaml

`type`:
- DeleteByTimeInName: filter by regexp, and sort by time string in tag name, e.g. 20240505, 20240506120000
- DeleteByTagName: filter by regexp, sort by name
- DeleteByCreateTimee: filter by regexp, sort by push time
- IgnoreRepos: ignore if repo name contains any string in the list
- IgnoreTags: ignore if tag name contains any string in the list

`Example`:

``` yaml
policies:
  - name: Policies for cleanup docker images
    rules:
      - type: DeleteByTimeInName
        regexp: '^master_.*'
        limit: 10
      - type: DeleteByTagName
        regexp: '^dev_.*'
        limit: 20
      - type: DeleteByTagName
        regexp: '^p0_.*'
        limit: 2
      - type: DeleteByTagName
        regexp: '^cqtel_.*'
        limit: 3
      - type: DeleteByTagName
        regexp: '^ctchq_.*'
        limit: 20
      - type: DeleteByCreateTime
        regexp: '.*'
        days: 45
      - type: IgnoreRepos
        repos:
          - "base"
      - type: IgnoreTags
        tags:
          - "lastest"
          - "2.0.0"
          - "1.0.0"
          - "1.5.0"
```

`Tips`:
  1. limit is set for each repo
  2. rules are merged and there will be no conflict
  3. ignore tags and repos are literal, not regexp
