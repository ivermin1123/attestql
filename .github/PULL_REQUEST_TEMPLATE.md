# What this changes

<!-- One paragraph: the behaviour before, the behaviour after. -->

## Why

<!-- The defect, the measurement or the request behind it. Link the issue when there is one. -->

## Evidence

<!--
A claim about what the code now does needs something a reader can rerun: a test name, a command
with its output, or a record under audit/ that shows it. A number that ends up in the README or
the site needs a row in docs/claims-register.md naming the artifact it came from.
-->

## Checklist

- [ ] `just check` is green locally, both sandboxes included.
- [ ] Behaviour that changed has a test that fails without the change.
- [ ] Documentation is updated where user-facing behaviour, flags or output moved.
- [ ] The prose added carries no em dash, en dash or curly quote.
