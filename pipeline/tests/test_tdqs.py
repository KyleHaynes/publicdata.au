import copy
import json

from publicdata import tdqs


def test_scores_round_half_up_in_integers_as_the_rubric_does():
    dims = dict(zip(tdqs.WEIGHTS, (4, 2, 2, 3, 4, 2), strict=True))
    assert tdqs.tool_score(dims) == 2.9
    assert tdqs.round1(345, 100) == 3.5
    coh = dict.fromkeys(tdqs.COHERENCE, 5) | {"completeness": 4}
    s = tdqs.server_scores([4.9, 4.8, 4.4], coh)
    # 0.6 x 4.7 + 0.4 x 4.4 = 4.58; the coherence mean 4.75 rounds up.
    assert s == {"description_quality": 4.6, "coherence": 4.8, "overall": 4.7}


def test_the_hash_moves_with_the_definition_and_nothing_else():
    t = tdqs.tools()[0]
    h = tdqs.definition_hash(t)
    assert h == tdqs.definition_hash(json.loads(json.dumps(t)))
    assert h != tdqs.definition_hash({**t, "description": t["description"] + " More."})
    assert len(h) == 16


def test_invocation_cost_follows_the_worked_example():
    leaf = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    union = {
        "oneOf": [leaf, {"type": "object", "properties": {}}, {"type": "object", "properties": {}}]
    }
    inner = {
        "type": "object",
        "properties": {"a": {}, "b": {}, "u": union},
        "required": ["a", "b", "u"],
    }
    tool = {"inputSchema": {"type": "object", "properties": {"q": inner}, "required": ["q"]}}
    assert tdqs.invocation_cost(tool) == (13, 5, 3, 2)
    flat = {"inputSchema": {"type": "object", "properties": {"a": {}, "b": {}}, "required": ["a"]}}
    assert tdqs.invocation_cost(flat) == (1, 1, 1, 0)
    nullable = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert tdqs._union(nullable) is None


def _store(ts, tool=5, coherence=5):
    dims = dict.fromkeys(tdqs.WEIGHTS, tool)
    run = {"scores": dims, "why": {}, "summary": "", "contradiction": False}
    cdims = dict.fromkeys(tdqs.COHERENCE, coherence)
    return {
        "rubric": tdqs.rubric_id(),
        "tools": {
            tdqs.definition_hash(t): {
                "name": t["name"],
                "tdqs": tdqs.tool_score(dims),
                "median": dims,
                "runs": [run] * 3,
            }
            for t in ts
        },
        "server": {
            "hash": tdqs.set_hash(ts),
            "median": cdims,
            "runs": [{"scores": cdims, "why": {}, "summary": ""}] * 3,
        },
    }


def test_check_passes_a_scored_set_and_fails_a_changed_tool_a_low_score_a_contradiction_or_another_rubric():
    ts = tdqs.tools()
    store = _store(ts)
    errors, report = tdqs.problems(ts, store)
    assert errors == [] and report[-1].startswith("server             5.0")

    changed = [{**ts[0], "description": "Search."}, *ts[1:]]
    errors = tdqs.problems(changed, store)[0]
    assert any("definition changed" in e for e in errors)
    assert any("tool set changed" in e for e in errors)

    low = copy.deepcopy(store)
    s = low["tools"][tdqs.definition_hash(ts[0])]
    s["tdqs"] = 4.6
    s["runs"][0] = {**s["runs"][0], "contradiction": True}
    errors = tdqs.problems(ts, low)[0]
    assert any(f"{ts[0]['name']}: TDQS 4.6 is under" in e for e in errors)
    assert any("contradicts the annotations" in e for e in errors)

    assert any("server: overall" in e for e in tdqs.problems(ts, _store(ts, coherence=3))[0])
    other = {**store, "rubric": "0/other/3"}
    assert "was scored under 0/other/3" in tdqs.problems(ts, other)[0][0]


def test_the_judge_is_sent_the_rubric_message_shape():
    t = tdqs.tools()[0]
    m = tdqs.tool_message(t, ["b", "c"])
    assert m.startswith(f'TOOL NAME: {t["name"]}\nTITLE: {t["title"]}\n\nDESCRIPTION:\n"')
    assert (
        "- Schema description coverage: 100%" in m
        and "<sibling-tools>\nb\nc\n</sibling-tools>" in m
    )
    assert m.endswith("Respond with JSON only.")
    s = tdqs.server_message("publicdata-au", tdqs.tools())
    assert s.startswith(
        f"SERVER NAME: publicdata-au\nTOOL COUNT: {len(tdqs.tools())}\n\n<tools>\n- "
    )
