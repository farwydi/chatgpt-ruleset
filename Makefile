PYTHON ?= python3

.PHONY: build clean

build:
	$(PYTHON) scripts/build_ruleset.py

clean:
	rm -rf dist
