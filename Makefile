.PHONY: eval eval-smoke test dashboard compare

eval:
	uv run pha-eval

eval-smoke:
	uv run pha-eval --limit 5

test:
	uv run pytest

dashboard:
	uv run pha dashboard --open

compare:
	uv run pha-compare
