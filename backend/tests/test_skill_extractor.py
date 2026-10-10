import pytest

from app.config import BACKEND_DIR
from app.services.skill_extractor import SkillExtractor


@pytest.fixture(scope="module")
def ex():
    return SkillExtractor.from_file(BACKEND_DIR / "config" / "skills.json")


def test_alias_normalization(ex):
    found = ex.extract_skills("Ran workloads on k8s and used sklearn, NLP and CI/CD daily.")
    assert {"Kubernetes", "scikit-learn", "Natural Language Processing", "CI/CD"} <= set(found)


def test_unique_results(ex):
    assert ex.extract_skills("Python python PYTHON python3").count("Python") == 1


def test_case_insensitive(ex):
    assert "Docker" in ex.extract_skills("DOCKER and docker-compose")


def test_java_not_in_javascript(ex):
    assert ex.extract_skills("Frontend work in JavaScript only") == ["JavaScript"]


def test_git_not_in_github_or_digital(ex):
    found = ex.extract_skills("Digital marketing, GitHub and GitLab users")
    assert "Git" not in found


def test_short_aliases_do_not_match_inside_words(ex):
    assert "Machine Learning" not in ex.extract_skills("html format, normal items, mlops culture")
    assert "Machine Learning" in ex.extract_skills("Experience in ML and AI")


def test_case_sensitive_ml_and_react(ex):
    assert "Machine Learning" not in ex.extract_skills("Added 500 ml of solution")
    assert "React" not in ex.extract_skills("We react quickly to incidents")
    assert "React" in ex.extract_skills("Built UIs with React and reactjs")


def test_nodejs_does_not_imply_javascript(ex):
    found = ex.extract_skills("Built services with Node.js")
    assert "Node.js" in found and "JavaScript" not in found


def test_cpp_and_special_characters(ex):
    assert "C++" in ex.extract_skills("Languages: C/C++, Rust")
    assert ex.extract_skills("Wrote C code") == []


def test_normalize_requirements_dedupes_and_maps_aliases(ex):
    assert ex.normalize_requirements(["python", "PYTHON3", "k8s", " Rust ", "rust"]) == ["Python", "Kubernetes", "Rust"]


def test_custom_skill_boundary_aware(ex):
    assert ex.contains_skill("Experienced with Rust and Go.", "Rust")
    assert not ex.contains_skill("A trustworthy person", "Rust")


def test_evidence_is_traceable_and_redacts_contacts(ex):
    text = "Summary\nBuilt APIs in Python. Email jane@example.com or call +1 415 555 0134 today\nOther"
    ev = ex.find_evidence(text, "Python")
    assert len(ev) == 1 and ev[0].line == 2
    assert "Built APIs in Python" in ev[0].snippet
    assert "jane@example.com" not in ev[0].snippet and "555" not in ev[0].snippet


def test_dictionary_metadata(ex):
    assert ex.dictionary.version and len(ex.dictionary.sha256) == 64
