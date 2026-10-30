"""Pure baseline reconstruction from explicit N6 declarations and retained N2 inputs."""

from ..analytical.policy_release import payload_hash
from .arithmetic import median, statistics
from .contracts import METRIC, RELEASE
from .evidence import metadata_reasons, quality_reasons, scope


def stratum_id(value):
    return "passive-stratum-" + payload_hash(dict(method_release=RELEASE, scope=value))[7:]


def reconstruct_baseline(evidence, inputs):
    from .models import same

    if tuple(i.entry_id for i in inputs) != tuple(e.entry_id for e in evidence.report.entries):
        raise ValueError("N9 baseline entry inventory mismatch")
    scope_members = {}
    for item in inputs:
        declaration, entry = evidence.entry(item.entry_id)
        reasons = metadata_reasons(evidence, declaration, entry)
        sid = None
        if reasons:
            if item.window is not None:
                raise ValueError("N9 metadata exclusion cannot retain a baseline window")
        else:
            if item.window is None:
                raise ValueError("N9 baseline original window missing")
            evidence.bind_window(declaration, entry, item.window)
            projection = scope(item.window)
            sid = stratum_id(projection)
            scope_members.setdefault(sid, (projection, []))[1].append(item)
            reasons.extend(quality_reasons(item.window))
        same(
            dict(
                entry_id=item.entry_id,
                group_id=item.group_id,
                stratum_id=item.stratum_id,
                selected=item.selected,
                reason_codes=list(item.reason_codes),
            ),
            dict(
                entry_id=entry.entry_id,
                group_id=entry.group_id,
                stratum_id=sid,
                selected=not reasons,
                reason_codes=reasons,
            ),
        )
    strata = []
    for sid, (projection, members) in sorted(scope_members.items()):
        groups, values = [], []
        for gid in sorted({m.group_id for m in members}):
            group = [m for m in members if m.group_id == gid]
            selected = [m for m in group if m.selected]
            observations = [m.window.measurements[METRIC].summary.value for m in selected]
            values.append(observations)
            groups.append(
                dict(
                    group_id=gid,
                    entry_ids=[m.entry_id for m in group],
                    selected_entry_ids=[m.entry_id for m in selected],
                    value=median(observations) if observations else None,
                )
            )
        strata.append(dict(stratum_id=sid, scope=projection, groups=groups, **statistics(values)))
    selected = sum(i.selected for i in inputs)
    count = dict(
        retained_entries=len(inputs),
        metadata_eligible_entries=sum(i.window is not None for i in inputs),
        selected_entries=selected,
        excluded_entries=len(inputs) - selected,
        retained_strata=len(strata),
        provisional_strata=sum(s["state"] == "provisional" for s in strata),
    )
    return strata, count, "provisional" if count["provisional_strata"] else "rejected"
