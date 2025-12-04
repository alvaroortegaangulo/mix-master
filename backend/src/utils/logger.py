import sys
import logging
from typing import Any, Dict, List, Optional
import math

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

class PipelineLogger:
    def __init__(self):
        self.logger = logging.getLogger("pipeline")
        self.logger.setLevel(logging.INFO)
        # Prevent propagation to root logger to avoid double printing or system prefixes
        self.logger.propagate = False

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            # Clean formatter, just the message
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def print_header(self, title: str, color: str = CYAN):
        border = "=" * 60
        # Print an empty line separately to ensure prefix applies cleanly if needed
        self.logger.info("")
        self.logger.info(f"{color}{BOLD}{border}{RESET}")
        self.logger.info(f"{color}{BOLD}{title.center(60)}{RESET}")
        self.logger.info(f"{color}{BOLD}{border}{RESET}")

    def print_section(self, title: str, color: str = BLUE):
        self.logger.info("")
        self.logger.info(f"{color}{BOLD}>> {title}{RESET}")

    def print_metric(self, name: str, value: Any, target: Any = None, status: str = "INFO", details: str = ""):
        """
        Prints a metric check result.
        Status: PASS, FAIL, WARN, INFO
        """
        status_color = {
            "PASS": GREEN,
            "FAIL": RED,
            "WARN": YELLOW,
            "INFO": WHITE
        }.get(status, WHITE)

        # Symbol
        symbol = {
            "PASS": "✔",
            "FAIL": "✘",
            "WARN": "⚠",
            "INFO": "ℹ"
        }.get(status, "•")

        val_str = f"{value}"
        if isinstance(value, float):
            val_str = f"{value:.2f}"

        target_str = ""
        if target is not None:
            if isinstance(target, float):
                target_str = f" (Target: {target:.2f})"
            else:
                target_str = f" (Target: {target})"

        line = f"{status_color}[{symbol}] {BOLD}{name:<30}{RESET}: {val_str}{target_str}"
        if details:
            line += f" | {details}"

        self.logger.info(line)

    def print_comparison(self, pre: Dict[str, Any], post: Dict[str, Any], title: str = "Analysis Comparison"):
        """
        Compares two dictionaries (flat or nested) and prints differences.
        Focuses on 'session' metrics usually found in analysis JSONs.
        """
        # Blank line before section and CYAN color as requested
        self.logger.info("")
        self.print_section(title, color=CYAN)

        # --- SESSION COMPARISON ---

        # Flatten simple keys for session
        pre_sess = pre.get("session", {})
        post_sess = post.get("session", {})

        keys = set(pre_sess.keys()) | set(post_sess.keys())

        # Filter for numeric metrics but show ALL of them as requested
        interesting_keys = sorted([k for k in keys if isinstance(pre_sess.get(k), (int, float)) or isinstance(post_sess.get(k), (int, float))])

        if interesting_keys:
            self.logger.info(f"{BOLD}{'Metric':<40} | {'Before':<15} | {'After':<15} | {'Diff':<10}{RESET}")
            self.logger.info("-" * 90)

            for k in interesting_keys:
                v1 = pre_sess.get(k)
                v2 = post_sess.get(k)

                if v1 is None and v2 is None:
                    continue

                v1_str = f"{v1:.2f}" if isinstance(v1, (int, float)) else str(v1)
                v2_str = f"{v2:.2f}" if isinstance(v2, (int, float)) else str(v2)

                diff_str = "-"
                row_color = RESET

                if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                    diff = v2 - v1
                    if abs(diff) < 0.001:
                        diff_str = "="
                    else:
                        diff_str = f"{diff:+.2f}"
                        row_color = YELLOW

                row = f"{row_color}{k:<40} | {v1_str:<15} | {v2_str:<15} | {diff_str:<10}{RESET}"
                self.logger.info(row)
        else:
            self.logger.info("No numeric session metrics found to compare.")

        # --- STEMS COMPARISON (Per Stem Tables) ---

        pre_stems = {s.get("file_name", "unknown"): s for s in pre.get("stems", [])}
        post_stems = {s.get("file_name", "unknown"): s for s in post.get("stems", [])}

        common_stems = sorted(list(set(pre_stems.keys()) & set(post_stems.keys())))

        if common_stems:
            self.logger.info("") # Spacing
            self.logger.info(f"{CYAN}{BOLD}>> Per-Stem Comparison{RESET}")

            for stem_name in common_stems:
                s1 = pre_stems[stem_name]
                s2 = post_stems[stem_name]

                # Find all numeric metrics in the stem data
                stem_keys = set(s1.keys()) | set(s2.keys())
                stem_metrics = sorted([k for k in stem_keys if isinstance(s1.get(k), (int, float)) or isinstance(s2.get(k), (int, float))])

                if not stem_metrics:
                    continue

                self.logger.info("")
                self.logger.info(f"{BOLD}Stem: {stem_name}{RESET}")
                self.logger.info("-" * 90)
                self.logger.info(f"{BOLD}{'Metric':<40} | {'Before':<15} | {'After':<15} | {'Diff':<10}{RESET}")
                self.logger.info("-" * 90)

                for k in stem_metrics:
                    v1 = s1.get(k)
                    v2 = s2.get(k)

                    if v1 is None and v2 is None:
                        continue

                    v1_str = f"{v1:.2f}" if isinstance(v1, (int, float)) else str(v1)
                    v2_str = f"{v2:.2f}" if isinstance(v2, (int, float)) else str(v2)

                    diff_str = "-"
                    row_color = RESET

                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        diff = v2 - v1
                        if abs(diff) < 0.001:
                            diff_str = "="
                        else:
                            diff_str = f"{diff:+.2f}"
                            row_color = YELLOW

                    row = f"{row_color}{k:<40} | {v1_str:<15} | {v2_str:<15} | {diff_str:<10}{RESET}"
                    self.logger.info(row)


    def log_stage_result(self, stage_id: str, success: bool):
        color = GREEN if success else RED
        res = "SUCCESS" if success else "FAILURE"
        # Color the whole block/text
        self.print_header(f"Stage {stage_id} Completed: {res}", color=color)

    # Method to filter verbose logs
    def info(self, msg: str, *args, **kwargs):
        # Silence logs starting with [S...] or specific tags unless they are warnings/errors (handled separately usually)
        # But here we only override info.

        # Tags to silence:
        # [S...], [mixdown_stems], [cleanup], [pipeline]

        if msg.startswith("["):
            # Check for stage prefix like [S1_...] or [mixdown_stems]
            # We want to keep [✔], [✘], [⚠], [ℹ] which might be in msg if passed directly (though print_metric handles that via self.logger.info)
            # print_metric constructs the string with colors, so it might not start cleanly with "[" if colors are there.
            # But here msg is the raw string passed to logger.info elsewhere.

            # Simple heuristic: if it looks like a stage tag or verbose tag
            # Tags to suppress explicitly mentioned by user
            if any(msg.startswith(tag) for tag in ["[mixdown_stems]", "[cleanup]", "[pipeline]", "[copy_stems]"]):
                return

            # Suppress [S...] tags BUT we need to be careful not to suppress useful info if it's the only info.
            # User said: "Los logs del procesamiento del stage, es decir, todos los que ahora mismo empiezan por [S2_GROUP_PHASE_DRUMS]..."
            # This implies the internal progress logs.
            # We must NOT suppress the Analysis Comparison or Metrics Limits Check, but those don't start with [Tag].
            if msg.startswith("[S") and "]" in msg:
                 # Check if it is a stage tag e.g. [S0_SESSION_FORMAT]
                 tag_end = msg.find("]")
                 tag = msg[1:tag_end]
                 # If tag starts with S and followed by digit (S0, S1, S10)
                 if len(tag) > 1 and tag[0] == 'S' and tag[1].isdigit():
                     return

        self.logger.info(msg, *args, **kwargs)

# Global instance
logger = PipelineLogger()
