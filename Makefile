.PHONY: gallery gallery-render gallery-open devto lint help

help:
	@echo "Slope Studio — make targets:"
	@echo "  make gallery         Deploy the effects gallery to GitHub Pages (uses existing examples/out/ clips)"
	@echo "  make gallery-render  Re-render ALL effect demos, then deploy (slow)"
	@echo "  make gallery-open    Open the live gallery in a browser"
	@echo "  make devto           Host article images + generate copy-paste-ready devto.md per article"
	@echo "  make lint            ruff check studio/"

# Publish article images to gh-pages + emit articles/<slug>/devto.md with absolute image URLs.
devto:
	./scripts/build_devto.sh

# Deploy the effects gallery (https://dasein108.github.io/slope-studio/).
# Rebuilds index.html from examples/out/, recompresses heavy clips, pushes gh-pages.
gallery:
	./scripts/deploy_gallery.sh

# Same, but regenerate every effect demo first (needs render deps + time).
gallery-render:
	RENDER=1 ./scripts/deploy_gallery.sh

gallery-open:
	open https://dasein108.github.io/slope-studio/

lint:
	uvx ruff check studio/
