# Solver configs carry executable YAML tags

**Category:** technical debt
**Priority:** low
**Status:** open

## Context

The kinet solver writes a config beside each dataset, for example
`sys_Re-5e4_Ma-1en1/configs/dc804f.yaml`, which carries
`!!python/object/apply:kinet.config...` tags. Reading it with `yaml.unsafe_load` would execute
arbitrary constructors on a file living in shared project space that we do not control.

Nothing currently reads these files, so this is a note for whoever first wants the solver
parameters rather than a live problem.

## What is needed

A SafeLoader subclass with a tag-dropping multi-constructor, which parses the file cleanly
and discards only the enum values that are not needed:

    class SimConfigLoader(yaml.SafeLoader):
        pass

    SimConfigLoader.add_multi_constructor(
        "tag:yaml.org,2002:python/object/apply:", lambda loader, suffix, node: None)

Note the physical parameters are not top-level keys -- they are nested under `solver` and
`normalization` -- so grep before relying on a path.

## Acceptance criteria

The solver config for a dataset parses without `unsafe_load`, and the Reynolds and Mach
numbers can be read from it.

## Related

`configs/dataset/*.yaml`, where these values are currently duplicated by hand.
