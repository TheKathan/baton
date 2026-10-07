.PHONY: install uninstall test lint

install:        ## install the baton command for this user (editable)
	./install.sh

uninstall:
	./install.sh --uninstall

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	uvx ruff check src tests
