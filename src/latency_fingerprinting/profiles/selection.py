"""Pure metadata selection; never touches held-out feature values or artifact files."""


def selection_reasons(entries):
    labels = {}
    for entry in entries:
        if (
            entry.input_kind == "response"
            and entry.role == "training"
            and entry.eligible
            and entry.label is not None
            and entry.representative_entry_id == entry.entry_id
        ):
            labels.setdefault((entry.partition_id, entry.group_id), set()).add(entry.label)
    mixed = {key for key, values in labels.items() if len(values) > 1}
    reasons = {}
    for entry in entries:
        codes = []
        if entry.input_kind == "missing":
            codes = ["missing_measurements"]
        else:
            if entry.input_kind == "healthy_window":
                codes.append("baseline_only")
            if entry.role != "training":
                codes.append("not_training")
            if not entry.eligible:
                codes.append("n6_excluded")
            if entry.representative_entry_id != entry.entry_id:
                codes.append("duplicate_evidence")
            if entry.input_kind == "response" and entry.label is None:
                codes.append("unknown_label")
            if not codes and (entry.partition_id, entry.group_id) in mixed:
                codes.append("mixed_group_labels")
        reasons[entry.entry_id] = codes
    return reasons, mixed
