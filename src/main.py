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
    parser.add_argument('--ignore-tags', default=[], help='List of image tags to exclude from deletion')
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


def get_tags_by_exclusion(tags: list, exclusion: list) -> list:
    """Return tags that are not in the exclusion list."""
    return [tag for tag in tags if tag not in exclusion]


def sort_tag(tag) -> list:
    """Sort tags by semantic versioning."""
    semver = extract_semver(tag)
    return list(map(int, semver.split('.')))


def get_latest_n_tags(list_tags, limit):
    """Return the latest n tags."""
    if limit == 0:
        return []
    if len(list_tags) > limit:
        return list_tags[-limit:]
    return list_tags


def get_latest_tags_by_regexp(list_tags: list, exp: str, limit: int) -> list:
    """Return the latest tags that match the given regular expression."""
    semver_images = [tag for tag in list_tags if regexp_match(exp, tag)]
    sorted_tag_list = sorted(semver_images, key=sort_tag)
    return get_latest_n_tags(sorted_tag_list, limit)


def get_feature_tags_younger_than_n_days(list_harbor_images, list_tags_to_remove, prod_regexp, staging_regexp,
                                         delete_docker_images_older_than):
    """Return feature tags younger than n days."""
    now = datetime.utcnow()
    last_n_days = now - timedelta(days=delete_docker_images_older_than)
    sorted_lst = sorted(list_harbor_images, key=lambda x: x['push_time'])
    images_younger_than_n_days = [x for x in sorted_lst if datetime.fromisoformat(
        x['push_time'].replace('Z', '')) >= last_n_days and not re.search(
        prod_regexp, str(x['tag'])) and not re.search(staging_regexp, str(x['tag']))]
    return [image["tag"] for image in images_younger_than_n_days if image["tag"] in list_tags_to_remove]


def delete_images(harbor_client, list_images_to_delete, dry_run=None):
    """Delete specified images from the Harbor registry."""
    logger.info("#" * 10 + " Docker images to remove " + "#" * 10)
    for image in list_images_to_delete:
        if dry_run:
            logger.info(f"DRY RUN: Deleting image {image}")
        else:
            logger.info(f"Deleting image {image}")
            # harbor_client.delete_image(image)


def get_tags_to_delete(repository, list_harbor_images, kustomization_yaml_images, args, policy):
    """Process images in a repository."""
    list_harbor_tags = [image["tag"] for image in list_harbor_images]
    list_kustomization_yaml_tags = [image["tag"] for image in kustomization_yaml_images if
                                    image["name"] == f"{args.domain_name}/{repository['name']}"]
    logger.info("#" * 45)
    logger.info(f"List of all tags: {list_harbor_tags}")
    logger.info(f"List of tags to save from kustomization yaml files: {list_kustomization_yaml_tags}")

    prod_tags = get_latest_tags_by_regexp(list_harbor_tags, get_field_from_rule(policy, 'SaveLastNProdTags', 'regexp'),
                                          get_field_from_rule(policy, 'SaveLastNProdTags', 'limit'))
    logger.info(f"List of prod tags to save: {prod_tags}")
    staging_tags = get_latest_tags_by_regexp(list_harbor_tags,
                                             get_field_from_rule(policy, 'SaveLastNStagingTags', 'regexp'),
                                             get_field_from_rule(policy, 'SaveLastNStagingTags', 'limit'))
    logger.info(f"List of staging tags to save: {staging_tags}")
    tags_to_remove = set(list_harbor_tags) - set(prod_tags) - set(staging_tags) - set(list_kustomization_yaml_tags)
    ignore_tags = get_field_from_rule(policy, 'IgnoreTags', 'tags')
    exclude_tags = ['develop', 'latest', 'master', 'main'] + ignore_tags
    logger.info(f"List of exclude tags: {exclude_tags}")
    list_tags_to_remove = get_tags_by_exclusion(list(tags_to_remove), exclude_tags)

    list_feature_tags_younger_than_n_days = get_feature_tags_younger_than_n_days(list_harbor_images,
                                                                                 list_tags_to_remove,
                                                                                 get_field_from_rule(
                                                                                     policy,
                                                                                     'SaveLastNProdTags',
                                                                                     'regexp'),
                                                                                 get_field_from_rule(
                                                                                     policy,
                                                                                     'SaveLastNStagingTags',
                                                                                     'regexp'),
                                                                                 get_field_from_rule(
                                                                                     policy,
                                                                                     'DeleteOlderThan',
                                                                                     'days'))
    logger.info(
        f"List of tags younger than {get_field_from_rule(policy, 'DeleteOlderThan', 'days')} "
        f"days to save: {list_feature_tags_younger_than_n_days}")

    list_tags_to_remove = list(set(list_tags_to_remove) - set(list_feature_tags_younger_than_n_days))

    list_n_last_tags = get_latest_n_tags(list_tags_to_remove,
                                         get_field_from_rule(policy, 'SaveLastNFeatureTags', 'limit'))
    logger.info(
        f"List of {get_field_from_rule(policy, 'SaveLastNFeatureTags', 'limit')} last tags to save: {list_n_last_tags}")

    list_tags_to_remove = list(set(list_tags_to_remove) - set(list_n_last_tags))
    logging.info(f"List of tags to remove: {list_tags_to_remove}\n")
    return list_tags_to_remove


if __name__ == '__main__':
    args = parse_args()

    cleanup_policy = load_cleanup_policy()
    for policy in cleanup_policy:
        try:
            validate_policy(policy)
        except ValueError as e:
            logger.error(f"Error in policy '{policy['name']}': {str(e)}")
            exit(1)

    policy = merge_policies(cleanup_policy)
    logger.info(f"Rules:\n{pformat(policy)}\n")

    kustomization_files = get_kustomization_files()
    kustomization_yaml_images = []
    for kustomization_file in kustomization_files:
        with open(kustomization_file, 'r') as f:
            kustomization_yaml = yaml.safe_load(f)
            kustomization_yaml_images += get_harbor_images(kustomization_yaml, args.domain_name)

    logger.info(
        f"List of images from kustomization.yaml files:\n" + "\n".join(map(str, kustomization_yaml_images)) + "\n")

    harbor_client = HarborClient(harbor_url=args.harbor_url, project_name=args.project_name, username=args.username,
                                 password=args.password)

    repositories = harbor_client.get_repositories()
    repositories_names = [repository_["name"] for repository_ in repositories]

    list_images_to_delete = []
    for repository in repositories:
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

        list_tags_to_delete = get_tags_to_delete(repository, list_harbor_images, kustomization_yaml_images, args,
                                                 policy)
        list_images_to_delete += [f"{repository['name']}:{tag}" for tag in list_tags_to_delete]

    delete_images(harbor_client, list_images_to_delete, args.dry_run)
