# Dynamic Clash Group Generation Plan

## Goal

Move the Clash endpoint to the native 3x-ui Clash subscription and generate proxy groups automatically from the returned proxies.

Keep the old `vless://` conversion path as a separate legacy endpoint.

## Decisions

- Auto generation applies only to the Clash endpoint.
- Manual proxy-group files fully replace auto-generated groups if they are present.
- Rules remain file-driven and are still loaded separately.

## Plan

1. Split the endpoints cleanly.
- Keep one endpoint for the legacy VLESS/base64 conversion.
- Keep a separate Clash endpoint that uses the native 3x-ui Clash subscription directly.
- Make sure the Clash endpoint no longer depends on converting `vless://` entries into Clash config.

2. Refactor the Clash pipeline.
- Fetch native Clash YAML from each source panel.
- Parse and merge only the `proxies` list from upstream Clash subscriptions.
- Keep the existing proxy cleanup and deduplication logic.
- do not use the groups or rules from 3x-ui
- Preserve the current behavior of ignoring failed sources and continuing with the rest.

3. Add auto proxy-group generation.
- Generate proxy groups from the merged proxy names after deduplication.
- Group proxies by common server name.
- Example: `sweden 1`, `sweden 2`, and `sweden 443` should become one group named `sweden`.
- If only one matching proxy exists, still create a valid one-item group.
- Use a predictable group type and structure that Mihomo/Clash can consume.

4. Define the naming heuristic.
- Normalize proxy names before grouping.
- Strip common suffixes like trailing numbers and port-like tokens when they are clearly just instance identifiers.
- Keep the heuristic conservative so intentional names are not merged incorrectly.

5. Support manual group overrides.
- If a proxy-groups file exists, load it and use it as-is.
- Do not merge auto-generated groups with manual ones in that case.
- Keep the existing per-`sub_id` override behavior if needed.

6. Keep rules unchanged.
- Continue loading rules from YAML files.
- Do not tie rule generation to group generation in the first iteration.

7. Update configuration and docs.
- Document that Clash now uses the native 3x-ui Clash subscription.
- Document the legacy VLESS conversion endpoint separately.
- Document how auto grouping works.
- Document that manual proxy-group files override auto generation completely.


## Implementation order

1. Split endpoint behavior in `app/main.py`.
2. Add proxy-name normalization and grouping helpers.
3. Wire auto generation into the Clash merge path.
4. Preserve manual proxy-groups as a full override.
5. Update docs and examples.
6. Add tests for grouping and endpoint behavior.
