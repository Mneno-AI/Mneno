from datetime import timedelta

from pytest import raises

from mneno import ContextBudget, ContextPackage, ContextPolicy, MemoryClient
from mneno.context import ContextPreset
from mneno.models import Memory, MemoryType, utc_now


def test_build_context_returns_context_package() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)

    context = client.build_context("What is the user building?", budget=50)

    assert isinstance(context, ContextPackage)
    assert context.query == "What is the user building?"
    assert context.included


def test_build_context_respects_token_budget_and_excludes_exhausted_items() -> None:
    client = MemoryClient()
    included = client.add("User builds Mneno.", importance=0.9)
    excluded = client.add("User also has a very long unrelated memory that cannot fit.", importance=0.8)

    context = client.build_context("User", budget=4)

    assert [item.memory_id for item in context.included] == [included.id]
    assert excluded.id in {item.memory_id for item in context.excluded}
    assert any(item.reason == "Excluded because budget exhausted" for item in context.excluded)
    assert context.stats.used_tokens <= context.stats.available_tokens


def test_build_context_includes_highest_scoring_memory_first() -> None:
    client = MemoryClient()
    weaker = client.add("The user mentioned a side note.", importance=0.1)
    stronger = client.add("The user is building Mneno, a Python memory SDK.", importance=0.9)

    context = client.build_context("What Python SDK is the user building?", budget=50)

    assert context.included[0].memory_id == stronger.id
    assert weaker.id in {item.memory_id for item in context.included}


def test_tight_budget_preserves_highest_relevance_evidence() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    expected = client.add("Python memory SDK.", importance=0.1)
    lower_value = client.add("Office chair inventory.", importance=1.0)

    context = client.build_context("Python memory SDK", budget=3)

    assert [item.memory_id for item in context.included] == [expected.id]
    excluded = next(item for item in context.excluded if item.memory_id == lower_value.id)
    assert excluded.reason == "Excluded because budget exhausted"


def test_duplicate_suppression_keeps_best_scored_duplicate() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    weaker = client.add("Python memory SDK.", importance=0.1)
    stronger = client.add("Python memory SDK.", importance=0.9)

    context = client.build_context("Python memory SDK", budget=20)

    assert [item.memory_id for item in context.included] == [stronger.id]
    excluded = next(item for item in context.excluded if item.memory_id == weaker.id)
    assert excluded.reason == "Excluded because duplicate content already included"


def test_context_explanation_includes_session_and_score_reasons() -> None:
    client = MemoryClient(auto_detect_conflicts=False)
    session = client.create_session(title="Current")
    memory = client.add("Python memory SDK.", session_id=session.id)

    context = client.build_context("Python memory SDK", budget=20, current_session_id=session.id)

    assert context.included[0].memory_id == memory.id
    assert "Session match boost applied for active session" in context.included[0].reason
    assert "Matched query term: memory" in context.included[0].reason


def test_build_context_supports_context_budget_object() -> None:
    client = MemoryClient()
    client.add("User prefers Python 3.11.", importance=0.8)
    budget = ContextBudget(max_tokens=20, reserve_tokens=5)

    context = client.build_context("What does the user prefer?", budget=budget)

    assert context.stats.max_tokens == 20
    assert context.stats.reserve_tokens == 5
    assert context.stats.available_tokens == 15


def test_build_context_supports_importance_strategy() -> None:
    client = MemoryClient()
    less_important = client.add("Mneno is a memory runtime.", importance=0.2)
    more_important = client.add("User prefers Python.", importance=0.95)
    budget = ContextBudget(max_tokens=50, strategy="importance")

    context = client.build_context("memory runtime", budget=budget)

    assert context.included[0].memory_id == more_important.id
    assert less_important.id in {item.memory_id for item in context.included}


def test_build_context_supports_recency_strategy() -> None:
    client = MemoryClient()
    old = Memory(
        content="Older memory about Mneno.",
        importance=0.9,
        updated_at=utc_now() - timedelta(days=10),
    )
    new = Memory(content="Newer memory about Mneno.", importance=0.1, updated_at=utc_now())
    client.store.add(old)
    client.store.add(new)
    budget = ContextBudget(max_tokens=50, strategy="recency")

    context = client.build_context("Mneno", budget=budget)

    assert context.included[0].memory_id == new.id


def test_build_context_avoids_duplicate_content() -> None:
    client = MemoryClient()
    first = client.add("User is building Mneno.", importance=0.9)
    duplicate = client.add("User is building Mneno.", importance=0.8)

    context = client.build_context("What is the user building?", budget=50)

    assert [item.content for item in context.included].count("User is building Mneno.") == 1
    assert {item.memory_id for item in context.included + context.excluded} == {first.id, duplicate.id}
    assert any(item.reason == "Excluded because duplicate content already included" for item in context.excluded)


