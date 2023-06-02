import pytest
from unittest.mock import MagicMock
from main import *


@pytest.fixture()
def mock_harbor_client():
    harbor_client = HarborClient('https://harbor.example.com', 'username', 'password', 'project-name',
                                 'repository-name')
    harbor_client.list_images = MagicMock(return_value=[{"name": "harbor.example.com/image1", "tag": "v1.0"},
                                                        {"name": "harbor.example.com/image1", "tag": "v1.1"},
                                                        {"name": "harbor.example.com/image1", "tag": "v1.2"},
                                                        {"name": "harbor.example.com/image2", "tag": "v1.0"},
                                                        {"name": "harbor.example.com/image2", "tag": "v1.1"}])
    harbor_client.get_image_manifest = MagicMock(return_value={"config": {"digest": "sha256:config_digest"}})
    harbor_client.get_image_labels = MagicMock(return_value={"key": "value"})
    return harbor_client


@pytest.fixture()
def mock_kustomization_yaml():
    kustomization_yaml = {"images": [{"name": "harbor.example.com/image1", "newTag": "v1.0"},
                                     {"name": "harbor.example.com/image2", "newName": "harbor.example.com/image2-new",
                                      "newTag": "v1.0"}]}
    return kustomization_yaml


def test_get_harbor_images(mock_kustomization_yaml):
    harbor_images = get_harbor_images(mock_kustomization_yaml, "harbor.example.com")
    assert len(harbor_images) == 2
    assert harbor_images[0] == {"name": "harbor.example.com/image1", "tag": "v1.0"}
    assert harbor_images[1] == {"name": "harbor.example.com/image2-new", "tag": "v1.0"}


def test_get_tags_by_exclusion():
    tags = ["v1.0", "v1.1", "v1.2", "v1.3"]
    exclusion = ["v1.1", "v1.2"]
    tags_after_exclusion = get_tags_by_exclusion(tags, exclusion)
    assert len(tags_after_exclusion) == 2
    assert "v1.0" in tags_after_exclusion
    assert "v1.3" in tags_after_exclusion


def test_sort_tag():
    assert sort_tag("v1.0.1") == [1, 0, 1]
    assert sort_tag("v2.1.0") == [2, 1, 0]
    assert sort_tag("v0.0.1") == [0, 0, 1]


def test_get_latest_n_tags():
    list_tags = ["v1.0", "v1.1", "v1.2", "v1.3"]
    limit = 2
    assert get_latest_n_tags(list_tags, limit) == ["v1.2", "v1.3"]


def test_get_harbor_images_by_domain():
    kustomization_yaml = {"images": [{"name": "harbor.example.com/image1", "newTag": "v1.0"},
                                     {"name": "harbor.example.com/image2", "newName": "docker.example.ru/image2-new",
                                      "newTag": "v1.1"}]}

    domain_name = "harbor.example.com"
    harbor_images = get_harbor_images(kustomization_yaml, domain_name)

    assert harbor_images == [{"name": "harbor.example.com/image1", "tag": "v1.0"}]


@pytest.mark.parametrize("list_tags,exp,limit,expected_output", [
    (["1.0.0", "2.0.1", "1.0.1", "2.0.0"], r"\d+\.\d+\.\d+", 2, ["2.0.0", "2.0.1"]),
    (["v1.0.0", "v2.0.0", "v2.0.1", "v1.0.1"], r"v\d+\.\d+\.\d+", 3, ["v1.0.1", "v2.0.0", "v2.0.1"]),
    (["v1.0.0-rc", "v2.0.0-rc", "v1.0.1-rc", "v2.0.1-rc"], r"^v\d+\.\d+\.\d+.+", 2, ["v2.0.0-rc", "v2.0.1-rc"]),
])
def test_get_latest_tags_by_regexp(list_tags, exp, limit, expected_output):
    output = get_latest_tags_by_regexp(list_tags, exp, limit)
    assert output == expected_output
    # assert sorted(output, key=sort_tag, reverse=True) == output
