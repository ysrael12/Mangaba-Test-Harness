"""
Integration — Crew orchestration (L6), sequential process, with mock LLMs.
"""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.integration


def _guard():
    if not compat.require("Crew", "Process", "Agent", "Task"):
        pytest.skip(compat.missing("Crew", "Process", "Agent", "Task"))


def _agent(client, role):
    return compat.Agent(
        role=role,
        goal=f"Perform the {role} duty",
        backstory="Deterministic test agent.",
        llm=client,
    )


def test_sequential_crew_returns_final_output(mock_client):
    _guard()
    researcher = _agent(mock_client(default_text="research done"), "Researcher")
    writer = _agent(mock_client(default_text="final report"), "Writer")

    t1 = compat.Task(
        description="Research the topic {topic}",
        expected_output="notes",
        agent=researcher,
    )
    t2 = compat.Task(
        description="Write a report",
        expected_output="report",
        agent=writer,
        context=[t1],
    )

    crew = compat.Crew(agents=[researcher, writer], tasks=[t1, t2], process=compat.Process.SEQUENTIAL)
    output = crew.kickoff(inputs={"topic": "AI"})
    assert str(output.final_output) == "final report"


def test_crew_requires_agents(mock_client):
    _guard()
    if compat.CrewError is None:
        pytest.skip(compat.missing("CrewError"))
    a = _agent(mock_client(), "Solo")
    t = compat.Task(description="do x", expected_output="y", agent=a)
    with pytest.raises(compat.CrewError):
        compat.Crew(agents=[], tasks=[t])
