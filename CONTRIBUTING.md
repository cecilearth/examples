# Contributing

Thanks for considering a contribution! This repo holds Cecil examples; new tutorials, use cases, and skills are all welcome.

## What goes where

- **`tutorials/`** — focused walkthroughs of a single technique (e.g. introduction to xarray, filter no-data values, reproject CRS). Aimed at someone learning a concept.
- **`use-cases/`** — end-to-end workflows that solve a real-world question (e.g. calculate total carbon storage, generate control plots). Aimed at someone with a concrete task.
- **`skills/`** — [Anthropic Agent Skills](https://www.anthropic.com/news/skills) for AI agents and developers reaching for a recipe. Each skill is a directory containing a `SKILL.md`.

If you're not sure where something belongs, open an issue first to discuss.

## Notebook checklist

Before opening a PR with a `.ipynb`:

- [ ] Notebook validates: `python -c "import nbformat; nbformat.validate(nbformat.read('path/to/your.ipynb', as_version=4))"`
- [ ] Runs end-to-end against the current `cecil` SDK with `CECIL_API_KEY` set in the environment.
- [ ] No hardcoded API keys, account IDs, or other secrets.
- [ ] AOI is modest in size — small examples run faster and keep dataset costs down for readers.
- [ ] Title (`## Your Title`) is the first markdown cell.
- [ ] Outputs: keep them if they add value (a rendered plot helps readers skim); strip them for runnable demos that should always re-execute.

## Skill checklist

Before opening a PR with a `skills/<name>/SKILL.md`:

- [ ] Directory name is kebab-case and matches the `name` field in the frontmatter.
- [ ] Frontmatter contains `name`, `description`, `license: MIT`.
- [ ] Body covers prerequisites, steps, important constraints, and references — see `skills/subscribe-and-load/SKILL.md` for a template.
- [ ] Cross-references to other skills use relative paths (e.g. `../subscribe-and-load/SKILL.md`).

## PR flow

1. Fork the repo and branch off `main`.
2. Add your file in the right folder.
3. Push and open a PR. The PR template will prompt you with a checklist; CI will validate notebooks and skills automatically.

## Questions

File an issue or drop in the [Cecil Slack community](https://join.slack.com/t/cecil-community/shared_invite/zt-37awi8mww-S6H50Ff7lbU0WO74UYjxXQ).

## License

By contributing, you agree that your work is released under the repo's [MIT license](LICENSE).
