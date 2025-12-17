from typing import Dict, Any, List, Optional
import math

def compute_analysis_diff(pre: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compares two analysis dictionaries (pre and post) and returns a structured difference.
    Matches the logic of PipelineLogger.print_comparison.
    """
    diffs = {
        "session": {},
        "stems": {}
    }

    # --- SESSION COMPARISON ---
    pre_sess = pre.get("session", {})
    post_sess = post.get("session", {})

    keys = set(pre_sess.keys()) | set(post_sess.keys())

    # Filter for numeric metrics
    for k in keys:
        v1 = pre_sess.get(k)
        v2 = post_sess.get(k)

        if v1 is None and v2 is None:
            continue

        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            diff_val = v2 - v1
            # Only record if there is a meaningful difference or if we want to track everything
            # Logger tracks everything but highlights diffs. We record everything here.
            diffs["session"][k] = {
                "before": v1,
                "after": v2,
                "diff": diff_val,
                "changed": abs(diff_val) >= 0.001
            }

    # --- STEMS COMPARISON ---
    pre_stems = {s.get("file_name", "unknown"): s for s in pre.get("stems", [])}
    post_stems = {s.get("file_name", "unknown"): s for s in post.get("stems", [])}

    common_stems = sorted(list(set(pre_stems.keys()) & set(post_stems.keys())))

    for stem_name in common_stems:
        s1 = pre_stems[stem_name]
        s2 = post_stems[stem_name]

        stem_diffs = {}
        stem_keys = set(s1.keys()) | set(s2.keys())

        for k in stem_keys:
            v1 = s1.get(k)
            v2 = s2.get(k)

            if v1 is None and v2 is None:
                continue

            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                diff_val = v2 - v1
                stem_diffs[k] = {
                    "before": v1,
                    "after": v2,
                    "diff": diff_val,
                    "changed": abs(diff_val) >= 0.001
                }

        if stem_diffs:
            diffs["stems"][stem_name] = stem_diffs

    return diffs
