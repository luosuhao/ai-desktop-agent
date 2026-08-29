"""Reasonix - Cache-first agent loop optimization for token/cost reduction

Key concepts:
- Append-only session: immutable conversation history
- Stable prefix prompt: system prompt + repo summary cached
- Tool schema fixed and cached
- Rolling task state compression
- Cache hit monitoring
"""

import time
import json
import hashlib
from typing import List, Dict, Optional, Any
from datetime import datetime


class CacheMetrics:
    """Track cache hit rates and token savings"""

    def __init__(self):
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.input_tokens_saved = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.latencies: List[float] = []
        self.request_log: List[Dict] = []

    def record_request(self, input_tokens: int, output_tokens: int,
                       latency_ms: float, cache_hit: bool):
        self.total_requests += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.latencies.append(latency_ms)
        if cache_hit:
            self.cache_hits += 1
            self.input_tokens_saved += input_tokens * 0.9  # 90% reduction on cache hit
        else:
            self.cache_misses += 1

        self.request_log.append({
            "timestamp": datetime.now().isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "cache_hit": cache_hit
        })

    def reset(self):
        """Reset all cache metrics"""
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.input_tokens_saved = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.latencies.clear()
        self.request_log.clear()

    @property
    def cache_hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    @property
    def avg_input_tokens(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_input_tokens / self.total_requests

    @property
    def total_cost_saved(self) -> float:
        """Estimate cost savings from caching"""
        # Rough: $0.15/M input tokens for Claude, cache = 90% cheaper
        cache_cost = (self.total_input_tokens - self.input_tokens_saved) * 0.15 / 1_000_000
        no_cache_cost = self.total_input_tokens * 0.15 / 1_000_000
        return no_cache_cost - cache_cost

    def get_report(self) -> Dict:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate * 100, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "avg_input_tokens": round(self.avg_input_tokens, 2),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "input_tokens_saved": round(self.input_tokens_saved),
            "estimated_cost_saved_usd": round(self.total_cost_saved, 4)
        }


