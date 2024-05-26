import argparse
import logging
import os
import re
from datetime import datetime, timedelta
from pprint import pformat

import requests
import yaml
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from config import load_cleanup_policy, validate_policy, merge_policies, get_field_from_rule
from harbor_client import HarborClient
from utils import regexp_match, extract_semver

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger('logger')

date_regexp = re.compile(r'\d{8}|\d{12}|\d{14}')

def combined_list(value):
    items = value.replace(',', ' ').split()
    return [item for item in items if item]


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Delete Docker images from a Harbor registry.')
    parser.add_argument('--harbor-url', required=True,
                        help='URL of the Harbor registry, including protocol (e.g. https://harbor.example.com)')
    parser.add_argument('--username', required=True, help='Username for the Harbor registry')
    parser.add_argument('--password', required=True, help='Password for the Harbor registry')
    parser.add_argument('--project-name', required=True, help='Name of the Harbor project')
    parser.add_argument('--repository-name', default=None, help='Name of the Harbor repository')
    parser.add_argument('--domain-name', default='registry.ru', required=True,
                        help='Domain name to match against image names')
    parser.add_argument('--ignore-tags', type=combined_list, nargs='*', default=[], help='List of image tags to exclude from deletion')
    parser.add_argument('--ignore-repos', type=combined_list, nargs='*', default=[], help='List of image repos to exclude from deletion')
    parser.add_argument('--dry-run', action='store_true', help='Do a dry run (don\'t actually delete any images)')
    return parser.parse_args()


def get_kustomization_files():
    """Get all kustomization files in the current directory and its subdirectories."""
    kustomization_files = []
    regex = re.compile('(kustomization.*)')
    for root, dirs, files in os.walk('.'):
        for file in files:
            if regex.match(file):
                kustomization_files.append(os.path.join(root, file))
    return kustomization_files


def get_harbor_images(kustomization_yaml, domain_name):
    """Extract harbor images from kustomization yaml file."""
    images = kustomization_yaml.get('images', [])
    harbor_images = []
    for image in images:
        if 'name' not in image and 'newName' not in image:
            logger.error(f"ERROR: Not found 'name' in images section. {images}")
            exit(1)
        if 'newName' in image:
            if image['newName'].split('/')[0] == domain_name:
                harbor_images.append({"name": f"{image['newName']}", "tag": f"{image['newTag']}"})
        elif image['name'].split('/')[0] == domain_name:
            harbor_images.append({"name": f"{image['name']}", "tag": f"{image['newTag']}"})

    return harbor_images


def get_tags_by_tag_exclusion(tags: list, rule ) -> list:
    """Return tags that are not in the exclusion list."""
    exclusions = rule['tags']
    ignored_list =[]
    for exclusion in exclusions:
        if exclusion in tags:
            ignored_list += [tag for tag in tags if exclusion in tag]
    return ignored_list


def sort_tag(tag) -> list:
    """Sort tags by semantic versioning."""
    semver = extract_semver(tag)
    version_parts = semver.split('_')
    return [int(part) for part in version_parts if part.isdigit()]
    # return list(map(int, semver.split('_')))


def get_latest_n_tags(reverse_sorted_tag_list, limit):
    """Return the latest n tags."""
    if limit == 0 or len(reverse_sorted_tag_list) <= limit:
        return []
    else:
        return reverse_sorted_tag_list[limit:]
    return reverse_sorted_tag_list

def extract_date(s):
    match = date_regexp.search(s)
    if match:
        date_str = match.group()
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d')
        elif len(date_str) == 12:
            return datetime.strptime(date_str, '%Y%m%d%H%M')
        elif len(date_str) == 14:
            return datetime.strptime(date_str, '%Y%m%d%H%M%S')
    return None

def get_delete_tags_by_time_in_name(list_tags: list, rule) -> list:
    """Return the latest tags that match the given regular expression."""
    exp = rule['regexp']
    limit = rule['limit']

    # filter by regexp
    matched_tags = [tag for tag in list_tags if regexp_match(exp, tag)]
    if matched_tags:
        # sort by pattern if time pattern found
        reverse_sorted_tag_list = sorted(matched_tags, key=lambda x: extract_date(x), reverse=True)

        return get_latest_n_tags(reverse_sorted_tag_list, limit)
    return []

def get_delete_tags_by_name_regexp(list_tags: list, rule) -> list:
    """Return the latest tags that match the given regular expression."""
    exp = rule['regexp']
    limit = rule['limit']

    # filter by regexp
    matched_tags = [tag for tag in list_tags if regexp_match(exp, tag)]
    if matched_tags:
        # sort by name
        reverse_sorted_tag_list = sorted(matched_tags, reverse=True)
        return get_latest_n_tags(reverse_sorted_tag_list, limit)
    return []

def get_delete_tags_by_create_time(list_harbor_images, rule):
    """Return feature tags younger than n days."""
    delete_docker_images_older_than = rule['days']
    exp = rule['regexp']
    matched_images = [image for image in list_harbor_images if regexp_match(exp, image['tag'])]
    if not matched_images:
        return []

    now = datetime.utcnow()
    last_n_days = now - timedelta(days=delete_docker_images_older_than)
    sorted_list = sorted(matched_images, key=lambda x: x['push_time'], reverse=True)
    images_younger_than_n_days = [x for x in sorted_list
                    if datetime.fromisoformat(x['push_time'].replace('Z', '')) < last_n_days]
    return [image["tag"] for image in images_younger_than_n_days]


