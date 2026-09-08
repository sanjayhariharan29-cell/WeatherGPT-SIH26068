"""Memory Quality Benchmarking and Evaluation Framework for WeatherGPT.

Implements multi-turn benchmark scenarios and calculates:
1. Context resolution accuracy
2. Location inheritance accuracy
3. Temporal inheritance accuracy
4. Reference resolution accuracy
5. Ambiguity detection accuracy
6. Language continuity accuracy
Aligned with Phase 10 & Phase 13 specifications.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from ai.memory.manager import ConversationMemoryManager
from ai.memory.resolver import ContextResolver
from ai.memory.models import ConversationTurn


class MemoryBenchmarkScenario(BaseModel):
    """Defines a multi-turn conversational benchmark scenario."""
    scenario_id: str
    description: str
    turns: List[Dict[str, Any]]
    expected_final_location: str
    expected_final_date: Optional[str] = None
    expected_final_time: Optional[str] = None
    expected_final_topic: Optional[str] = None
    expected_final_persona: Optional[str] = None
    expected_final_language: Optional[str] = None
    expected_ambiguity: bool = False


# Curated Multi-Turn Evaluation Benchmark Dataset
MEMORY_EVALUATION_DATASET: List[MemoryBenchmarkScenario] = [
    MemoryBenchmarkScenario(
        scenario_id="eval_01_temporal_inheritance",
        description="Inheriting date 'tomorrow' when follow-up specifies only time-of-day 'evening'",
        turns=[
            {"user": "Will it rain tomorrow in Coimbatore?", "role": "user", "location": "Coimbatore", "date": "tomorrow"},
            {"assistant": "Light rain expected tomorrow in Coimbatore.", "role": "assistant"},
            {"user": "What about evening?", "role": "user"}
        ],
        expected_final_location="Coimbatore",
        expected_final_date="tomorrow",
        expected_final_time="evening",
        expected_final_topic="rain"
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_02_pronoun_reference_there",
        description="Resolving pronoun 'there' back to previously mentioned location 'Chennai'",
        turns=[
            {"user": "What is the weather in Chennai?", "role": "user", "location": "Chennai"},
            {"assistant": "It is currently 32°C and humid in Chennai.", "role": "assistant"},
            {"user": "Will it rain there tomorrow?", "role": "user"}
        ],
        expected_final_location="Chennai",
        expected_final_date="tomorrow",
        expected_final_topic="rain"
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_03_language_continuity_tamil",
        description="Maintaining Tamil language preference across short follow-up turns",
        turns=[
            {"user": "கோயம்புத்தூரில் நாளை மழை வருமா?", "role": "user", "language": "ta", "location": "Coimbatore"},
            {"assistant": "நாளை கோயம்புத்தூரில் மிதமான மழை பெய்ய வாய்ப்புள்ளது.", "role": "assistant", "language": "ta"},
            {"user": "மாலையில் எப்படி?", "role": "user"}
        ],
        expected_final_location="Coimbatore",
        expected_final_time="evening",
        expected_final_language="ta"
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_04_topic_continuation_wind",
        description="Maintaining location/temporal context while switching topic from rain to wind",
        turns=[
            {"user": "Rain forecast for tomorrow in Coimbatore?", "role": "user", "location": "Coimbatore", "date": "tomorrow", "topic": "rain"},
            {"assistant": "Scattered showers likely tomorrow.", "role": "assistant"},
            {"user": "What about the wind?", "role": "user"}
        ],
        expected_final_location="Coimbatore",
        expected_final_date="tomorrow",
        expected_final_topic="wind"
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_05_explicit_location_override",
        description="Explicitly mentioned new location 'Madurai' overrides previous location 'Coimbatore'",
        turns=[
            {"user": "Is it hot in Coimbatore today?", "role": "user", "location": "Coimbatore"},
            {"assistant": "Temperature is 31°C in Coimbatore.", "role": "assistant"},
            {"user": "How about in Madurai?", "role": "user"}
        ],
        expected_final_location="Madurai"
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_06_multiple_location_ambiguity",
        description="Detecting ambiguity when 'there' is used after discussing both Coimbatore and Chennai",
        turns=[
            {"user": "Compare weather between Coimbatore and Chennai", "role": "user", "location": "Coimbatore", "secondary_location": "Chennai"},
            {"assistant": "Coimbatore is 28°C while Chennai is 33°C.", "role": "assistant"},
            {"user": "Will it rain there tomorrow?", "role": "user"}
        ],
        expected_final_location="Chennai",
        expected_ambiguity=True
    ),
    MemoryBenchmarkScenario(
        scenario_id="eval_07_persona_persistence_farmer",
        description="Persisting farmer persona across multi-turn advisory interaction",
        turns=[
            {"user": "I am a farmer in Coimbatore, will it rain tomorrow?", "role": "user", "location": "Coimbatore", "persona": "farmer", "date": "tomorrow"},
            {"assistant": "Agricultural alert: Light rain expected tomorrow.", "role": "assistant"},
            {"user": "Should I spray pesticide then?", "role": "user"}
        ],
        expected_final_location="Coimbatore",
        expected_final_persona="farmer",
        expected_final_date="tomorrow"
    )
]


class MemoryEvaluator:
    """Runs systematic benchmarks on conversation memory and produces metric scores."""

    @classmethod
    def evaluate_benchmark(cls, dataset: Optional[List[MemoryBenchmarkScenario]] = None) -> Dict[str, Any]:
        """Runs all test scenarios in the dataset and computes accuracy scores (0.0 to 1.0)."""
        scenarios = dataset or MEMORY_EVALUATION_DATASET
        total = len(scenarios)

        loc_matches = 0
        date_matches = 0
        time_matches = 0
        topic_matches = 0
        ambiguity_matches = 0
        lang_matches = 0
        overall_passes = 0

        date_tests = 0
        time_tests = 0
        topic_tests = 0
        lang_tests = 0

        detailed_results = []

        for sc in scenarios:
            mgr = ConversationMemoryManager(ttl_seconds=1800)
            conv_id = f"bench_{sc.scenario_id}"

            # Simulate conversation turns
            for turn_data in sc.turns[:-1]:
                if turn_data.get("role") == "user":
                    user_turn = ConversationTurn(
                        role="user",
                        message=turn_data["user"],
                        location=turn_data.get("location"),
                        language=turn_data.get("language", "en")
                    )
                    # If secondary location mentioned, record it
                    mgr.update_context(
                        conversation_id=conv_id,
                        user_turn=user_turn,
                        location=turn_data.get("location"),
                        date_context=turn_data.get("date"),
                        time_context=turn_data.get("time"),
                        persona=turn_data.get("persona"),
                        language=turn_data.get("language"),
                        active_topic=turn_data.get("topic")
                    )
                    if turn_data.get("secondary_location"):
                        ctx = mgr.get_context(conv_id)
                        ctx.recent_locations.append(turn_data["secondary_location"])

            # Resolve the final follow-up query
            final_turn = sc.turns[-1]
            ctx = mgr.get_context(conv_id)
            resolved = ContextResolver.resolve_query(
                message=final_turn["user"],
                context=ctx
            )

            # Evaluate matches
            loc_pass = resolved.resolved_location.lower() == sc.expected_final_location.lower()
            if loc_pass:
                loc_matches += 1

            date_pass = True
            if sc.expected_final_date:
                date_tests += 1
                date_pass = (resolved.resolved_date or "").lower() == sc.expected_final_date.lower()
                if date_pass:
                    date_matches += 1

            time_pass = True
            if sc.expected_final_time:
                time_tests += 1
                time_pass = (resolved.resolved_time or "").lower() == sc.expected_final_time.lower()
                if time_pass:
                    time_matches += 1

            topic_pass = True
            if sc.expected_final_topic:
                topic_tests += 1
                topic_pass = (resolved.resolved_topic or "").lower() == sc.expected_final_topic.lower()
                if topic_pass:
                    topic_matches += 1

            ambiguity_pass = resolved.is_ambiguous == sc.expected_ambiguity
            if ambiguity_pass:
                ambiguity_matches += 1

            lang_pass = True
            if sc.expected_final_language:
                lang_tests += 1
                lang_pass = resolved.resolved_language == sc.expected_final_language
                if lang_pass:
                    lang_matches += 1

            scenario_pass = loc_pass and date_pass and time_pass and topic_pass and ambiguity_pass and lang_pass
            if scenario_pass:
                overall_passes += 1

            detailed_results.append({
                "scenario_id": sc.scenario_id,
                "passed": scenario_pass,
                "resolved_location": resolved.resolved_location,
                "resolved_date": resolved.resolved_date,
                "resolved_time": resolved.resolved_time,
                "resolved_topic": resolved.resolved_topic,
                "is_ambiguous": resolved.is_ambiguous
            })

        metrics = {
            "total_scenarios": total,
            "overall_pass_rate": round(overall_passes / total, 3) if total > 0 else 0.0,
            "location_inheritance_accuracy": round(loc_matches / total, 3) if total > 0 else 0.0,
            "temporal_inheritance_accuracy": round((date_matches + time_matches) / (date_tests + time_tests), 3) if (date_tests + time_tests) > 0 else 1.0,
            "topic_continuation_accuracy": round(topic_matches / topic_tests, 3) if topic_tests > 0 else 1.0,
            "ambiguity_detection_accuracy": round(ambiguity_matches / total, 3) if total > 0 else 0.0,
            "language_continuity_accuracy": round(lang_matches / lang_tests, 3) if lang_tests > 0 else 1.0,
            "detailed_results": detailed_results
        }
        return metrics