def test_included_memories_increment_access_count_but_excluded_do_not() -> None:
    client = MemoryClient()
    included = client.add("User builds Mneno.", importance=0.9)
    excluded = client.add("User also has a very long unrelated memory that cannot fit.", importance=0.8)

    context = client.build_context("User", budget=4)

    assert included.id in {item.memory_id for item in context.included}
    assert excluded.id in {item.memory_id for item in context.excluded}
    included_after = client.get(included.id)
    excluded_after = client.get(excluded.id)
    assert included_after is not None
    assert excluded_after is not None
    assert included_after.access_count == 1
    assert included_after.last_accessed_at is not None
    assert excluded_after.access_count == 0
    assert excluded_after.last_accessed_at is None


def test_build_context_stats_are_correct() -> None:
    client = MemoryClient()
    client.add("User builds Mneno.", importance=0.9)
    client.add("User is building Mneno.", importance=0.8)

    context = client.build_context("User Mneno", budget=8)

    assert context.stats.max_tokens == 8
    assert context.stats.available_tokens == 8
    assert context.stats.used_tokens == sum(item.estimated_tokens for item in context.included)
    assert context.stats.remaining_tokens == context.stats.available_tokens - context.stats.used_tokens
    assert context.stats.included_count == len(context.included)
    assert context.stats.excluded_count == len(context.excluded)
    assert context.stats.total_candidates == 2


def test_context_text_contains_only_included_memories() -> None:
    client = MemoryClient()
    included = client.add("User builds Mneno.", importance=0.9)
    excluded = client.add("User also has a very long unrelated memory that cannot fit.", importance=0.8)

    context = client.build_context("User", budget=4)

    assert included.content in context.text
    assert excluded.content not in context.text


def test_empty_memory_store_returns_empty_context_package_safely() -> None:
    client = MemoryClient()

    context = client.build_context("Anything", budget=50)

    assert context.text == "Relevant memories:"
    assert context.included == []
    assert context.excluded == []
    assert context.stats.total_candidates == 0
    assert context.stats.used_tokens == 0


def test_build_context_excludes_score_below_threshold() -> None:
    client = MemoryClient()
    low_score = Memory(
        content="Old noisy note.",
        memory_type=MemoryType.EPISODIC,
        importance=0.0,
        created_at=utc_now() - timedelta(days=400),
        updated_at=utc_now() - timedelta(days=400),
    )
    client.store.add(low_score)

    context = client.build_context("unmatched query", budget=50)

    assert context.included == []
    assert context.excluded[0].memory_id == low_score.id
    assert "below min_score" in context.excluded[0].reason


def test_cheap_preset_creates_smaller_context_than_high_recall() -> None:
    client = MemoryClient()
    for index in range(8):
        client.add(f"Mneno memory detail {index}.", importance=0.8)

    cheap = client.build_context("Mneno memory", preset="cheap")
    high_recall = client.build_context("Mneno memory", preset="high_recall")

    assert cheap.stats.preset == "cheap"
    assert high_recall.stats.preset == "high_recall"
    assert len(cheap.included) == 5
    assert len(high_recall.included) == 8
    assert cheap.stats.used_tokens < high_recall.stats.used_tokens


def test_balanced_is_default_preset() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)

    context = client.build_context("Mneno")

    assert context.preset == "balanced"
    assert context.policy_name == "balanced"
    assert context.policy.max_tokens == 1200
    assert context.stats.reserve_tokens == 200


def test_invalid_preset_raises_value_error() -> None:
    client = MemoryClient()

    with raises(ValueError, match="Unknown context preset"):
        client.build_context("Mneno", preset="invalid")


def test_explicit_policy_overrides_preset() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)
    policy = ContextPolicy(max_tokens=800, reserve_tokens=100, strategy="importance", min_score=0.25)

    context = client.build_context("Mneno", preset="cheap", policy=policy)

    assert context.preset is None
    assert context.policy_name == "custom"
    assert context.policy.max_tokens == 800
    assert context.policy.strategy == "importance"
    assert context.stats.min_score == 0.25


def test_budget_int_remains_backward_compatible() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)

    context = client.build_context("Mneno", budget=50)

    assert context.policy_name == "budget"
    assert context.preset is None
    assert context.stats.max_tokens == 50
    assert context.stats.reserve_tokens == 0


def test_preset_none_uses_balanced_fallback() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)

    context = client.build_context("Mneno", preset=None)

    assert context.policy_name == "balanced"
    assert context.preset == "balanced"


def test_context_budget_remains_backward_compatible() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)
    budget = ContextBudget(max_tokens=60, reserve_tokens=10, strategy="recency")

    context = client.build_context("Mneno", budget=budget)

    assert context.policy_name == "budget"
    assert context.stats.max_tokens == 60
    assert context.stats.reserve_tokens == 10
    assert context.stats.strategy == "recency"


