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

    def print_header(self, title: str):
        border = "=" * 60
        self.logger.info(f"\n{CYAN}{BOLD}{border}{RESET}")
        self.logger.info(f"{CYAN}{BOLD}{title.center(60)}{RESET}")
        self.logger.info(f"{CYAN}{BOLD}{border}{RESET}")

    def print_section(self, title: str):
        self.logger.info(f"\n{BLUE}{BOLD}>> {title}{RESET}")

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
        self.print_section(title)

        # Flatten simple keys for session
        pre_sess = pre.get("session", {})
        post_sess = post.get("session", {})

        keys = set(pre_sess.keys()) | set(post_sess.keys())

        # Filter for numeric metrics but show ALL of them as requested
        interesting_keys = sorted([k for k in keys if isinstance(pre_sess.get(k), (int, float)) or isinstance(post_sess.get(k), (int, float))])

        if not interesting_keys:
            self.logger.info("No numeric session metrics found to compare.")
            return

        # Header for table
        self.logger.info(f"{BOLD}{'Metric':<40} | {'Before':<15} | {'After':<15} | {'Diff':<10}{RESET}")
        self.logger.info("-" * 90)

        for k in interesting_keys:
            v1 = pre_sess.get(k)
            v2 = post_sess.get(k)

            # Skip if both None
            if v1 is None and v2 is None:
                continue

            # Format values
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
                    row_color = YELLOW # Highlight changed rows

            # Print row
            row = f"{row_color}{k:<40} | {v1_str:<15} | {v2_str:<15} | {diff_str:<10}{RESET}"
            self.logger.info(row)

        # Also check Stems if manageable
        # Stems comparison is tricky because it's a list. We assume same order or match by name.
        pre_stems = {s.get("file_name", "unknown"): s for s in pre.get("stems", [])}
        post_stems = {s.get("file_name", "unknown"): s for s in post.get("stems", [])}

        common_stems = set(pre_stems.keys()) & set(post_stems.keys())

        if common_stems:
            self.logger.info("-" * 90)
            self.logger.info(f"{BOLD}Stem Differences (Significant Only){RESET}")

            for name in sorted(common_stems):
                s1 = pre_stems[name]
                s2 = post_stems[name]

                # Compare specific metrics like LUFS, Peak, RMS
                metrics_to_check = ["integrated_lufs", "true_peak_dbfs", "total_rms_db"]
                diffs = []
                for m in metrics_to_check:
                    val1 = s1.get(m)
                    val2 = s2.get(m)
                    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                        if abs(val1 - val2) > 0.05: # Threshold for showing diff
                             diffs.append(f"{m}: {val1:.2f} -> {val2:.2f}")

                if diffs:
                    self.logger.info(f"{name:<30} | " + " || ".join(diffs))

    def log_stage_result(self, stage_id: str, success: bool):
        color = GREEN if success else RED
        res = "SUCCESS" if success else "FAILURE"
        self.print_header(f"Stage {stage_id} Completed: {color}{res}{RESET}")

# Global instance
logger = PipelineLogger()
