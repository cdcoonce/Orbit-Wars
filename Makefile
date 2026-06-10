# afk fleet git conventions — apply the committed .gitconfig to this clone.
#
# Self-contained (no afk-driver dependency): wires include.path idempotently,
# so `git config` settings in .gitconfig (e.g. fetch.prune) take effect here.
# The afk executor also applies this automatically during its cycle preflight.
.PHONY: setup
setup:
	@git config --local --get-all include.path | grep -qx '../.gitconfig' \
		|| git config --local --add include.path '../.gitconfig'
	@echo "wired git conventions (.gitconfig)"