def test_context_policy_min_score_filters_low_score_memories() -> None:
    client = MemoryClient()
    client.add("Weak unrelated note.", importance=0.1)
    policy = ContextPolicy(max_tokens=100, min_score=0.95)

    context = client.build_context("Mneno", policy=policy)

    assert context.included == []
    assert context.excluded
    assert "below min_score" in context.excluded[0].reason


def test_preserve_memory_types_can_include_operational_memory_below_min_score() -> None:
    client = MemoryClient()
    operational = Memory(
        content="Current task state should remain visible.",
        memory_type=MemoryType.OPERATIONAL,
        importance=0.0,
        created_at=utc_now() - timedelta(days=400),
        updated_at=utc_now() - timedelta(days=400),
    )
    client.store.add(operational)
    policy = ContextPolicy(max_tokens=100, min_score=0.95, preserve_memory_types=[MemoryType.OPERATIONAL])

    context = client.build_context("Mneno", policy=policy)

    assert [item.memory_id for item in context.included] == [operational.id]
    assert "preserved memory type 'operational'" in context.included[0].reason


def test_preserve_tags_can_include_tagged_memory_below_min_score() -> None:
    client = MemoryClient()
    tagged = Memory(
        content="Pinned project context.",
        importance=0.0,
        tags=["Pinned"],
        created_at=utc_now() - timedelta(days=400),
        updated_at=utc_now() - timedelta(days=400),
    )
    client.store.add(tagged)
    policy = ContextPolicy(max_tokens=100, min_score=0.95, preserve_tags=["pinned"])

    context = client.build_context("Mneno", policy=policy)

    assert [item.memory_id for item in context.included] == [tagged.id]
    assert "preserved tag 'pinned'" in context.included[0].reason


def test_context_policy_max_items_is_respected() -> None:
    client = MemoryClient()
    first = client.add("Mneno first memory.", importance=0.9)
    second = client.add("Mneno second memory.", importance=0.8)
    policy = ContextPolicy(max_tokens=100, max_items=1)

    context = client.build_context("Mneno", policy=policy)

    assert len(context.included) == 1
    assert context.included[0].memory_id in {first.id, second.id}
    assert any(item.reason == "Excluded because max_items reached" for item in context.excluded)


def test_context_exclusion_reasons_are_clear() -> None:
    client = MemoryClient()
    client.add("Mneno duplicate memory.", importance=0.9)
    client.add("Mneno duplicate memory.", importance=0.8)
    client.add("Mneno extra memory.", importance=0.7)
    policy = ContextPolicy(max_tokens=100, max_items=1)

    context = client.build_context("Mneno", policy=policy, limit=2)
    reasons = {item.reason for item in context.excluded}

    assert "Excluded because duplicate content already included" in reasons
    assert "Excluded because not selected by policy" in reasons


def test_context_stats_include_policy_metadata() -> None:
    client = MemoryClient()
    client.add("User is building Mneno.", importance=0.9)
    policy = ContextPolicy(max_tokens=80, reserve_tokens=10, strategy="importance", min_score=0.2, max_items=3)

    context = client.build_context("Mneno", policy=policy)

    assert context.stats.policy_name == "custom"
    assert context.stats.preset is None
    assert context.stats.min_score == 0.2
    assert context.stats.max_items == 3
    assert context.stats.strategy == "importance"
    assert context.stats.candidate_count_before_filter == 1
    assert context.stats.candidate_count_after_filter == 1


def test_policy_access_count_increments_only_for_included_items() -> None:
    client = MemoryClient()
    included = client.add("Mneno short memory.", importance=0.9)
    excluded = client.add("Mneno long memory that cannot fit within tiny context budget.", importance=0.8)
    policy = ContextPolicy(max_tokens=3)

    context = client.build_context("Mneno", policy=policy)

    assert included.id in {item.memory_id for item in context.included}
    assert excluded.id in {item.memory_id for item in context.excluded}
    included_after = client.get(included.id)
    excluded_after = client.get(excluded.id)
    assert included_after is not None
    assert excluded_after is not None
    assert included_after.access_count == 1
    assert excluded_after.access_count == 0


def test_agent_state_preset_preserves_operational_and_preference_memories() -> None:
    client = MemoryClient()
    operational = client.add("Current goal: finish Step 5.", memory_type="operational", importance=0.0)
    preference = client.add("User prefers Python-first APIs.", memory_type="preference", importance=0.0)

    context = client.build_context("unmatched", preset=ContextPreset.AGENT_STATE)

    assert {item.memory_id for item in context.included} == {operational.id, preference.id}
    assert context.policy.preserve_memory_types == [MemoryType.OPERATIONAL, MemoryType.PREFERENCE]
