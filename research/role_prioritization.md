# Prototype role-priority sensitivity

Compared the three highest measured gaps under uniform and role-weighted ranking across 100
synthetic baselines. Ties were ordered by topic name. The weighted list uses
`max(0, 75 - topic score) × role weight`.

- 44 baselines changed at least one top-three topic.
- Mean overlap was 2.51 of three topics.

The comparison measures sensitivity to the selected weights. It provides no evidence
about which ranking improves learning or agrees with independent role experts.
