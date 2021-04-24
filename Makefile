.PHONY: readme docs install devinstall uninstall dist pub testpub format lint clean distclean

readme:
	./make_readme.py

docs: readme
	rm -f docs/chaintool.rst docs/modules.rst
	sphinx-apidoc -o docs src/chaintool
	cat docs/chaintool.rst | sed '/^Submodules$$/{s/.*/:ref:`search`/;N;s/\n.*//;}' | sed '/^Module contents$$/,$$ d' > docs/chaintool.rst.modified
	mv docs/chaintool.rst.modified docs/chaintool.rst
	cd docs; make html
	rm -f docs/modules.rst

install: readme
	python3 -m pip install .

devinstall: readme
	python3 -m pip install -e .

uninstall:
	python3 -m pip uninstall chaintool -y

dist: distclean readme
	python3 -m build

pub: dist
	./dev-ver-check.py && twine upload dist/*

testpub: dist
	twine upload -r testpypi dist/*

format:
	black -t py37 -l 79 --experimental-string-processing src/chaintool

# For flake8, W503 should stay suppressed (W504 is instead correct). So should
# E203 (not PEP 8 compliant for slicing). E501 is disabled in favor of B950.
# For pylint, restore C0116 once everything has docstrings. R0801 is worth
# checking every now and then but can be too twitchy. May need to disable
# C0330 and C0326 for black-compliance but that hasn't been an issue yet.
lint:
	flake8 --select C,E,F,W,B,B950 --ignore W503,E203,E501 src/chaintool
	pylint -d C0116,R0801 src/chaintool

clean:
	-rm -rf build
	-find . -name '*.pyc' -exec rm {} \;
	-find . -name '__pycache__' -prune -exec rm -rf {} \;
	-find . -name '*.egg-info' -prune -exec rm -rf {} \;
	cd docs; make clean
	rm -f docs/modules.rst

distclean: clean
	-rm -rf dist
