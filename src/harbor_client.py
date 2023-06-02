import logging

import requests

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger('logger')


class HarborClient:
    HEADERS = {'Content-Type': 'application/json', 'accept': 'application/json'}

    def __init__(self, harbor_url, project_name, username, password, ssl_verify=False):
        self._harbor_url = harbor_url
        self._project_name = project_name
        self._username = username
        self._password = password
        self._verify = ssl_verify

    def _get_data_from_response(self, resp):
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"ERROR: Not found. {resp.status_code}")
            exit(1)

    def _get_response(self, url):
        responces = []
        first_page = requests.get(url, headers=HarborClient.HEADERS, auth=(self._username, self._password),
                                  verify=self._verify)
        responces += self._get_data_from_response(first_page)
        next_page = first_page
        while next_page.links.get('next', None) is not None:
            try:
                next_page_url = next_page.links['next']['url']
                next_page = requests.get(f'{self._harbor_url}/{next_page_url}', headers=HarborClient.HEADERS,
                                         auth=(self._username, self._password),
                                         verify=self._verify)
                responces += self._get_data_from_response(next_page)
            except KeyError:
                logger.info("No data")
                exit(1)

        return responces

    def _delete_image(self, url):
        response = requests.delete(url, headers=HarborClient.HEADERS,
                                   auth=(self._username, self._password), verify=self._verify)
        if response.status_code != 200:
            logger.error(f"ERROR: Not found. {response.status_code}")
            exit(1)
        else:
            logging.info("Image deleted successfully")

    def _get_images(self, artifacts, repo_name):
        list_images = []
        for artifact in artifacts:
            if artifact["tags"]:
                for tag in artifact["tags"]:
                    list_images.append({"name": repo_name, "tag": tag['name'], "push_time": tag["push_time"],
                                        "pull_time": tag["pull_time"]})

        return list_images

    def get_repositories(self):
        url = f'{self._harbor_url}/api/v2.0/projects/{self._project_name}/repositories'
        return self._get_response(url)

    def get_images(self, repository_name):
        rep_name_without_slash = repository_name.replace('/', '%2F')
        url = f'{self._harbor_url}/api/v2.0/projects/{self._project_name}/repositories/' \
              f'{rep_name_without_slash}/artifacts?with_tag=true'
        return self._get_images(self._get_response(url), f"{self._project_name}/{repository_name}")

    def delete_image(self, image):
        image_name, tag = image.split(':')
        rep_name_without_slash = image_name.replace(f'{self._project_name}/', '').replace('/', '%2F')
        url = f'{self._harbor_url}/api/v2.0/projects/{self._project_name}/repositories/{rep_name_without_slash}' \
              f'/artifacts/{tag}'
        self._delete_image(url)
