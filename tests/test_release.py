from scripts.check_release import package_version, project_version, validate


def test_versions_match() -> None:
    project = project_version()
    assert project == package_version()
    assert validate(f"v{project}") == project
