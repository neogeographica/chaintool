.PHONY: readme docs check-installed install devinstall uninstall dist pub \
testpub check-format format lint pre-commit clean distclean

readme:
	./make_readme.py

docs: check-installed readme
	rm -f docs/chaintool.rst docs/modules.rst
	sphinx-apidoc -o docs src/chaintool
	cd docs; make html
	rm -f docs/modules.rst

check-installed:
	@pip show chaintool > /dev/null 2>&1 || \
	    (echo "chaintool not installed" && false)

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

check-format:
	black --check -t py37 -l 79 --experimental-string-processing src/chaintool
	black --check -t py37 -l 79 --experimental-string-processing src/chaintool_completions_helper.py

format:
	black -t py37 -l 79 --experimental-string-processing src/chaintool
	black -t py37 -l 79 --experimental-string-processing src/chaintool_completions_helper.py

# For flake8, W503 should stay suppressed (W504 is instead correct), and I
# often disagree with E731. E203 also needs to stay suppressed (not PEP 8
# compliant for slicing). E501 is disabled in favor of B950.
# For pylint, R0801 is worth checking every now and then but can be too
# twitchy. May need to disable C0330 and C0326 for black-compliance but that
# hasn't been an issue yet.
lint:
	flake8 --select C,E,F,W,B,B950 --ignore W503,E203,E501,E731 src/chaintool
	flake8 --select C,E,F,W,B,B950 --ignore W503,E203,E501,E731 src/chaintool_completions_helper.py
	pylint -d R0801 src/chaintool
	pylint -d R0801 src/chaintool_completions_helper.py

# A helpful target for using in a pre-commit hook if you don't mind waiting a bit.
pre-commit: check-format lint

clean:
	-rm -rf build
	-find . -name '*.pyc' -exec rm {} \;
	-find . -name '__pycache__' -prune -exec rm -rf {} \;
	-find . -name '*.egg-info' -prune -exec rm -rf {} \;
	cd docs; make clean
	rm -f docs/modules.rst

distclean: clean
	-rm -rf dist
