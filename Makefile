PIXI := $(shell command -v pixi 2>/dev/null || echo "$(HOME)/.pixi/bin/pixi")
ifdef NOCONDA
CONDA_RUN  :=
else
CONDA_RUN  := $(PIXI) run --
endif
SRC        := src
LOCALE_DIR := src/pbnightingale/locale
POT_FILE   := $(LOCALE_DIR)/pbnightingale.pot
PO_LOCALES := en fr

# ── Docs ─────────────────────────────────────────────────────────────────────
# Narrative pages only (index.rst + manual/) get translated — api.rst
# (autodoc) and changelog.rst (generated, English-only per CLAUDE.md) never
# do. See CODING.md, "Packaging & docs" — docs/locale/ mirrors src/…/locale/
# but is a wholly separate sphinx-intl catalog, one .po per source file.
DOCS           := docs
DOCS_LOCALE    := $(DOCS)/locale
DOC_LOCALES    := fr
# sphinx-build -b gettext takes individual source files, not a directory —
# passing docs/manual/ as-is is silently ignored (with a warning), so this
# must be a real file list, not a directory glob pattern.
DOCS_NARRATIVE := $(DOCS)/index.rst $(wildcard $(DOCS)/manual/*.rst)

R  := \033[0m
B  := \033[1m
G  := \033[32m
Y  := \033[33m
C  := \033[36m

# All Python sources. Sorted: `find` order is filesystem-dependent, and
# pybabel's extraction order follows file processing order — an unsorted
# list makes `make translate` reorder .po entries on every run even with no
# string changes, dirtying the tree for no reason.
PY_SOURCES := $(shell find $(SRC)/pbnightingale -name "*.py" \
                ! -path "*/__pycache__/*" | sort)

PO_FILES        := $(foreach lang,$(PO_LOCALES),$(LOCALE_DIR)/$(lang)/LC_MESSAGES/pbnightingale.po)
TRANSLATE_STAMP := .translate.stamp

.DEFAULT_GOAL := help
.PHONY: help venv venv-update install run test coverage hooks lint format ci \
        clean translate force-translate new-lang compile-translations \
        update-icons dist srcdist docs docs-live docs-translate docs-stats

help: ## This help
	@printf "$(B)$(C)PBNightingale — Development Tasks$(R)\n\n"
	@printf "$(Y)Usage:$(R) make $(G)<target>$(R)\n\n"
	@printf "$(Y)Targets:$(R)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS=":.*?## "}; {printf "  $(G)%-14s$(R) %s\n", $$1, $$2}'
	@printf "\n$(Y)Variables:$(R)\n"
	@printf "  $(G)NOCONDA$(R)        Bypass pixi wrapping; tools must be on PATH\n"
	@printf "                 e.g. $(C)make test NOCONDA=1$(R)  or  $(C)export NOCONDA=1$(R)\n"

venv: ## Create/update the pixi environment from pyproject.toml (installs pixi if missing)
	@if ! command -v pixi >/dev/null 2>&1 && [ ! -x "$(PIXI)" ]; then \
		printf "$(C)pixi not found — installing...$(R)\n"; \
		curl -fsSL https://pixi.sh/install.sh | sh; \
	fi
	@printf "$(C)Installing pixi environment...$(R)\n"
	$(PIXI) install
	@printf "$(G)Done! Run tasks with:$(R) make <target>  (e.g. make run, make test)\n"

venv-update: ## Update the pixi environment / lockfile from pyproject.toml
	@printf "$(C)Updating pixi environment...$(R)\n"
	$(PIXI) update
	@printf "$(G)Done.$(R)\n"

# ── i18n ──────────────────────────────────────────────────────────────────────

translate: $(TRANSLATE_STAMP) ## Extract translatable strings, update .po files and compile .mo

$(TRANSLATE_STAMP): $(PY_SOURCES) $(PO_FILES)
	@printf "$(C)Extracting all translatable strings...$(R)\n"
	@printf '_("language_name")\n' > tools/_lang_name_stub.py
	$(CONDA_RUN) pybabel extract -F babel.cfg \
	    --copyright-holder="Marcel Spock" \
	    --msgid-bugs-address="mrspock@cardolan.net" \
	    --project="PBNightingale" \
	    --no-location \
	    -k _ -o $(POT_FILE) \
	    $(PY_SOURCES) tools/_lang_name_stub.py
	@rm -f tools/_lang_name_stub.py
	@printf "$(C)Updating .po files...$(R)\n"
	$(CONDA_RUN) pybabel update -i $(POT_FILE) -d $(LOCALE_DIR) \
	    -D pbnightingale --no-fuzzy-matching
	$(CONDA_RUN) python tools/fix_po_files.py $(LOCALE_DIR)
	@printf "$(C)Compiling .mo files...$(R)\n"
	$(CONDA_RUN) pybabel compile -d $(LOCALE_DIR) -D pbnightingale
	@printf "$(G)Done.$(R)\n"
	@touch $@

force-translate: ## Force-rebuild translations regardless of source changes
	@rm -f $(TRANSLATE_STAMP)
	@$(MAKE) translate

new-lang: ## Scaffold a new translation (usage: make new-lang LOCALE=de)
	@test -n "$(LOCALE)" || { \
	    printf "$(Y)Usage:$(R) make new-lang LOCALE=<lang-code>  (e.g. LOCALE=de)\n"; exit 1; }
	@test -f $(POT_FILE) || { \
	    printf "$(Y)Run 'make translate' first to generate the .pot template.$(R)\n"; exit 1; }
	$(CONDA_RUN) pybabel init -i $(POT_FILE) -d $(LOCALE_DIR) \
	    -D pbnightingale -l $(LOCALE)
	@printf "\n$(G)Created:$(R) $(LOCALE_DIR)/$(LOCALE)/LC_MESSAGES/pbnightingale.po\n\n"
	@printf "$(Y)Next steps:$(R)\n"
	@printf "  1. Edit the .po file and translate every msgstr entry.\n"
	@printf "  2. Set the $(B)language_name$(R) msgstr to the language's own name (e.g. 'Deutsch').\n"
	@printf "  3. Add $(B)$(LOCALE)$(R) to PO_LOCALES in the Makefile.\n"
	@printf "  4. Run: $(G)make translate$(R)\n"
	@printf "  5. Commit the .po and .mo files.\n"

compile-translations: ## Compile the committed .po catalogues to .mo (no extraction)
	$(CONDA_RUN) pybabel compile -d $(LOCALE_DIR) -D pbnightingale

# ── Development ───────────────────────────────────────────────────────────────

install: ## Register git hooks (the editable install is handled by `make venv`)
	$(CONDA_RUN) pre-commit install

run: compile-translations ## Launch PBNightingale from the pixi env  (usage: make run ARGS="--version")
	$(CONDA_RUN) python -m pbnightingale $(ARGS)

test: compile-translations ## Run test suite (usage: make run ARGS="tests/tests_something.py")
	$(CONDA_RUN) pytest $(ARGS)

coverage: ## Run test suite and open HTML coverage report
	$(CONDA_RUN) pytest --cov-report=term-missing --cov-report=html
	@printf "$(G)Report:$(R) $(Y)htmlcov/index.html$(R)\n"

hooks: ## Run all pre-commit hooks on all files
	$(CONDA_RUN) pre-commit run --all-files

lint: ## Check code style
	$(CONDA_RUN) ruff check $(SRC)
	$(CONDA_RUN) ruff format --check $(SRC)

format: ## Auto-format source code
	$(CONDA_RUN) ruff format $(SRC)
	$(CONDA_RUN) ruff check --fix $(SRC)

update-icons: ## Sync resources/ icons from PBIcons  (usage: make update-icons ARGS="--dry-run" or ARGS="quit.svg")
	$(CONDA_RUN) python tools/update_icons.py $(ARGS)

docs: ## Build HTML documentation (English source)
	$(CONDA_RUN) sphinx-build -b html $(DOCS) $(DOCS)/_build/html
	@printf "$(G)Open:$(R) $(DOCS)/_build/html/index.html\n"

docs-live: ## Build docs and watch for changes (hot reload)
	$(CONDA_RUN) sphinx-autobuild $(DOCS) $(DOCS)/_build/html

docs-translate: ## Extract narrative-page strings and update docs/locale/*.po
	@printf "$(C)Extracting translatable strings from narrative pages...$(R)\n"
	$(CONDA_RUN) sphinx-build -b gettext $(DOCS) $(DOCS)/_build/gettext $(DOCS_NARRATIVE)
	@printf "$(C)Updating docs/locale/*.po...$(R)\n"
	$(CONDA_RUN) sphinx-intl update -p $(DOCS)/_build/gettext -d $(DOCS_LOCALE) \
	    $(foreach lang,$(DOC_LOCALES),-l $(lang))
	@printf "$(G)Done.$(R) Translate every new msgstr under $(Y)$(DOCS_LOCALE)/$(R), then re-run to verify.\n"

docs-stats: ## Report docs/locale/*.po translation completeness
	$(CONDA_RUN) sphinx-intl stat -d $(DOCS_LOCALE)

# ── Local CI ──────────────────────────────────────────────────────────────────

# No GitHub remote yet: this target stands in for `.github/workflows/ci.yml`,
# run entirely on this machine (see CLAUDE.md, "no publishing to GitHub yet").
ci: lint hooks test ## Run the full local CI pipeline (lint → hooks → test)
	@printf "$(G)Local CI passed.$(R)\n"

clean: ## Remove all build/cache artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage coverage.xml htmlcov .ruff_cache
	rm -rf $(DOCS)/_build $(DOCS)/changelog.rst $(DOCS)/_static/pbnightingale.png \
	       $(DOCS)/_static/icons
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -f $(POT_FILE) $(TRANSLATE_STAMP)

# ── Packaging ─────────────────────────────────────────────────────────────────

# PyInstaller builds natively: run this target on the target OS.
# Version comes from the exact git tag when HEAD is tagged and the tree is
# clean; otherwise "dev".  Output in dist/:
#   Linux   → dist/pbnightingale-<ver>-linux-x86_64
#   Windows → dist/pbnightingale-<ver>-windows-x86_64.exe
#   macOS   → dist/pbnightingale-<ver>-macos-arm64  (.app bundle)
dist: compile-translations ## Build a standalone executable for the current platform
	@ver=$$(bash tools/git_version.sh); \
	printf "$(C)PyInstaller — version: $$ver  platform: $$($(CONDA_RUN) python -c 'import sys; print(sys.platform)')$(R)\n"; \
	mkdir -p dist; \
	PBNIGHTINGALE_VERSION=$$ver $(CONDA_RUN) pyinstaller --clean --noconfirm \
	    --distpath dist --workpath build/pyinstaller \
	    pbnightingale.spec
	@printf "$(G)Done.$(R) Executable in $(Y)dist/$(R)\n"

srcdist: ## Build a source archive (dist/pbnightingale-<ver>-src.tar.gz) via git archive
	@ver=$$(bash tools/git_version.sh); \
	out="dist/pbnightingale-$$ver-src.tar.gz"; \
	printf "$(C)Source archive — version: $$ver$(R)\n"; \
	mkdir -p dist; \
	git archive --format=tar.gz --prefix="pbnightingale-$$ver/" HEAD -o "$$out"; \
	printf "$(G)Done.$(R) Archive: $(Y)$$out$(R)\n"