class OptimizedAgentLoop:
    """Cache-first agent loop with prefix stability and state compression"""

    def __init__(self, agent):
        self.agent = agent
        self.cache_metrics = CacheMetrics()
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.system_prefix = ""
        self.is_prefix_stable = False

    def build_stable_prefix(self, repo_summary: str = "", task_context: str = "") -> str:
        """Build a stable system prompt prefix for caching"""
        prefix_parts = [
            "You are an AI Coding Agent in a desktop application.",
            "",
            "## System Configuration",
            f"- Session: {self.session_id}",
            "- Available tools: read_file, write_file, execute_command, create_checkpoint, rollback_checkpoint, list_directory, run_tests, get_git_diff",
            "- Always create a checkpoint before editing files",
            "- Execute tests after making changes (use run_tests for Java)",
            "- Report errors clearly with file paths and line numbers",
            "- CRITICAL: You MUST use write_file() to save generated code, never just print it",
            "- Default to writing Java code unless the task explicitly specifies another language",
            "- Use list_directory() to explore project structure",
            "- Use get_git_diff() to review changes before finalizing",
            "",
        ]

        if repo_summary:
            prefix_parts.append("## Repository Context")
            prefix_parts.append(repo_summary)
            prefix_parts.append("")

        if task_context:
            prefix_parts.append("## Current Task")
            prefix_parts.append(task_context)
            prefix_parts.append("")

        self.system_prefix = "\n".join(prefix_parts)
        self.is_prefix_stable = True
        return self.system_prefix

    def get_fixed_tool_schemas(self) -> List[Dict]:
        """Return fixed tool schemas (cacheable)"""
        return self.agent.tools.get_schemas()

    def compress_error_log(self, error_log: str, max_lines: int = 50) -> str:
        """Compress error logs by removing redundant lines"""
        lines = error_log.split("\n")
        if len(lines) <= max_lines:
            return error_log

        # Keep first 10 and last 40 lines
        compressed = lines[:10] + ["... (truncated)"] + lines[-(max_lines - 10):]
        return "\n".join(compressed)

    def roll_task_state(self, history: List[Dict], max_messages: int = 30) -> List[Dict]:
        """Compress task state by summarizing older messages.
        Preserves tool_call<->tool result pairs to avoid broken references."""
        if len(history) <= max_messages:
            return history

        system_msgs = [m for m in history if m.get("role") == "system"]

        # Find a safe cutoff: keep recent messages, but ensure
        # we never split tool_call<->tool result pairs
        cutoff_idx = len(history) - max_messages

        # Walk back from cutoff to find start of a complete tool_call pair
        adjusted_cutoff = cutoff_idx
        for i in range(cutoff_idx, max(len(system_msgs) - 1, 0), -1):
            if history[i].get("role") == "tool":
                adjusted_cutoff = i - 1
            else:
                # Check if this assistant has tool_calls that need their results
                if history[i].get("role") == "assistant" and history[i].get("tool_calls"):
                    # If the NEXT message is a tool result, keep this assistant
                    if i + 1 < len(history) and history[i + 1].get("role") == "tool":
                        adjusted_cutoff = i
                        break
                break

        recent_msgs = history[adjusted_cutoff:]

        # Create summary of dropped messages
        dropped = history[len(system_msgs):adjusted_cutoff]
        dropped_assistant = sum(1 for m in dropped if m.get("role") == "assistant" and not m.get("tool_calls"))
        dropped_pairs = sum(1 for m in dropped if m.get("role") == "assistant" and m.get("tool_calls"))

        summary = {
            "role": "system",
            "content": f"[Summary of {len(dropped)} dropped messages: {dropped_assistant} assistant turns, {dropped_pairs} tool_call pairs]"
        }

        return system_msgs + [summary] + recent_msgs

    def execute_with_cache(self, task_description: str,
                           repo_summary: str = "",
                           max_rounds: int = 20) -> Dict:
        """Execute task with cache optimization"""
        # Save initial file state and reset for fresh execution
        self.agent._save_initial_files()
        self.agent.task_state = {
            "task_id": hashlib.md5(task_description.encode()).hexdigest()[:8],
            "description": task_description,
            "plan": [], "current_step": 0,
            "read_files": [], "edited_files": [],
            "test_results": [], "errors": []
        }
        start_time = time.time()

        # Build stable prefix
        self.build_stable_prefix(repo_summary, task_description)

        messages = [{"role": "system", "content": self.system_prefix}]
        tool_schemas = self.get_fixed_tool_schemas()
        round_num = 0

        while round_num < max_rounds:
            round_num += 1

            # Simulate cache metrics for monitoring
            is_cache_hit = round_num > 1 and self.is_prefix_stable
            req_start = time.time()

            response = self.agent.adapter.chat(messages, tool_schemas)
            latency = (time.time() - req_start) * 1000

            # Estimate token counts
            input_tokens = len(json.dumps(messages, ensure_ascii=False)) // 4
            output_tokens = len(response.get("content", "")) // 4

            self.cache_metrics.record_request(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                cache_hit=is_cache_hit
            )

            # Build assistant message (DeepSeek requires null content when tool_calls present)
            assistant_msg = {"role": "assistant"}
            if response.get("content"):
                assistant_msg["content"] = response["content"]
            if response["tool_calls"]:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    }
                    for tc in response["tool_calls"]
                ]
                if "content" not in assistant_msg:
                    assistant_msg["content"] = None
            messages.append(assistant_msg)

            if not response["tool_calls"]:
                break

            for tc in response["tool_calls"]:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                result = self.agent.tools.execute(func_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })

            # Roll task state periodically
            if round_num % 5 == 0:
                messages = self.roll_task_state(messages)

        total_time = time.time() - start_time

        return {
            "task_id": self.agent.task_state["task_id"],
            "session_id": self.session_id,
            "rounds": round_num,
            "total_time_seconds": round(total_time, 2),
            "cache_metrics": self.cache_metrics.get_report(),
            "read_files": self.agent.task_state["read_files"],
            "edited_files": self.agent.task_state["edited_files"],
            "checkpoints_count": len(self.agent.checkpoints),
            "conversation_history": messages
        }