def delete_images(harbor_client, list_images_to_delete, dry_run=None):
    """Delete specified images from the Harbor registry."""
    logger.info("#" * 10 + " Docker images to remove " + "#" * 10)
    for image in list_images_to_delete:
        if dry_run:
            logger.info(f"DRY RUN: Deleting image {image}")
        else:
            logger.info(f"Deleting image {image}")
            harbor_client.delete_image(image)


def get_tags_to_delete(repository, list_harbor_images, kustomization_yaml_images, args, policy):
    """Process images in a repository."""
    list_harbor_tags = [image["tag"] for image in list_harbor_images]
    list_kustomization_yaml_tags = [image["tag"] for image in kustomization_yaml_images if
                                    image["name"] == f"{args.domain_name}/{repository['name']}"]
    # logger.info(f"List of all tags: {list_harbor_tags}")
    # logger.info(f"List of tags to save from kustomization yaml files: {list_kustomization_yaml_tags}")

    tags_to_remove = []

    # ignore repos
    for rule in policy['rules']:
        if 'IgnoreRepos' in rule['type']:
            ignore_repos = rule['repos']
            for ignore_repo in ignore_repos:
                if ignore_repo in repository['name']:
                    logger.info(f"Repository {repository['name']} ignored.")
                    return []

    for rule in policy['rules']:
        tags_to_delete_for_rule = []
        if 'name' not in rule:
            if rule['type'] not in ['IgnoreTags', 'IgnoreRepos']:
                rule['name'] = rule['type'] + '-' + rule['regexp']
            else:
                rule['name'] = rule['type']

        if rule['type'] == 'DeleteByTimeInName':
            tags_to_delete = get_delete_tags_by_time_in_name(list_harbor_tags, rule)
            tags_to_delete_for_rule += set(tags_to_delete)

        elif rule['type'] == 'DeleteByTagName':
            tags_to_delete = get_delete_tags_by_name_regexp(list_harbor_tags, rule)
            tags_to_delete_for_rule += set(tags_to_delete)

        elif rule['type'] == 'DeleteByCreateTime':
            tags_to_delete = get_delete_tags_by_create_time(list_harbor_images, rule)
            tags_to_delete_for_rule += set(tags_to_delete)
        else:
            continue

        logger.info(f"List of tags to delete for rule - {rule['name']}: {tags_to_delete_for_rule}")
        tags_to_remove += tags_to_delete_for_rule

    for rule in policy['rules']:
        if rule['type'] == 'IgnoreTags':
            tags_ignored = get_tags_by_tag_exclusion(tags_to_remove, rule)
            logger.info(f"List of tags to ignore for rule - {rule['name']}: {tags_ignored}")
            tags_to_remove = [item for item in tags_to_remove if item not in tags_ignored]
        else:
            continue

    tags_to_remove = list(set(tags_to_remove))

    logging.info(f"List of tags in repo {repository['name']} to remove for policy {policy['name']}: {tags_to_remove}\n")
    return tags_to_remove


if __name__ == '__main__':
    args = parse_args()
    if args.ignore_repos:
        args.ignore_repos = [tag for sublist in args.ignore_repos for tag in sublist]
    if args.ignore_tags:
        args.ignore_tags = [tag for sublist in args.ignore_tags for tag in sublist]

    cleanup_policy = load_cleanup_policy()

    for policy in merge_policies(cleanup_policy, args):
        try:
            validate_policy(policy)
        except ValueError as e:
            logger.error(f"Error in policy '{policy['name']}': {str(e)}")
            exit(1)

        logger.info(f"========== Process with policy '{policy['name']} start ========== \n")
        logger.info(f"Rules:\n{pformat(policy)}\n")

        kustomization_files = get_kustomization_files()
        kustomization_yaml_images = []
        for kustomization_file in kustomization_files:
            with open(kustomization_file, 'r') as f:
                kustomization_yaml = yaml.safe_load(f)
                kustomization_yaml_images += get_harbor_images(kustomization_yaml, args.domain_name)

        logger.info(
            f"List of images from kustomization.yaml files:\n" + "\n".join(map(str, kustomization_yaml_images)) + "\n")

        harbor_client = HarborClient(harbor_url=args.harbor_url, project_name=args.project_name, username=args.username, password=args.password)


        repositories = harbor_client.get_repositories()
        repositories_names = [repository_["name"] for repository_ in repositories]

        list_images_to_delete = []
        for repository in repositories:
            logger.info(f"========> policy: {policy['name']}, repository: {repository['name']} start <========")
            if args.repository_name and f'{args.project_name}/{args.repository_name}' not in repositories_names:
                logger.error(
                    f"The repository_name - '{args.repository_name}' not found. "
                    f"List of repositories names - {repositories_names}")
                exit(1)

            repository_name = repository["name"].replace(f'{args.project_name}/', '')
            if args.repository_name and args.repository_name != repository_name:
                continue
            list_harbor_images = harbor_client.get_images(repository_name)

            logger.info(
               f"List of images from harbor for repo name "
               f"{repository['name']}:\n" + "\n".join(map(str, list_harbor_images)) + "\n")


            list_tags_to_delete = get_tags_to_delete(repository, list_harbor_images, kustomization_yaml_images, args, policy)

            list_images_to_delete += [f"{repository['name']}:{tag}" for tag in list_tags_to_delete]
            logger.info(f"========> policy: {policy['name']}, repository: {repository['name']} end <========\n")

        delete_images(harbor_client, list_images_to_delete, args.dry_run)
        logger.info(f"========== Process with policy '{policy['name']} complete ========== \n")
